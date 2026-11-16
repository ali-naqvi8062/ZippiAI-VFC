import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
import pdfplumber
from PIL import Image
from .schema import DraftBundle, SAFETY

SAMPLE_HASH='f0a5e4024b1c57996b4a4771dc7ae9b5f29ff931fa915ec4b40569761dd8012f'
ROOT=Path(__file__).resolve().parents[1]


def provider_schema(value):
    """Use Gemini's documented JSON-schema subset; enforce the full schema locally."""
    if isinstance(value,list): return [provider_schema(v) for v in value]
    if not isinstance(value,dict): return value
    allowed={'$id','$defs','$ref','$anchor','type','format','title','description','enum',
             'items','prefixItems','minItems','maxItems','minimum','maximum','anyOf','oneOf',
             'properties','additionalProperties','required'}
    result={}
    for key,item in value.items():
        if key=='const': result['enum']=[item]
        elif key in ['$defs','properties']:
            result[key]={name:provider_schema(schema) for name,schema in item.items()}
        elif key in allowed: result[key]=provider_schema(item)
    return result


def parse_pages(spec, count):
    if not spec:
        return list(range(1,count+1))
    result=set()
    for item in spec.split(','):
        bounds=item.strip().split('-')
        if len(bounds)>2: raise ValueError('Use page numbers or ranges, e.g. 2-7,19-21')
        lo=int(bounds[0]); hi=int(bounds[-1])
        if not 1<=lo<=hi<=count: raise ValueError('Page range outside the PDF')
        result.update(range(lo,hi+1))
    return sorted(result)


