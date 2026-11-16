"""Local MiniLM inference with pinned ONNX/tokenizer files; no API key."""
import hashlib
import json
import threading
import urllib.request
from pathlib import Path
import numpy as np

MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'


class Embedder:
    def __init__(self, cache: Path):
        self.cache=cache
        self.lock=threading.Lock()
        self.session=None

    def load(self):
        if self.session is not None:
            return
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.cache.mkdir(parents=True, exist_ok=True)
        checksums={}
        for name in ['tokenizer.json', 'onnx/model.onnx']:
            target=self.cache/Path(name).name
            if not target.exists():
                temp=target.with_suffix('.download')
                with urllib.request.urlopen(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}', timeout=120) as src:
                    with temp.open('wb') as dst:
                        while chunk:=src.read(1024*1024): dst.write(chunk)
                temp.replace(target)
            checksums[target.name]=hashlib.sha256(target.read_bytes()).hexdigest()
        manifest=self.cache/'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text())['sha256'] != checksums:
            raise ValueError('Cached embedding model changed; restore verified model files')
        manifest.write_text(json.dumps({'model':MODEL,'revision':REVISION,'sha256':checksums},indent=2))
        self.tokenizer=Tokenizer.from_file(str(self.cache/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding()
        opts=ort.SessionOptions()
        opts.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(self.cache/'model.onnx'), sess_options=opts, providers=['CPUExecutionProvider'])

    def encode(self, texts):
        with self.lock:
            self.load()
            items=self.tokenizer.encode_batch(texts)
            inputs={'input_ids':np.array([x.ids for x in items],dtype=np.int64),
                    'attention_mask':np.array([x.attention_mask for x in items],dtype=np.int64),
                    'token_type_ids':np.array([x.type_ids for x in items],dtype=np.int64)}
            inputs={x.name:inputs[x.name] for x in self.session.get_inputs()}
            hidden=self.session.run(None,inputs)[0]
            mask=inputs['attention_mask'][...,None]
            pooled=(hidden*mask).sum(1)/np.maximum(mask.sum(1),1)
            return (pooled/np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-12)).tolist()


def retrieval_text(p):
    return ' '.join([p['symptom'], *p['symptom_aliases'], *[c['description'] for c in p['causes']]])
