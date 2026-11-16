import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ValidationError
from .store import Store

ROOT=Path(__file__).resolve().parents[1]


class Edit(BaseModel):
    expected_version: int = Field(ge=1)
    procedure: dict


class Review(BaseModel):
    expected_version: int = Field(ge=1)
    reviewer: str
    attestations: dict[str,bool]


class Search(BaseModel):
    manual_id: str
    query: str
    preview: bool = False


def create_app(store=None):
    app=FastAPI(title='AR Companion - Phase 2',version='1.0.0')
    app.state.store=store or Store(os.getenv('AR_DATA_DIR',str(ROOT/'data')),os.getenv('AR_MODEL_CACHE'))
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        if request.method not in ['GET','HEAD','OPTIONS']:
            origin=request.headers.get('origin')
            if origin and origin!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Cross-origin mutations are disabled'},status_code=403)
            if request.headers.get('x-ar-admin')!='local-review':
                return JSONResponse({'detail':'Missing local admin request header'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request,exc): return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request,exc): return JSONResponse({'detail':str(exc)},status_code=404)

    @app.get('/')
    def index(): return FileResponse(ROOT/'static/index.html')

    @app.get('/api/manuals')
    def manuals(): return app.state.store.manuals()

    @app.post('/api/ingest')
    def ingest(file:UploadFile=File(...),appliance_id:str=Form(...),provider:str=Form('demo'),pages:str=Form('')):
        content=file.file.read(25*1024*1024+1)
        try: return app.state.store.ingest(content,appliance_id,provider,pages or None)
        except (ValueError,KeyError): raise
        except Exception as e:
            # Avoid sending credential-bearing provider exceptions to the browser.
            raise HTTPException(502,'Ingestion failed ('+type(e).__name__+'). Check dependencies, selected pages, and provider configuration.') from e

    @app.get('/api/manuals/{manual}/procedures')
    def procedures(manual:str): return app.state.store.procedures(manual)

    @app.get('/api/manuals/{manual}/evidence')
    def evidence(manual:str): return app.state.store.evidence(manual)

    @app.put('/api/manuals/{manual}/procedures/{pid}')
    def save(manual:str,pid:str,body:Edit): return app.state.store.save(manual,pid,body.procedure,body.expected_version)

    @app.post('/api/manuals/{manual}/procedures/{pid}/publish')
    def publish(manual:str,pid:str,body:Review):
        return app.state.store.publish(manual,pid,body.reviewer,body.expected_version,body.attestations)

    @app.post('/api/search')
    def search(body:Search): return app.state.store.search(body.manual_id,body.query,body.preview)

    @app.get('/api/manuals/{manual}/export')
    def export(manual:str):
        return JSONResponse({'procedures':app.state.store.procedures(manual)},headers={'Content-Disposition':'attachment; filename="procedures.json"'})

    @app.get('/assets/{manual}/{name}')
    def asset(manual:str,name:str):
        app.state.store.evidence(manual)
        if Path(name).name!=name or not name.endswith('.png'): raise HTTPException(404)
        target=app.state.store.root/'manuals'/manual/'assets'/name
        if not target.is_file(): raise HTTPException(404)
        return FileResponse(target)

    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    return app


app=create_app()
