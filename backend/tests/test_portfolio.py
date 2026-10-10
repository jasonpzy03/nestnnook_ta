import json
from concurrent.futures import ThreadPoolExecutor

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend import portfolio
from backend.cloud_store import RedisStore, StorageError


@pytest.fixture(params=['local','cloud'])
def client(request, monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio, 'FILE', tmp_path/'portfolio.json')
    for key in ('VERCEL','UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN'):
        monkeypatch.delenv(key, raising=False)
    if request.param == 'cloud':
        redis = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setenv('UPSTASH_REDIS_REST_URL', 'https://test.upstash.io')
        monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN', 'test-token')
        monkeypatch.setattr(RedisStore, 'command', lambda self,*args:redis.execute_command(*args))
    app = FastAPI()
    app.include_router(portfolio.router)
    with TestClient(app) as test_client:
        yield test_client


def rental(**patch):
    return dict(unit='16-03', room='Room 02', rent=3100, parking=310,
                start_date='2026-10-25', last_rental_date='2027-04-30', active=True, **patch)


def test_projection_partial_full_and_expiry_months(client):
    assert client.post('/api/portfolio/rooms',json=rental()).status_code == 200
    assert client.post('/api/portfolio/expenses',json={'name':'Internet and cleaning','amount':500}).status_code == 200
    for month, income, net, days in [('2026-09',0,-500,0),('2026-10',770,270,7),('2026-11',3410,2910,30),('2027-04',3410,2910,30),('2027-05',0,-500,0)]:
        data = client.get('/api/portfolio',params={'month':month}).json()
        assert (data['rental_income'],data['net_income'],data['rooms'][0]['rental_days']) == (income,net,days)
        assert data['fixed_expenses'] == 500


def test_duplicate_share_requires_explicit_update_and_stale_writes_fail(client):
    first = client.post('/api/portfolio/rooms',json=rental()).json()
    same = {**rental(), 'unit':' Unit 16-03 ', 'room':'r2', 'rent':3200}
    duplicate = client.post('/api/portfolio/rooms',json=same)
    assert duplicate.status_code == 409
    assert duplicate.json()['detail']['record']['id'] == first['id']
    update = {**same, 'revision':first['revision']}
    saved = client.put('/api/portfolio/rooms/'+first['id'],json=update)
    assert saved.status_code == 200
    assert client.put('/api/portfolio/rooms/'+first['id'],json=update).status_code == 409
    current = client.get('/api/portfolio?month=2026-11').json()
    assert len(current['rooms']) == 1
    assert current['rental_income'] == 3510
    assert client.delete('/api/portfolio/rooms/'+first['id'],params={'revision':first['revision']}).status_code == 409
    assert client.delete('/api/portfolio/rooms/'+first['id'],params={'revision':saved.json()['revision']}).status_code == 200
    assert client.get('/api/portfolio?month=2026-11').json()['rooms'] == []


def test_room_identity_and_validation(client):
    for patch in ({'rent':-1},{'rent':1.001},{'rent':None},{'unit':' '},{'room':'Room '},{'last_rental_date':'2026-10-24'},{'tenant_id':'must-not-be-stored'}):
        assert client.post('/api/portfolio/rooms',json={**rental(),**patch}).status_code == 422
    for month in ('2026-13','2026-00','0000-01','Oct 2026'):
        assert client.get('/api/portfolio',params={'month':month}).status_code == 422
    first = client.post('/api/portfolio/rooms',json=rental()).json()
    assert client.put('/api/portfolio/rooms/'+first['id'],json={**rental(),'room':'03','revision':first['revision']}).status_code == 422
    assert client.post('/api/portfolio/rooms',json={**rental(),'unit':'17-03'}).status_code == 200
    assert client.post('/api/portfolio/rooms',json={**rental(),'room':'03'}).status_code == 200
    assert len(client.get('/api/portfolio?month=2026-11').json()['rooms']) == 3


def test_manual_ongoing_inactive_and_expense_edit(client):
    first = client.post('/api/portfolio/rooms',json={'unit':'A','room':'1','rent':1200}).json()
    assert client.get('/api/portfolio?month=2024-02').json()['rental_income'] == 1200
    assert client.put('/api/portfolio/rooms/'+first['id'],json={'unit':'A','room':'1','rent':1200,'active':False,'revision':first['revision']}).status_code == 200
    assert client.get('/api/portfolio?month=2024-02').json()['rental_income'] == 0
    expense = client.post('/api/portfolio/expenses',json={'name':'Rent','amount':1100}).json()
    update = client.put('/api/portfolio/expenses/'+expense['id'],json={'name':'Unit rent','amount':1000,'revision':expense['revision']})
    assert update.status_code == 200
    assert client.get('/api/portfolio?month=2024-02').json()['net_income'] == -1000
    assert client.delete('/api/portfolio/expenses/'+expense['id'],params={'revision':update.json()['revision']}).status_code == 200


def test_concurrent_adds_do_not_double_count(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _:client.post('/api/portfolio/rooms',json=rental()).status_code,range(8)))
    assert results.count(200) == 1
    assert results.count(409) == 7


def test_leap_year_and_cent_rounding():
    row={'kind':'room','id':'test','revision':'test','unit':'A','room':'1','rent':'1000.01','parking':'0.00','start_date':'2024-02-25','last_rental_date':None,'active':True}
    data=portfolio.project([row],'2024-02')
    assert data['rental_income'] == 172.42
    assert data['rooms'][0]['rental_days'] == 5
    assert portfolio.project([row],'2024-03')['rental_income'] == 1000.01
    row.update(rent='100.01',parking='100.01',start_date='2026-04-16')
    assert portfolio.project([row],'2026-04')['rental_income'] == 100.02


def test_cloud_outage_never_writes_local(monkeypatch,tmp_path):
    target=tmp_path/'never-created.json'
    monkeypatch.setattr(portfolio,'FILE',target)
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL','https://test.upstash.io')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN','test-token')
    def fail(*args):raise StorageError('outage')
    monkeypatch.setattr(RedisStore,'command',fail)
    with pytest.raises(Exception) as error:portfolio.add_room(portfolio.Rental(**rental()))
    assert error.value.status_code == 503
    assert not target.exists()


def test_authenticated_access_and_cross_site_protection(monkeypatch,tmp_path):
    from backend.main import app, auth
    from backend.auth import password_record
    for key in ('VERCEL','UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('NEST_STAFF_PASSWORD_RECORD',json.dumps(password_record('portfolio-test-password')))
    monkeypatch.setattr(portfolio,'FILE',tmp_path/'private.json')
    with TestClient(app) as client:
        assert client.get('/api/portfolio?month=2026-10').status_code == 401
        assert client.post('/api/portfolio/rooms',json=rental()).status_code == 401
        assert client.post('/login',data={'password':'portfolio-test-password'},follow_redirects=False).status_code == 303
        assert client.post('/api/portfolio/rooms',json=rental(),headers={'origin':'https://untrusted.example'}).status_code == 403
        assert client.post('/api/portfolio/rooms',json=rental()).status_code == 200
        response=client.get('/api/portfolio?month=2026-10')
        assert response.status_code == 200 and response.headers['cache-control']=='no-store'
