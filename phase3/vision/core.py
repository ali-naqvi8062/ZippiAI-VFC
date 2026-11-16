import hashlib, io, json, os, threading, time
from pathlib import Path
from typing import Literal
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, model_validator

PARTS = {
 'water_tank':'water tank',
 'drip_tray':'drip tray',
 'portafilter':'portafilter',
 'portafilter_handle':'black handle',
 'filter_basket':'filter basket',
 'steam_wand':'steam wand',
 'tank_lid':'water tank lid',
 'control_panel':'control panel buttons',
}
MODEL='IDEA-Research/grounding-dino-tiny'
REVISION='a2bb814dd30d776dcf7e30523b00659f4f141c71'
class Label(BaseModel):
 model_config=ConfigDict(extra='forbid')
 visibility:Literal['visible','absent','ambiguous']
 bbox:list[float]|None=None
 @model_validator(mode='after')
 def valid(self):
  if self.visibility=='visible':
   if self.bbox is None or len(self.bbox)!=4: raise ValueError('Visible targets require a box')
   a,b,c,d=self.bbox
   if not (0<=a<c<=1 and 0<=b<d<=1): raise ValueError('Box must be normalized xyxy with positive area')
  elif self.bbox is not None: raise ValueError('Absent/ambiguous targets must not have boxes')
  return self

def iou(a,b):
 if a is None or b is None:return 0.0
 x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
 inter=x*y;union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
 return inter/union if union>0 else 0.0

class Dataset:
 def __init__(self,root):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
  self.path=self.root/'dataset.json'
 def read(self):
  return json.loads(self.path.read_text()) if self.path.exists() else {'appliance_id':'breville-bes500','images':[],'frozen':False}
 def write(self,d):
  temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(d,indent=2));temp.replace(self.path)
 def add(self,content,session,split,kind,lighting,angle):
  if len(content)>20*1024*1024:raise ValueError('Maximum file size is 20 MB')
  if split not in ['dev','test'] or kind not in ['real_photo','diagram']:raise ValueError('Invalid split or source kind')
  if not session.strip() or not lighting.strip() or not angle.strip():raise ValueError('Record session, lighting and angle')
  with Image.open(io.BytesIO(content)) as source:
   if source.format not in ['JPEG','PNG','WEBP']:raise ValueError('Use JPEG, PNG or WebP')
   if source.width*source.height>30000000:raise ValueError('Maximum image size is 30 megapixels')
   im=ImageOps.exif_transpose(source).convert('RGB');im.thumbnail((1600,1600))
   ident=hashlib.sha256(str(im.size).encode()+im.tobytes()).hexdigest()
   with self.lock:
    d=self.read()
    if d['frozen'] and split=='test':raise ValueError('Test set is frozen; use a new workspace for a new benchmark')
    if any(x['id']==ident for x in d['images']):raise ValueError('Duplicate image: already imported')
    if any(x['session']==session and x['split']!=split for x in d['images']):raise ValueError('A capture session must belong to only one split')
    im.save(self.root/(ident+'.png'))
    row={'id':ident,'session':session,'split':split,'kind':kind,'lighting':lighting,'angle':angle,'width':im.width,'height':im.height,'labels':{}}
    d['images'].append(row);self.write(d);return row
 def label(self,ident,part,value):
  if part not in PARTS:raise ValueError('Unknown part ID')
  value=Label.model_validate(value).model_dump()
  with self.lock:
   d=self.read();row=next((x for x in d['images'] if x['id']==ident),None)
   if row is None:raise ValueError('Image not found')
   if d['frozen'] and row['split']=='test':raise ValueError('Frozen test labels cannot be changed')
   row['labels'][part]=value;self.write(d);return row
 def freeze(self):
  with self.lock:
   d=self.read()
   if d['frozen']:raise ValueError('Test set is already frozen')
   rows=[x for x in d['images'] if x['split']=='test']
   pilot=d.get('evaluation_protocol')=='small-public-photo-pilot'
   minimum=3 if pilot else 50
   required=d.get('required_parts',list(PARTS)) if pilot else list(PARTS)
   if not required or any(p not in PARTS for p in required):raise ValueError('Invalid required parts')
   if len(rows)<minimum or any(x['kind']!='real_photo' for x in rows):raise ValueError(f'Need at least {minimum} real test photos; diagrams do not count')
   if any(not set(required).issubset(x['labels']) for x in rows):raise ValueError('Label every required part as visible, absent or ambiguous on every test photo')
   if not pilot and sum(v['visibility']=='absent' for x in rows for v in x['labels'].values())<20:raise ValueError('Include at least 20 absent-part image/part pairs')
   if any(sum(x['labels'][part]['visibility']=='visible' for x in rows)<(1 if pilot else 5) for part in required):raise ValueError('Need visible test examples for every required part')
   d['detector_config']={'model':MODEL,'revision':REVISION,'prompts':PARTS,'box_threshold':0.35,'text_threshold':0.25}
   d['frozen']=True;d['benchmark_sha256']=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();self.write(d);return d
 def image(self,ident):
  if not any(x['id']==ident for x in self.read()['images']):raise ValueError('Unknown image')
  return self.root/(ident+'.png')

