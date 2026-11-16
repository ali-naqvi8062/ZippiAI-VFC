import io
import pytest
from PIL import Image
from vision.core import Dataset,Label,PARTS,iou,evaluate

def picture(color=1):
 b=io.BytesIO();Image.new('RGB',(50,30),(color,0,0)).save(b,format='PNG');return b.getvalue()
def add(d,color=1,session='dev-session',split='dev',kind='real_photo'):
 return d.add(picture(color),session,split,kind,'indoor','front')

def test_iou():
 assert iou([0,0,1,1],[0,0,1,1])==1
 assert iou([0,0,.5,.5],[.5,.5,1,1])==0
 assert iou([0,0,1,1],[0,0,.5,.5])==.25
 assert iou(None,[0,0,1,1])==0
@pytest.mark.parametrize('value',[{'visibility':'visible','bbox':None},{'visibility':'visible','bbox':[1,0,0,1]},{'visibility':'visible','bbox':[0,0,2,1]},{'visibility':'absent','bbox':[0,0,1,1]},{'visibility':'visible','bbox':[0,0,float('nan'),1]}])
def test_invalid_boxes(value):
 with pytest.raises(ValueError):Label.model_validate(value)
def test_duplicate_and_session_leakage(tmp_path):
 d=Dataset(tmp_path);add(d)
 with pytest.raises(ValueError,match='Duplicate'):add(d,session='other',split='test')
 with pytest.raises(ValueError,match='session'):add(d,2,split='test')
def test_no_empty_benchmark(tmp_path):
 d=Dataset(tmp_path)
 with pytest.raises(ValueError,match='50'):d.freeze()
def test_labels_and_traversal(tmp_path):
 d=Dataset(tmp_path);a=add(d)
 with pytest.raises(ValueError):d.label(a['id'],'invented',{'visibility':'absent'})
 with pytest.raises(ValueError):d.image('../../secret')
 d.label(a['id'],'water_tank',{'visibility':'absent'})
 assert d.read()['images'][0]['labels']['water_tank']['bbox'] is None
class Fake:
 def predict(self,path,part):return {'bbox':[0,0,.5,.5], 'inference_seconds':1.0}
def test_metrics_include_failures_and_negatives(tmp_path):
 d=Dataset(tmp_path);a=add(d)
 for part,value in [('water_tank',{'visibility':'visible','bbox':[0,0,.5,.5]}),('drip_tray',{'visibility':'absent'}),('steam_wand',{'visibility':'ambiguous'})]:d.label(a['id'],part,value)
 r=evaluate(d,Fake(),'dev')
 assert r['summary']['correct_iou50']==1 and r['summary']['false_positive_count']==1
 assert r['ambiguous_pairs_excluded']==1 and len(r['records'])==2
 assert r['latency_seconds']['p95']==1
 with pytest.raises(ValueError,match='Freeze'):evaluate(d,Fake(),'test')
def test_frozen_dataset(tmp_path):
 # Synthetic colored fixtures test bookkeeping ONLY; never reported as real evaluation.
 d=Dataset(tmp_path)
 for n in range(50):
  row=add(d,n,session='test-session',split='test')
  for part in PARTS:d.label(row['id'],part,{'visibility':'visible','bbox':[0,0,.5,.5]} if n<5 else {'visibility':'absent'})
 frozen=d.freeze();assert len(frozen['benchmark_sha256'])==64
 with pytest.raises(ValueError,match='Frozen'):d.label(row['id'],'water_tank',{'visibility':'absent'})
 with pytest.raises(ValueError,match='frozen'):add(d,99,session='test-session',split='test')
 add(d,98,session='new-dev')
def test_diagrams_do_not_qualify(tmp_path):
 d=Dataset(tmp_path);add(d,kind='diagram',split='test',session='test')
 with pytest.raises(ValueError,match='real'):d.freeze()

def test_small_pilot_freeze_and_honest_claim(tmp_path):
 d=Dataset(tmp_path)
 d.write({'images':[],'frozen':False,'evaluation_protocol':'small-public-photo-pilot','required_parts':['steam_wand']})
 for n in range(3):
  row=add(d,n,session='pilot',split='test')
  d.label(row['id'],'steam_wand',{'visibility':'visible','bbox':[0,0,.5,.5]})
 d.freeze()
 report=evaluate(d,Fake(),'test')
 assert report['summary']['visible_pairs']==3
 assert 'Small public-photo pilot' in report['claim']
 assert report['summary']['absent_pairs']==0
