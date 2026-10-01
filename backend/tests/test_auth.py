import json
import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app,auth
from backend.auth import password_record,COOKIE

@pytest.fixture
def client(tmp_path,monkeypatch):
    config=tmp_path/'auth.json';config.write_text(json.dumps(password_record('test-staff-password')))
    monkeypatch.setattr(auth,'config',config)
    auth.sessions.clear();auth.attempts.clear()
    return TestClient(app,follow_redirects=False)

def login(client):return client.post('/login',data={'password':'test-staff-password'})

@pytest.mark.parametrize('path',['/','/main.js','/styles.css','/agreements/letter%20of%20offer%20to%20rent.pdf','/.local/auth.json','/openapi.json'])
def test_signed_out_files_blocked(client,path):
    r=client.get(path);assert r.status_code==303 and r.headers['location']=='/login'
    assert r.headers['cache-control']=='no-store'

def test_signed_out_api_blocked(client):
    for path in ['/api/defaults','/api/health']:
        assert client.get(path).status_code==401
    assert client.post('/api/generate',json={}).status_code==401

def test_login_cookie_and_logout(client):
    r=login(client);assert r.status_code==303
    cookie=r.headers['set-cookie'];assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age=28800' in cookie
    token=client.cookies.get(COOKIE)
    assert client.get('/api/defaults').status_code==200
    assert client.post('/logout').status_code==303
    client.cookies.set(COOKIE,token)
    assert client.get('/api/defaults').status_code==401

def test_wrong_password_rate_limit(client):
    for _ in range(5):assert client.post('/login',data={'password':'wrong'}).status_code==401
    r=login(client);assert r.status_code==429 and int(r.headers['retry-after'])>0

def test_expired_and_forged_sessions(client):
    login(client)
    for k in auth.sessions:auth.sessions[k]=time.time()-1
    assert client.get('/api/defaults').status_code==401
    client.cookies.set(COOKIE,'invented-session')
    assert client.get('/api/defaults').status_code==401

def test_password_change_revokes_sessions(client):
    login(client)
    auth.config.write_text(json.dumps(password_record('new-staff-password')))
    assert client.get('/api/defaults').status_code==401
    assert login(client).status_code==401

def test_missing_config_fails_closed(client):
    auth.config.unlink()
    assert client.get('/').status_code==503
    assert client.post('/api/generate',json={}).status_code==503

def test_cross_site_requests_blocked(client):
    assert client.post('/login',data={'password':'test-staff-password'},headers={'origin':'https://another-site.test'}).status_code==403
    login(client)
    assert client.post('/api/generate',json={},headers={'origin':'https://another-site.test'}).status_code==403
    assert client.post('/logout',headers={'sec-fetch-site':'cross-site'}).status_code==403
    assert client.get('/api/defaults').status_code==200

def test_https_cookie(client):
    with TestClient(app,base_url='https://testserver',follow_redirects=False) as https:
        r=login(https);assert 'Secure' in [part.strip() for part in r.headers['set-cookie'].split(';')]

def test_private_files_not_served_after_login(client):
    login(client)
    assert client.get('/.local/auth.json').status_code==404
    assert client.get('/openapi.json').status_code==404



def test_browser_form_origin_policy(client):
    response=client.get('/login')
    assert response.status_code==200
    assert response.headers['referrer-policy']=='strict-origin-when-cross-origin'
    headers={'origin':'http://testserver','sec-fetch-site':'same-origin'}
    response=client.post('/login',data={'password':'test-staff-password'},headers=headers)
    assert response.status_code==303
    assert client.get('/api/defaults').status_code==200
    assert client.post('/logout',headers=headers).status_code==303


def test_null_origin_remains_blocked(client):
    response=client.post('/login',data={'password':'test-staff-password'},headers={'origin':'null','sec-fetch-site':'same-origin'})
    assert response.status_code==403
