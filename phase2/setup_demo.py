"""Prepare the verified sample without requiring PowerShell activation."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
EXPECTED = 'f0a5e4024b1c57996b4a4771dc7ae9b5f29ff931fa915ec4b40569761dd8012f'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',action='store_true',help='Restore included evidence and draft snapshots without downloading the PDF')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    args=parser.parse_args()
    if args.snapshot:
        from ar_companion.store import Store
        from ar_companion.schema import DraftBundle
        from ar_companion.embeddings import retrieval_text
        store=Store(args.data_dir,os.environ.get('AR_MODEL_CACHE'))
        if store.manuals():
            print('Existing data preserved. Start Run-Demo.cmd.');return
        sample=ROOT/'sample'
        manifest=json.loads((sample/'extracted/manifest.json').read_text(encoding='utf-8'))
        bodies=[p.model_dump() for p in DraftBundle.model_validate_json((sample/'drafts.json').read_text(encoding='utf-8')).procedures]
        vectors=store.embedder.encode([retrieval_text(p) for p in bodies])
        folder=store.root/'manuals'/EXPECTED
        shutil.copytree(sample/'extracted',folder,dirs_exist_ok=True)
        manifest['setup_mode']='restored_bundled_snapshot_not_fresh_pdf_extraction'
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        with store.connect() as c:
            c.execute('INSERT INTO manuals VALUES(?,?,?)',(EXPECTED,'breville-bes500',json.dumps(manifest)))
            for body,vector in zip(bodies,vectors):
                c.execute('INSERT INTO procedures VALUES(?,?,?,?)',(EXPECTED,body['procedure_id'],json.dumps(body),json.dumps(vector)))
            store.audit(c,'restore_demo_snapshot',EXPECTED,None,{'fresh_extraction':False})
        print('Restored included evidence and drafts (not a fresh PDF extraction). Run Run-Demo.cmd.');return
    if not shutil.which('pdftoppm'):
        bundled = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'
        if (bundled/'pdftoppm.exe').exists():
            os.environ['PATH'] = str(bundled)+os.pathsep+os.environ.get('PATH','')
        else:
            raise SystemExit('Install Poppler and add its executable directory to PATH, then rerun this command.')
    manual = args.data_dir.resolve()/'input/BES500_USCM_IB_T23_LR.pdf'
    manual.parent.mkdir(parents=True, exist_ok=True)
    if not manual.exists():
        print('Downloading the official Breville manual...', flush=True)
        try:
            content = urllib.request.urlopen('https://assets.breville.com/BES500/BES500_USCM_IB_T23_LR.pdf',timeout=60).read()
        except Exception as exc:
            raise SystemExit(f'Manual download failed ({type(exc).__name__}). Use setup_demo.py --snapshot for the bundled demo, or save the verified manual at {manual}.') from None
        if hashlib.sha256(content).hexdigest()!=EXPECTED:
            raise SystemExit('Official download differs from the verified demo manual; download was not saved.')
        manual.write_bytes(content)
    if hashlib.sha256(manual.read_bytes()).hexdigest()!=EXPECTED:
        raise SystemExit('Existing manual differs from the verified demo manual; left untouched.')
    subprocess.run([sys.executable,'-m','ar_companion.cli','--data-dir',str(args.data_dir.resolve()),'ingest',str(manual),'--appliance-id','breville-bes500'],cwd=ROOT,check=True)
    print('Ready. Run Run-Demo.cmd and open http://127.0.0.1:8765')

if __name__=='__main__':
    main()
