import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app,auth
from backend.auth import password_record
from backend import addresses

@pytest.fixture
def client(tmp_path,monkeypatch):
    config=tmp_path/'auth.json';config.write_text(json.dumps(password_record('test-address-password')))
    monkeypatch.setattr(auth,'config',config)
    monkeypatch.setattr(addresses,'FILE',tmp_path/'addresses.json')
    auth.sessions.clear();auth.attempts.clear()
    c=TestClient(app,follow_redirects=False)
    assert c.post('/login',data={'password':'test-address-password'}).status_code==303
    return c

def test_address_options_persist_and_deduplicate(client):
    assert client.get('/api/addresses').json()=={'addresses':[]}
    r=client.post('/api/addresses',json={'address':'  Example Residence, Johor  '})
    assert r.status_code==200
    assert r.json()['selected']=='Example Residence, Johor'
    assert json.loads(addresses.FILE.read_text())==['Example Residence, Johor']
    assert client.post('/api/addresses',json={'address':'example residence, johor'}).json()['addresses']==['Example Residence, Johor']
    assert client.get('/api/addresses').json()['addresses']==['Example Residence, Johor']

def test_address_validation_and_auth(client):
    for value in ['', ' '*4, 'x'*601]:assert client.post('/api/addresses',json={'address':value}).status_code==422
    client.post('/logout')
    assert client.get('/api/addresses').status_code==401
    assert client.post('/api/addresses',json={'address':'private'}).status_code==401