def extract(pdf, target, page_spec=None):
    target.mkdir(parents=True,exist_ok=True)
    assets=target/'assets'; assets.mkdir(exist_ok=True)
    result={'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':[], 'warnings':[]}
    with pdfplumber.open(pdf) as document:
        if not 1<=len(document.pages)<=150: raise ValueError('PDF must contain 1-150 pages')
        if any(p.width*p.height>2000000 for p in document.pages): raise ValueError('Oversized PDF page')
        result['page_count']=len(document.pages)
        selected=parse_pages(page_spec,len(document.pages))
        for n in selected:
            p=document.pages[n-1]
            text=p.extract_text(layout=False) or ''
            # Text-aligned tables preserve extraction hypotheses for human inspection.
            tables=p.extract_tables({'vertical_strategy':'text','horizontal_strategy':'text','min_words_vertical':3})
            record={'pdf_page':n,'width':p.width,'height':p.height,'text':text,'tables':tables,
                    'words':p.extract_words(), 'raster_image_count':len(p.images), 'vector_curve_count':len(p.curves)}
            result['pages'].append(record)
            if len(text.strip())<40:
                result['warnings'].append(f'Page {n}: little selectable text; OCR/manual transcription required.')
    if sum(len(p['text']) for p in result['pages'])<100:
        raise ValueError('No useful text found. OCR this scanned PDF before ingestion; no drafts generated.')
    # Render selected pages so vector diagrams survive; embedded-image extraction alone loses them.
    for p in result['pages']:
        n=p['pdf_page']
        stem=assets/f'page-{n}'
        run=subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-singlefile','-scale-to','1400','-png',str(pdf),str(stem)],capture_output=True,timeout=45)
        if run.returncode: raise ValueError('PDF page rendering failed')
        p['page_image']=f'page-{n}.png'
    if result['sha256']==SAMPLE_HASH:
        for n,box,name in [(6,(.09,.10,.88,.69),'components.png'),(7,(.12,.07,.92,.67),'accessories.png')]:
            path=assets/f'page-{n}.png'
            if path.exists():
                with Image.open(path) as im:
                    w,h=im.size
                    im.crop(tuple(int(v*s) for v,s in zip(box,[w,h,w,h]))).save(assets/name)
    result['table_note']='Text-aligned table candidates; PDF row spans must be checked against page images.'
    (target/'extraction.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def generate(extraction, appliance_id, provider='demo'):
    if provider=='demo':
        if extraction['sha256']!=SAMPLE_HASH or appliance_id!='breville-bes500':
            raise ValueError('Bundled LLM drafts apply only to the verified BES500 manual and appliance ID. Use Gemini for another manual.')
        body=json.loads((ROOT/'sample/drafts.json').read_text(encoding='utf-8'))
        metadata=json.loads((ROOT/'sample/generation.json').read_text(encoding='utf-8'))
    elif provider=='gemini':
        key=os.getenv('GEMINI_API_KEY'); model=os.getenv('GEMINI_MODEL')
        if not key or not model: raise ValueError('Set GEMINI_API_KEY and GEMINI_MODEL locally before selecting Gemini.')
        if not re.fullmatch(r'[A-Za-z0-9._-]+',model): raise ValueError('Invalid Gemini model ID')
        pages=[{'pdf_page':p['pdf_page'],'text':p['text'],'reference_image':p['page_image']} for p in extraction['pages']]
        source=json.dumps(pages,ensure_ascii=False)
        if len(source)>150000: raise ValueError('Selected text exceeds 150000 characters; select relevant pages explicitly.')
        prompt=(ROOT/'docs/extraction_prompt.txt').read_text(encoding='utf-8')
        prompt+='\nAppliance ID: '+appliance_id+'\nManual SHA256: '+extraction['sha256']
        prompt+='\nRequired first two steps: '+json.dumps(SAFETY)
        payload={'systemInstruction':{'parts':[{'text':prompt}]},
                 'contents':[{'role':'user','parts':[{'text':'Untrusted PDF source data follows:\n'+source}]}],
                 'generationConfig':{'temperature':0,'responseMimeType':'application/json',
                                     'responseJsonSchema':provider_schema(DraftBundle.model_json_schema())}}
        request=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key})
        with urllib.request.urlopen(request,timeout=180) as response:
            raw=json.load(response)
        try:
            candidate=raw['candidates'][0]
            if candidate.get('finishReason')!='STOP': raise ValueError('Incomplete provider response')
            body=json.loads(''.join(p.get('text','') for p in candidate['content']['parts'] if not p.get('thought')))
        except (KeyError,IndexError,json.JSONDecodeError) as e:
            raise ValueError('Provider returned no valid complete procedure JSON') from e
        metadata={'provider':'gemini','model':model,'model_version':raw.get('modelVersion'),
                  'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'usage':raw.get('usageMetadata'),
                  'mode':'live_api','manual_sha256':extraction['sha256']}
    else:
        raise ValueError('Unknown provider')
    bundle=DraftBundle.model_validate(body)
    for p in bundle.procedures:
        if p.status!='draft' or p.appliance_id!=appliance_id or p.manual_version!=extraction['sha256']:
            raise ValueError('Generated identity/status does not match this ingestion')
        check_evidence(p,extraction)
    return bundle,metadata


def check_evidence(p,extraction):
    pages={x['pdf_page']:x for x in extraction['pages']}
    images={x['page_image'] for x in extraction['pages']}
    if extraction['sha256']==SAMPLE_HASH:
        if 6 in pages: images.add('components.png')
        if 7 in pages: images.add('accessories.png')
    for item in [*p.parts,*p.steps]:
        if item.reference_image and item.reference_image not in images:
            raise ValueError('Unknown reference image')
    for step in p.steps:
        if step.source.kind=='manual':
            source=pages.get(step.source.pdf_page)
            if source is None: raise ValueError('Evidence page was not extracted')
            x1,y1,x2,y2=step.source.region
            if not any(x1 <= ((w['x0']+w['x1'])/2)/source['width'] <= x2 and
                       y1 <= ((w['top']+w['bottom'])/2)/source['height'] <= y2 for w in source['words']):
                raise ValueError('Evidence region contains no extracted text')
    # Geometric validation cannot establish semantic correctness; publication needs human review.
