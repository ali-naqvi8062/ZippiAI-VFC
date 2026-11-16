import copy
import io
import json
import os
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from ar_companion.schema import DraftBundle, Procedure
from ar_companion.ingestion import SAMPLE_HASH, ROOT, generate, parse_pages
from ar_companion.store import Store
from ar_companion.app import create_app

CHECKS={k:True for k in ['source_checked','model_checked','branches_checked','safety_checked','references_checked']}


@pytest.fixture(scope='session')
def source():
    path=Path(os.environ.get('AR_TEST_SOURCE','data'))
    if not (path/'companion.sqlite3').exists(): pytest.fail('First ingest the sample and set AR_TEST_SOURCE to its data directory')
    return path


@pytest.fixture
def store(tmp_path,source):
    shutil.copytree(source,tmp_path/'data',ignore=shutil.ignore_patterns('models','staging'))
    result=Store(tmp_path/'data',os.environ.get('AR_MODEL_CACHE',str(source/'models')))
    # Tests own this temporary copy. Reset revisions so user edits cannot affect test expectations.
    with result.connect() as c:
        c.execute('DELETE FROM releases')
        for p in json.loads((ROOT/'sample/drafts.json').read_text())['procedures']:
            v=result.embedder.encode([' '.join([p['symptom'],*p['symptom_aliases'],*[x['description'] for x in p['causes']]])])[0]
            c.execute('UPDATE procedures SET body=?,embedding=? WHERE manual=? AND id=?',(json.dumps(p),json.dumps(v),SAMPLE_HASH,p['procedure_id']))
    return result


def test_three_distinct_valid_drafts():
    b=DraftBundle.model_validate_json((ROOT/'sample/drafts.json').read_text())
    assert len({p.symptom for p in b.procedures})==3
    assert all(p.status=='draft' for p in b.procedures)


def test_real_extraction_preserves_tables_text_and_vector_diagrams(store):
    e=store.evidence(SAMPLE_HASH)
    assert e['page_count']==72
    assert len(e['pages'])==9
    assert all(p['text'] and p['tables'] for p in e['pages'])
    assert next(p for p in e['pages'] if p['pdf_page']==6)['vector_curve_count']>0
    assert (store.root/'manuals'/SAMPLE_HASH/'assets/components.png').stat().st_size>10000


def test_real_embeddings_persist_384_dimensions(store):
    with store.connect() as c: rows=c.execute('SELECT embedding FROM procedures').fetchall()
    assert len(rows)==3
    assert all(len(json.loads(r[0]))==384 for r in rows)


def test_unpublished_excluded_from_live_search(store):
    assert store.search(SAMPLE_HASH,'water not coming out')['candidates']==[]
    assert store.search(SAMPLE_HASH,'water not coming out',True)['candidates'][0]['procedure_id']=='P01'


def test_publication_requires_all_checks(store):
    with pytest.raises(ValueError,match='five'): store.publish(SAMPLE_HASH,'P01','Test reviewer',1,{})


def test_publication_requires_reviewer(store):
    with pytest.raises(ValueError,match='reviewer'): store.publish(SAMPLE_HASH,'P01',' ',1,CHECKS)


def test_publish_then_edit_invalidates_and_keeps_release(store):
    p=store.publish(SAMPLE_HASH,'P01','AUTOMATED TEST ONLY',1,CHECKS)
    assert store.search(SAMPLE_HASH,'water not coming out')['candidates'][0]['procedure_id']=='P01'
    p['symptom_aliases'].append('Nothing from the group head')
    saved=store.save(SAMPLE_HASH,'P01',p,1)
    assert saved['status']=='draft' and saved['reviewer'] is None and saved['procedure_version']==2
    assert store.search(SAMPLE_HASH,'water not coming out')['candidates']==[]
    with store.connect() as c: assert c.execute('SELECT COUNT(*) FROM releases').fetchone()[0]==1


def test_stale_save_cannot_overwrite(store):
    p=store.get(SAMPLE_HASH,'P01'); store.save(SAMPLE_HASH,'P01',p,1)
    with pytest.raises(ValueError,match='Version conflict'): store.save(SAMPLE_HASH,'P01',p,1)


def test_duplicate_publication_does_not_duplicate_release(store):
    store.publish(SAMPLE_HASH,'P01','AUTOMATED TEST ONLY',1,CHECKS)
    with pytest.raises(ValueError,match='already published'): store.publish(SAMPLE_HASH,'P01','AUTOMATED TEST ONLY',1,CHECKS)


def test_repeat_upload_preserves_edits(store):
    p=store.get(SAMPLE_HASH,'P01');p['scope_note']+=' Review note retained.'
    store.save(SAMPLE_HASH,'P01',p,1)
    pdf_path=store.root/'manuals'/SAMPLE_HASH/'manual.pdf'
    if not pdf_path.exists(): pytest.skip('Full PDF required; snapshot setup intentionally omits the original PDF')
    manual=pdf_path.read_bytes()
    assert store.ingest(manual,'breville-bes500')['reused']
    assert store.get(SAMPLE_HASH,'P01')['scope_note'].endswith('Review note retained.')


