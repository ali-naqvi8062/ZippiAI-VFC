import os
import json
from pathlib import Path
from vision.core import Dataset,Detector,PARTS,iou
root=Path(__file__).resolve().parent
d=Dataset(root/'data-dedica');detector=Detector(Path(os.environ.get('VISION_MODELS',str(root/'models'))))
choices=[('train-18','portafilter','black handle'),('train-17','steam_wand','metal tube'),('test-01','drip_tray','metal tray')]
results=[]
for session,part,prompt in choices:
 row=next(x for x in d.read()['images'] if x['session']==session)
 PARTS[part]=prompt
 pred=detector.predict(d.image(row['id']),part)
 record={'session':session,'part':part,'prediction':pred,'truth':row['labels'][part],'iou':iou(row['labels'][part]['bbox'],pred['bbox'])}
 results.append(record);print(json.dumps(record),flush=True)
 (root/'docs/visual-prompt-check.json').write_text(json.dumps(results,indent=2))
