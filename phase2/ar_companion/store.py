import copy
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .embeddings import Embedder, MODEL, REVISION, retrieval_text
from .ingestion import extract, generate, check_evidence, SAMPLE_HASH
from .schema import Procedure


def now(): return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root, model_cache=None):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'companion.sqlite3'
        self.embedder=Embedder(Path(model_cache) if model_cache else self.root/'models')
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS manuals(id TEXT PRIMARY KEY, appliance TEXT NOT NULL, manifest TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS procedures(manual TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, embedding TEXT NOT NULL, PRIMARY KEY(manual,id));
              CREATE TABLE IF NOT EXISTS releases(manual TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(manual,id,version));
              CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,event TEXT NOT NULL,manual TEXT NOT NULL,procedure TEXT,detail TEXT NOT NULL);
            ''')

    def connect(self):
        c=sqlite3.connect(self.db,timeout=30)
        c.row_factory=sqlite3.Row
        return c

    def ingest(self, content, appliance, provider='demo', page_spec=None):
        import hashlib
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,79}',appliance): raise ValueError('Invalid appliance ID')
        if len(content)>25*1024*1024 or not content.startswith(b'%PDF-'): raise ValueError('Upload a PDF of at most 25 MB')
        digest=hashlib.sha256(content).hexdigest()
        with self.connect() as c:
            existing=c.execute('SELECT manifest,appliance FROM manuals WHERE id=?',(digest,)).fetchone()
            if existing:
                if existing['appliance']!=appliance: raise ValueError('This manual is already assigned to a different appliance')
                return {**json.loads(existing['manifest']),'reused':True}
        folder=self.root/'manuals'/digest
        # Unique staging means interrupted uploads never replace a successful ingestion.
        stage=self.root/'staging'/uuid.uuid4().hex
        stage.mkdir(parents=True)
        (stage/'manual.pdf').write_bytes(content)
        pages=page_spec or ('2-7,19-21' if digest==SAMPLE_HASH else None)
        extraction=extract(stage/'manual.pdf',stage,pages)
        bundle,metadata=generate(extraction,appliance,provider)
        bodies=[p.model_dump() for p in bundle.procedures]
        vectors=self.embedder.encode([retrieval_text(p) for p in bodies])
        manifest={'manual_id':digest,'appliance_id':appliance,'page_count':extraction['page_count'],
                  'extracted_pages':[p['pdf_page'] for p in extraction['pages']],
                  'procedure_count':len(bodies),'created_at':now(),'generation':metadata,
                  'embedding':{'model':MODEL,'revision':REVISION,'dimensions':len(vectors[0])},
                  'warnings':extraction['warnings'],'table_count':sum(len(p['tables']) for p in extraction['pages'])}
        (stage/'generation.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        (stage/'drafts.json').write_text(json.dumps({'procedures':bodies},indent=2),encoding='utf-8')
        (stage/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing=c.execute('SELECT manifest,appliance FROM manuals WHERE id=?',(digest,)).fetchone()
            if existing:
                if existing['appliance']!=appliance: raise ValueError('Concurrent upload used another appliance ID')
                return {**json.loads(existing['manifest']),'reused':True}
            folder.parent.mkdir(exist_ok=True)
            if folder.exists():
                # Preserve an orphan from an interrupted transaction instead of deleting it.
                folder.rename(folder.with_name(digest+'-orphan-'+uuid.uuid4().hex[:8]))
            stage.rename(folder)
            c.execute('INSERT INTO manuals VALUES(?,?,?)',(digest,appliance,json.dumps(manifest)))
            for p,v in zip(bodies,vectors):
                c.execute('INSERT INTO procedures VALUES(?,?,?,?)',(digest,p['procedure_id'],json.dumps(p),json.dumps(v)))
            self.audit(c,'ingest',digest,None,{'procedures':len(bodies),'provider':metadata})
        return manifest

    def audit(self,c,event,manual,procedure,detail):
        c.execute('INSERT INTO audit(at,event,manual,procedure,detail) VALUES(?,?,?,?,?)',
                  (now(),event,manual,procedure,json.dumps(detail)))

    def manuals(self):
        with self.connect() as c: return [json.loads(r[0]) for r in c.execute('SELECT manifest FROM manuals ORDER BY rowid DESC')]

    def procedures(self,manual):
        with self.connect() as c: return [json.loads(r[0]) for r in c.execute('SELECT body FROM procedures WHERE manual=? ORDER BY id',(manual,))]

    def get(self,manual,pid):
        with self.connect() as c: row=c.execute('SELECT body FROM procedures WHERE manual=? AND id=?',(manual,pid)).fetchone()
        if row is None: raise KeyError('Procedure not found')
        return json.loads(row['body'])

    def evidence(self,manual):
        if not re.fullmatch('[a-f0-9]{64}',manual): raise ValueError('Invalid manual ID')
        path=self.root/'manuals'/manual/'extraction.json'
        if not path.exists(): raise KeyError('Manual not found')
        return json.loads(path.read_text(encoding='utf-8'))

    def save(self,manual,pid,data,expected_version):
        old=self.get(manual,pid)
        p=Procedure.model_validate(data)
        if (p.procedure_id,p.manual_version,p.appliance_id)!=(pid,manual,old['appliance_id']):
            raise ValueError('Procedure and manual identity cannot be edited')
        # All approval fields and version numbers are server-owned.
        p.status='draft'; p.reviewer=None; p.reviewed_at=None
        p.procedure_version=expected_version+1
        p=Procedure.model_validate(p.model_dump())
        check_evidence(p,self.evidence(manual))
        body=p.model_dump(); vector=self.embedder.encode([retrieval_text(body)])[0]
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            current=json.loads(c.execute('SELECT body FROM procedures WHERE manual=? AND id=?',(manual,pid)).fetchone()[0])
            if current['procedure_version']!=expected_version: raise ValueError('Version conflict: reload the current draft')
            c.execute('UPDATE procedures SET body=?,embedding=? WHERE manual=? AND id=?',(json.dumps(body),json.dumps(vector),manual,pid))
            self.audit(c,'save_draft',manual,pid,{'version':body['procedure_version'],'previous':current})
        return body

    def publish(self,manual,pid,reviewer,expected_version,attestations):
        required={'source_checked','model_checked','branches_checked','safety_checked','references_checked'}
        if set(k for k,v in attestations.items() if v is True)!=required: raise ValueError('Complete all five review checks')
        if not 2<=len(reviewer.strip())<=100: raise ValueError('Enter a reviewer name')
        p=Procedure.model_validate(self.get(manual,pid))
        check_evidence(p,self.evidence(manual))
        # Defense in depth, not a substitute for semantic review.
        forbidden=r'\b(descal\w*|purge|rewir\w*|energiz\w*|energise\w*|casing|housing|screwdriver)\b|\bplug\s+(it\s+)?in\b|\b(turn|switch|power)\s+(it\s+)?on\b'
        if any(re.search(forbidden,s.instruction,re.I) for s in p.steps[2:]):
            raise ValueError('Instruction exceeds the unpowered external-maintenance scope')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            current=json.loads(c.execute('SELECT body FROM procedures WHERE manual=? AND id=?',(manual,pid)).fetchone()[0])
            if current['procedure_version']!=expected_version: raise ValueError('Version conflict: reload before publishing')
            if current['status']=='published': raise ValueError('This version is already published')
            p.status='published'; p.reviewer=reviewer.strip(); p.reviewed_at=now()
            body=Procedure.model_validate(p.model_dump()).model_dump()
            c.execute('INSERT INTO releases VALUES(?,?,?,?)',(manual,pid,p.procedure_version,json.dumps(body)))
            c.execute('UPDATE procedures SET body=? WHERE manual=? AND id=?',(json.dumps(body),manual,pid))
            self.audit(c,'publish',manual,pid,{'reviewer':reviewer.strip(),'version':p.procedure_version,'checks':attestations})
        return body

    def search(self,manual,query,preview=False):
        if not 3<=len(query.strip())<=1000: raise ValueError('Enter 3-1000 characters')
        with self.connect() as c:
            rows=c.execute('SELECT body,embedding FROM procedures WHERE manual=?',(manual,)).fetchall()
        rows=[r for r in rows if preview or json.loads(r['body'])['status']=='published']
        if not rows: return {'status':'no_match','message':'No published procedure is available. Contact support.','candidates':[]}
        q=np.array(self.embedder.encode([query])[0])
        ranked=[]
        for r in rows:
            p=json.loads(r['body']); score=float(np.dot(q,np.array(json.loads(r['embedding']))))
            ranked.append({'procedure_id':p['procedure_id'],'symptom':p['symptom'],'score':round(score,4),'status':p['status']})
        ranked.sort(key=lambda x:x['score'],reverse=True)
        # Conservative exploratory thresholds, not calibrated probabilities.
        if ranked[0]['score']<0.38:
            status='no_match'; msg='No sufficiently close procedure. Contact support.'
        else:
            status='clarify'; msg='Confirm the symptom and a supported cause before choosing a procedure.'
        return {'status':status,'message':msg,'preview':preview,'candidates':ranked[:3],
                'score_note':'Cosine similarity; not a probability. No repair is automatically selected.'}