class Detector:
 def __init__(self,cache):self.cache=str(cache);self.lock=threading.Lock();self.model=None
 def load(self):
  if self.model is not None:return
  import torch
  from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
  torch.set_num_threads(4)
  self.processor=AutoProcessor.from_pretrained(MODEL,revision=REVISION,cache_dir=self.cache)
  self.model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL,revision=REVISION,cache_dir=self.cache,use_safetensors=True).eval()
 def predict(self,path,part):
  if part not in PARTS:raise ValueError('Unknown part')
  with self.lock:
   start=time.perf_counter();self.load();loaded=time.perf_counter()
   import torch
   with Image.open(path) as source:im=source.convert('RGB')
   inputs=self.processor(images=im,text=PARTS[part]+'.',return_tensors='pt')
   with torch.inference_mode():output=self.model(**inputs)
   result=self.processor.post_process_grounded_object_detection(output,inputs.input_ids,threshold=0.35,text_threshold=0.25,target_sizes=[(im.height,im.width)])[0]
   candidates=[]
   for box,score in zip(result['boxes'].tolist(),result['scores'].tolist()):
    b=[max(0,min(1,float(v)/size)) for v,size in zip(box,[im.width,im.height,im.width,im.height])]
    if b[0]<b[2] and b[1]<b[3]:candidates.append({'bbox':b,'score':score})
   candidates.sort(key=lambda x:x['score'],reverse=True)
   best=candidates[0] if candidates else None
   return {'part_id':part,'visibility':'candidate' if best else 'not_detected','bbox':best['bbox'] if best else None,'score':best['score'] if best else None,'candidates':candidates,'model':MODEL,'revision':REVISION,'prompt':PARTS[part]+'.','box_threshold':0.35,'text_threshold':0.25,'inference_seconds':time.perf_counter()-loaded,'load_seconds':loaded-start,'total_seconds':time.perf_counter()-start,'note':'Model candidate, not verified identity. No detection does not prove absence.'}

def evaluate(dataset,detector,split):
 d=dataset.read()
 if split not in ['dev','test']:raise ValueError('Invalid split')
 if split=='test' and not d['frozen']:raise ValueError('Freeze a qualified test set first')
 rows=[x for x in d['images'] if x['split']==split]
 if not rows or any(not x['labels'] for x in rows):raise ValueError('Import and label images first')
 records=[]
 for row in rows:
  for part,truth in row['labels'].items():
   if truth['visibility']=='ambiguous':continue
   pred=detector.predict(dataset.image(row['id']),part)
   records.append({'image_id':row['id'],'part_id':part,'truth':truth,'prediction':pred,'iou':iou(truth['bbox'],pred['bbox'])})
 visible=[r for r in records if r['truth']['visibility']=='visible'];negative=[r for r in records if r['truth']['visibility']=='absent']
 def metric(rs):
  pos=[r for r in rs if r['truth']['visibility']=='visible'];neg=[r for r in rs if r['truth']['visibility']=='absent']
  return {'visible_pairs':len(pos),'correct_iou50':sum(r['iou']>=.5 for r in pos),'accuracy_iou50':sum(r['iou']>=.5 for r in pos)/len(pos) if pos else None,'absent_pairs':len(neg),'false_positive_count':sum(r['prediction']['bbox'] is not None for r in neg)}
 import numpy as np
 latency=[r['prediction']['inference_seconds'] for r in records]
 report={'split':split,'image_count':len(rows),'real_photo_count':sum(x['kind']=='real_photo' for x in rows),'ambiguous_pairs_excluded':sum(v['visibility']=='ambiguous' for x in rows for v in x['labels'].values()),'benchmark_sha256':d.get('benchmark_sha256'),'summary':metric(records),'per_part':{p:metric([r for r in records if r['part_id']==p]) for p in PARTS},'latency_seconds':{'p50':float(np.percentile(latency,50)) if latency else None,'p95':float(np.percentile(latency,95)) if latency else None},'records':records,'claim':'Exploratory only; not a held-out benchmark' if split=='dev' else 'Frozen real-photo test; identity depends on correct human annotations'}
 report['evaluation_protocol']=d.get('evaluation_protocol','original-50-photo-protocol')
 if d.get('evaluation_protocol')=='small-public-photo-pilot':report['claim']='Small public-photo pilot; approximate visually reviewed labels; no generalisation or independent held-out accuracy claim'
 report['run_id']=str(time.time_ns());(dataset.root/('evaluation-'+report['run_id']+'.json')).write_text(json.dumps(report,indent=2));return report
