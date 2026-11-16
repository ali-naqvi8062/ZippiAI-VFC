from fastapi.testclient import TestClient
from vision.app import app

def test_preloaded_pilot_and_report():
 with TestClient(app) as client:
  response=client.get('/api/data')
  assert response.status_code==200
  data=response.json()['dataset']
  assert data['appliance_id']=='delonghi-dedica-family-pilot'
  assert len(data['images'])==5
  for row in data['images']:
   assert client.get('/images/'+row['id']).status_code==200
  assert client.get('/api/pilot-results').status_code==200
  assert client.post('/api/freeze').status_code==403
  assert client.post('/api/freeze',headers={'X-Vision-Admin':'local'}).status_code==422
