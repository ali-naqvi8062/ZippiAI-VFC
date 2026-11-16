"""Reproduce the five-photo pilot. Labels were visually authored before inference.
No missing source annotation is interpreted as absence.
"""
import hashlib, json, urllib.request
from pathlib import Path
from vision.core import Dataset

ROOT=Path(__file__).resolve().parent
REPO='start2fix/Coffee-Machine-Parts-Detection'
REV='86f5bdc0a14e9a5eedc2abea27a24012fa52fae7'
# Normalized visible-part extents; partial/uncertain targets excluded.
SELECTION=[
 ('train',3,{'steam_wand':[.545,.26,.61,.60],'drip_tray':[.429,.735,.59,.86]}),
 ('train',17,{'steam_wand':[.537,.106,.674,.666],'control_panel':None}),
 ('train',18,{'steam_wand':[.51,.35,.58,.57],'drip_tray':[.285,.48,.49,.74],'portafilter':[.123,.39,.447,.68]}),
 ('test',1,{'steam_wand':[.42,.15,.59,.49],'drip_tray':[.02,.435,.43,.735],'control_panel':None}),
 ('test',3,{'control_panel':[.135,.15,.622,.39]}),
]
def download(path):
 return urllib.request.urlopen(f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/{path}').read()
def main():
 d=Dataset(ROOT/'data-dedica')
 if d.read()['images']:raise SystemExit('Pilot exists; refusing to overwrite annotations/results')
 metadata={s:[json.loads(x) for x in download(s+'/metadata.jsonl').decode().splitlines()] for s in ['train','test']}
 manifest=[]
 for split,index,labels in SELECTION:
  source=metadata[split][index];name=source['file_name'];content=download(split+'/'+name)
  row=d.add(content,f'{split}-{index:02d}','dev','real_photo','Online photo; capture lighting unknown','Mixed views; see photo')
  for part,box in labels.items():d.label(row['id'],part,{'visibility':'visible' if box else 'absent','bbox':box})
  manifest.append({'image_id':row['id'],'source_split':split,'source_index':index,'source_file':name,'source_sha256':hashlib.sha256(content).hexdigest(),'source_annotation':source,'url':f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/{split}/{name}'})
 state=d.read();state.update(appliance_id='delonghi-dedica-family-pilot',evaluation_protocol='small-public-photo-pilot',minimum_test_photos=3,required_parts=['steam_wand','drip_tray','control_panel'],annotation_author='Assistant visual review; approximate boxes, not manufacturer-verified',scope='Dedica family inferred visually; exact SKUs unverified. All images are exploratory dev images, including original source test images. No model training or prompt tuning performed.')
 d.write(state)
 (ROOT/'docs/pilot-manifest.json').write_text(json.dumps({'repo':REPO,'revision':REV,'images':manifest},indent=2))
 (ROOT/'docs/dataset-card.md').write_bytes(download('README.md'))
 print('Imported',len(manifest),'photos into',d.root)
if __name__=='__main__':main()
