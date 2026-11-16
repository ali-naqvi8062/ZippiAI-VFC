import os
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from .core import Dataset,Detector,PARTS,evaluate
ROOT=Path(__file__).resolve().parents[1]
data=Dataset(os.environ.get('VISION_DATA',str(ROOT/'data-dedica')))
detector=Detector(os.environ.get('VISION_MODELS',str(ROOT/'models')))
app=FastAPI(title='AR Companion Phase 3 - Vision Lab')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])
@app.middleware('http')
async def guard(request:Request,call_next):
 if request.method not in ['GET','HEAD']:
  if request.headers.get('x-vision-admin')!='local' or request.headers.get('origin',str(request.base_url).rstrip('/'))!=str(request.base_url).rstrip('/'):
   return JSONResponse({'detail':'Local admin request required'},403)
 return await call_next(request)
@app.exception_handler(ValueError)
async def error(request,exc):return JSONResponse({'detail':str(exc)},422)
@app.get('/')
def home():return FileResponse(ROOT/'static/index.html')
@app.get('/api/data')
def listing():return {'dataset':data.read(),'parts':PARTS}
@app.post('/api/images')
def upload(file:UploadFile=File(...),session:str=Form(...),split:str=Form(...),kind:str=Form(...),lighting:str=Form(...),angle:str=Form(...)):
 return data.add(file.file.read(20*1024*1024+1),session,split,kind,lighting,angle)
class Annotation(BaseModel):
 part_id:str
 label:dict
@app.put('/api/images/{ident}/label')
def label(ident:str,body:Annotation):return data.label(ident,body.part_id,body.label)
@app.get('/images/{ident}')
def picture(ident:str):return FileResponse(data.image(ident))
@app.post('/api/images/{ident}/predict/{part}')
def predict(ident:str,part:str):
 # Test photos are reserved for batch evaluation to discourage threshold tuning on them.
 row=next((r for r in data.read()['images'] if r['id']==ident),None)
 if row and row['split']=='test':raise ValueError('Use dev images for interactive inference; test images are evaluated after freezing')
 return detector.predict(data.image(ident),part)
@app.post('/api/freeze')
def freeze():return data.freeze()
@app.post('/api/evaluate/{split}')
def score(split:str):return evaluate(data,detector,split)
@app.get('/api/export')
def export():return JSONResponse(data.read(),headers={'Content-Disposition':'attachment; filename=annotations.json'})
@app.get('/api/pilot-results')
def pilot_results():
 path=ROOT/'docs/pilot-results.json'
 if not path.exists():raise ValueError('Pilot evaluation has not finished')
 return FileResponse(path)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
