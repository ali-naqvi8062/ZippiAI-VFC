import argparse
import json
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ar_companion.store import Store
from ar_companion.ingestion import SAMPLE_HASH,ROOT


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--model-cache',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();store=Store(a.data_dir,a.model_cache)
    q=json.loads((ROOT/'sample/retrieval_queries.json').read_text())
    rows=[]
    for query,expected in q['positive']:
        start=time.perf_counter();r=store.search(SAMPLE_HASH,query,True)
        rows.append({'query':query,'expected':expected,'top_candidate':r['candidates'][0]['procedure_id'],'correct_top1':r['candidates'][0]['procedure_id']==expected,'milliseconds':round((time.perf_counter()-start)*1000,2),'result':r})
    unsupported=[{'query':query,'result':store.search(SAMPLE_HASH,query,True)} for query in q['unsupported']]
    report={'protocol':q['protocol'],'positive_top1_correct':sum(r['correct_top1'] for r in rows),'positive_count':len(rows),'positive':rows,'unsupported':unsupported,'unsupported_no_match_count':sum(r['result']['status']=='no_match' for r in unsupported),'automatic_procedure_selection':False,'live_search_before_review':store.search(SAMPLE_HASH,'No water comes out',False)}
    Path(a.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['positive','unsupported']},indent=2))


if __name__=='__main__': main()
