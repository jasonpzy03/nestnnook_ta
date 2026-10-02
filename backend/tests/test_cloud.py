import json
from concurrent.futures import ThreadPoolExecutor
import fakeredis
import pytest
from fastapi.testclient import TestClient
from backend.main import app,auth
from backend.auth import COOKIE,TTL,password_record
from backend.cloud_store import RedisStore,StorageError

@pytest.fixture
def cloud(monkeypatch):
    redis=fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setenv('VERCEL','1')
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL','https://test.upstash.io')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN','test-token')
    monkeypatch.setenv('NEST_REDIS_PREFIX','test:production')
    monkeypatch.setenv('NEST_STAFF_PASSWORD_RECORD',json.dumps(password_record('test-cloud-password')))
    monkeypatch.setattr(RedisStore,'command',lambda self,*args:redis.execute_command(*args))
    with TestClient(app,base_url='https://testserver',follow_redirects=False) as client:
        yield client,redis


def sign_in(client):
    response=client.post('/login',data={'password':'test-cloud-password'},headers={'origin':'https://testserver','x-forwarded-for':'192.0.2.10'})
    assert response.status_code==303,response.text
    return client.cookies.get(COOKIE)


def test_shared_sessions_logout_and_ttl(cloud):
    client,redis=cloud
    token=sign_in(client);store=RedisStore()
    assert 0<redis.ttl(store.key('session',token))<=TTL
    auth.sessions.clear()
    assert store.valid(token,auth.record()['digest'])
    with TestClient(app,base_url='https://testserver',follow_redirects=False) as second:
        second.cookies.set(COOKIE,token)
        assert second.get('/api/defaults').status_code==200
        assert second.post('/logout').status_code==303
    assert client.get('/api/defaults').status_code==401


def test_expiry_and_password_rotation(cloud,monkeypatch):
    client,redis=cloud
    token=sign_in(client)
    redis.expire(RedisStore().key('session',token),-1)
    assert client.get('/api/defaults').status_code==401
    sign_in(client)
    monkeypatch.setenv('NEST_STAFF_PASSWORD_RECORD',json.dumps(password_record('changed-cloud-password')))
    assert client.get('/api/defaults').status_code==401


def test_atomic_rate_limit_and_expiry(cloud):
    client,redis=cloud
    with ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(lambda _:RedisStore().reserve_attempt('same-ip'),range(20)))
    assert sum(result[0] for result in results)==5
    key=RedisStore().key('attempt','same-ip')
    assert 0<redis.ttl(key)<=900
    redis.expire(key,-1)
    assert RedisStore().reserve_attempt('same-ip')[0]==1
    for _ in range(5):
        assert client.post('/login',data={'password':'wrong'}).status_code==401
    assert client.post('/login',data={'password':'test-cloud-password'}).status_code==429


def test_addresses_shared_deduplicated_and_no_expiry(cloud):
    client,redis=cloud;sign_in(client)
    assert client.post('/api/addresses',json={'address':'Example Residence'}).status_code==200
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda _:RedisStore().add_address('example residence'),range(20)))
    assert RedisStore().addresses()==['Example Residence']
    assert redis.ttl(RedisStore().key('addresses'))==-1
    auth.sessions.clear()
    assert client.get('/api/addresses').json()=={'addresses':['Example Residence']}
    for n in range(499):RedisStore().add_address(f'Unit {n}')
    assert client.post('/api/addresses',json={'address':'Overflow'}).status_code==422
    assert client.post('/api/addresses',json={'address':'Example Residence'}).status_code==200


def test_cloud_config_and_outage_fail_closed(cloud,monkeypatch):
    client,_=cloud;sign_in(client)
    def unavailable(*args):raise StorageError('test outage')
    monkeypatch.setattr(RedisStore,'command',unavailable)
    assert client.get('/api/defaults').status_code==503
    assert client.get('/main.js').status_code==503
    monkeypatch.delenv('UPSTASH_REDIS_REST_TOKEN')
    assert client.get('/login').status_code==503


def test_cloud_requires_env_password_and_protects_assets(cloud,monkeypatch):
    client,_=cloud
    assert client.get('/').status_code==303
    assert client.get('/main.js').status_code==303
    sign_in(client)
    assert client.get('/').status_code==200
    assert client.get('/main.js').status_code==200
    assert client.get('/agreements/2.%20House%20Rules.docx').status_code==404
    assert client.get('/.local/auth.json').status_code==404
    monkeypatch.delenv('NEST_STAFF_PASSWORD_RECORD')
    assert client.get('/').status_code==503


def test_preview_namespace_is_separate(cloud,monkeypatch):
    client,_=cloud;token=sign_in(client)
    RedisStore().add_address('Production address')
    monkeypatch.setenv('NEST_REDIS_PREFIX','test:preview')
    assert not RedisStore().valid(token,auth.record()['digest'])
    assert RedisStore().addresses()==[]


def test_http_errors_hide_credentials(monkeypatch):
    from backend import cloud_store
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL','https://test.upstash.io')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN','secret-value')
    class Broken:
        def open(self,*args,**kwargs):raise OSError('secret-value')
    monkeypatch.setattr(cloud_store,'build_opener',lambda *_:Broken())
    with pytest.raises(StorageError,match='temporarily unavailable') as error:RedisStore().command('GET','test')
    assert 'secret-value' not in str(error.value)

@pytest.mark.parametrize('status,code',[(401,'redis_auth_failed'),(403,'redis_access_denied'),(429,'redis_rate_limited'),(500,'redis_http_error')])
def test_safe_http_diagnostics(monkeypatch,status,code):
    from backend import cloud_store
    from urllib.error import HTTPError
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL','https://test.upstash.io')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN','secret-value')
    class Broken:
        def open(self,*args,**kwargs):raise HTTPError('https://test.upstash.io',status,'secret-value',{},None)
    monkeypatch.setattr(cloud_store,'build_opener',lambda *_:Broken())
    with pytest.raises(StorageError) as error:RedisStore().command('GET','private-key')
    assert error.value.code==code
    assert 'secret-value' not in str(error.value)


def test_missing_credentials_logged_safely(cloud,monkeypatch,caplog):
    client,_=cloud
    monkeypatch.delenv('UPSTASH_REDIS_REST_TOKEN')
    response=client.get('/login')
    assert response.status_code==503
    assert 'redis_credentials_missing' in caplog.text
    assert 'test-token' not in caplog.text
    assert 'redis_credentials_missing' not in response.text


def test_redis_credentials_trim_whitespace(monkeypatch):
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL',' https://test.upstash.io/\n')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN',' test-token\n')
    store=RedisStore()
    assert store.url=='https://test.upstash.io' and store.token=='test-token'
