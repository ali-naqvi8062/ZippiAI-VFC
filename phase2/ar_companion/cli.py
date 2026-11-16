import argparse
import json
import os
from pathlib import Path
from .store import Store
from .schema import DraftBundle


def main():
    parser=argparse.ArgumentParser(description='PDF to source-linked procedure drafts and embeddings')
    parser.add_argument('--data-dir',default=os.getenv('AR_DATA_DIR','data'))
    parser.add_argument('--model-cache',default=os.getenv('AR_MODEL_CACHE'))
    commands=parser.add_subparsers(dest='command',required=True)
    ingest=commands.add_parser('ingest')
    ingest.add_argument('pdf',type=Path)
    ingest.add_argument('--appliance-id',required=True)
    ingest.add_argument('--provider',choices=['demo','gemini'],default='demo')
    ingest.add_argument('--pages',help='Optional 1-based PDF page ranges, such as 2-7,19-21')
    schema=commands.add_parser('schema'); schema.add_argument('--output',type=Path,required=True)
    export=commands.add_parser('export'); export.add_argument('manual_id'); export.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='schema':
        args.output.write_text(json.dumps(DraftBundle.model_json_schema(),indent=2),encoding='utf-8'); return
    store=Store(args.data_dir,args.model_cache)
    if args.command=='ingest':
        print(json.dumps(store.ingest(args.pdf.read_bytes(),args.appliance_id,args.provider,args.pages),indent=2))
    elif args.command=='export':
        args.output.write_text(json.dumps({'procedures':store.procedures(args.manual_id)},indent=2),encoding='utf-8')


if __name__=='__main__': main()
