import os
import json
from pathlib import Path
from PIL import Image,ImageDraw
from vision.core import Dataset,Detector,evaluate
ROOT=Path(__file__).resolve().parent
def main():
 data=Dataset(ROOT/'data-dedica')
 cache=Path(os.environ.get('VISION_MODELS',str(ROOT/'models')))
 report=evaluate(data,Detector(cache),'dev')
 (ROOT/'docs/pilot-results.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2),flush=True)
 records=report['records'];sheet=Image.new('RGB',(1200,((len(records)+2)//3)*340),'white');draw=ImageDraw.Draw(sheet)
 for i,r in enumerate(records):
  im=Image.open(data.image(r['image_id'])).convert('RGB');im.thumbnail((390,290));g=ImageDraw.Draw(im)
  for box,color in [(r['truth']['bbox'],'green'),(r['prediction']['bbox'],'orange')]:
   if box:g.rectangle([box[0]*im.width,box[1]*im.height,box[2]*im.width,box[3]*im.height],outline=color,width=3)
  x=(i%3)*400;y=(i//3)*340;sheet.paste(im,(x,y+40));draw.text((x+4,y+4),r['part_id']+' IoU '+str(round(r['iou'],2)),fill='black')
 sheet.save(ROOT/'docs/pilot-predictions.jpg')
if __name__=='__main__':main()