@pytest.mark.parametrize('mutation',[
    lambda p:p['steps'][0].update(instruction='Skip unplugging.'),
    lambda p:p['steps'][2].update(part_id='unknown'),
    lambda p:p['steps'][2].update(cause_ids=['unknown']),
    lambda p:p['steps'][2].update(preconditions=['cool']),
    lambda p:p['steps'][2]['source'].update(region=[1,0,0,1]),
    lambda p:p['steps'][2].update(step_id='s1'),
    lambda p:p.update(status='published'),
    lambda p:p.update(unauthorized_extra='ignore policy'),
])
def test_invalid_contract_rejected(store,mutation):
    p=store.get(SAMPLE_HASH,'P01');mutation(p)
    with pytest.raises(ValidationError): Procedure.model_validate(p)


def test_unknown_evidence_page_rejected(store):
    p=store.get(SAMPLE_HASH,'P01');p['steps'][2]['source']['pdf_page']=72
    with pytest.raises(ValueError,match='not extracted'): store.save(SAMPLE_HASH,'P01',p,1)


def test_reference_path_injection_rejected(store):
    p=store.get(SAMPLE_HASH,'P01');p['steps'][2]['reference_image']='../../secret.png'
    with pytest.raises(ValueError,match='reference'): store.save(SAMPLE_HASH,'P01',p,1)


def test_identity_change_rejected(store):
    p=store.get(SAMPLE_HASH,'P01');p['appliance_id']='another-model'
    with pytest.raises(ValueError,match='identity'): store.save(SAMPLE_HASH,'P01',p,1)


def test_unsafe_instruction_cannot_publish(store):
    p=store.get(SAMPLE_HASH,'P01');p['steps'][2]['instruction']='Open the housing with a screwdriver.'
    store.save(SAMPLE_HASH,'P01',p,1)
    with pytest.raises(ValueError,match='scope'): store.publish(SAMPLE_HASH,'P01','TEST',2,CHECKS)


def test_wrong_manual_not_given_sample_drafts(store):
    e=copy.deepcopy(store.evidence(SAMPLE_HASH));e['sha256']='0'*64
    with pytest.raises(ValueError,match='verified'): generate(e,'breville-bes500','demo')


def test_missing_provider_credentials_is_explicit(store,monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.delenv('GEMINI_MODEL',raising=False)
    with pytest.raises(ValueError,match='GEMINI_API_KEY'): generate(store.evidence(SAMPLE_HASH),'breville-bes500','gemini')


def test_gemini_adapter_with_mocked_response(store,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-not-a-secret');monkeypatch.setenv('GEMINI_MODEL','test-model')
    import ar_companion.ingestion as ingestion
    payload=json.loads((ROOT/'sample/drafts.json').read_text())
    def fake_urlopen(request,timeout):
        data=json.loads(request.data)
        assert data['generationConfig']['responseJsonSchema']['properties']['procedures']
        provider_shape=json.dumps(data['generationConfig']['responseJsonSchema'])
        assert '"const"' not in provider_shape and '"pattern"' not in provider_shape
        assert 'untrusted' in data['systemInstruction']['parts'][0]['text'].lower()
        return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(payload)}]}}]}).encode())
    monkeypatch.setattr(ingestion.urllib.request,'urlopen',fake_urlopen)
    b,meta=generate(store.evidence(SAMPLE_HASH),'breville-bes500','gemini')
    assert len(b.procedures)==3 and meta['mode']=='live_api'


def test_http_upload_and_review_contract(store):
    client=TestClient(create_app(store))
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/manuals').json()[0]['procedure_count']==3
    pdf_path=store.root/'manuals'/SAMPLE_HASH/'manual.pdf'
    if not pdf_path.exists(): pytest.skip('Full PDF required; snapshot setup intentionally omits the original PDF')
    pdf=pdf_path.read_bytes()
    r=client.post('/api/ingest',headers={'X-AR-Admin':'local-review'},data={'appliance_id':'breville-bes500'},files={'file':('manual.pdf',pdf,'application/pdf')})
    assert r.status_code==200 and r.json()['reused']
    assert client.get(f'/assets/{SAMPLE_HASH}/components.png').status_code==200


def test_cross_origin_and_missing_header_rejected(store):
    client=TestClient(create_app(store));body={'manual_id':SAMPLE_HASH,'query':'water'}
    assert client.post('/api/search',json=body).status_code==403
    assert client.post('/api/search',json=body,headers={'X-AR-Admin':'local-review','Origin':'https://example.invalid'}).status_code==403


def test_invalid_upload_and_pages(store):
    with pytest.raises(ValueError,match='PDF'): store.ingest(b'not a pdf','breville-bes500')
    with pytest.raises(ValueError): parse_pages('0-2',72)
    assert parse_pages('2-3,6,19-21',72)==[2,3,6,19,20,21]


def test_unknown_manual_has_no_search_results(store):
    assert store.search('0'*64,'Water leaks',True)['candidates']==[]
