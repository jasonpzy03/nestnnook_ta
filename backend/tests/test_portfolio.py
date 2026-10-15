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


def property_unit(**patch):
    return {**dict(unit='16-03', property_name='Trellis', address='Test address', bathrooms=2,
                   carparks=2, rooms=[{'room':'01','standard_rent':1550},{'room':'02','standard_rent':3100}]), **patch}


def test_inventory_matches_existing_rental_and_weights_occupancy(client):
    client.post('/api/portfolio/rooms',json=rental(tenant_name='Alex'))
    initial = client.get('/api/portfolio?month=2026-10').json()
    assert initial['occupancy_rate'] is None and initial['unlinked_rentals'] == 1
    assert client.post('/api/portfolio/units',json=property_unit()).status_code == 200
    assert client.post('/api/portfolio/units',json=property_unit(unit='B',carparks=1,rooms=[{'room':'1','standard_rent':620}])).status_code == 200
    result = client.get('/api/portfolio?month=2026-10').json()
    assert result['total_bedrooms'] == 3 and result['total_carparks'] == 3
    assert result['occupied_room_days'] == 7 and result['available_room_days'] == 93
    assert result['occupancy_rate'] == 7.53 and result['unlinked_rentals'] == 0
    assert result['vacancy_loss'] == 1550 + 2400 + 620
    unit = result['units'][0]
    assert unit['occupancy_rate'] == 11.29 and unit['vacancy_loss'] == 3950
    assert unit['expected_income'] == 770  # Seven days room rent plus parking.
    assert unit['room_rows'][1]['tenant_name'] == 'Alex'
    assert unit['room_rows'][1]['vacant_days'] == 24
    full = client.get('/api/portfolio?month=2026-11').json()
    assert full['units'][0]['occupancy_rate'] == 50
    assert full['units'][0]['vacancy_loss'] == 1550
    expired = client.get('/api/portfolio?month=2027-05').json()
    assert expired['occupancy_rate'] == 0 and expired['vacancy_loss'] == 5270


def test_free_or_discounted_rent_is_still_occupied(client):
    client.post('/api/portfolio/units',json=property_unit(rooms=[{'room':'1','standard_rent':1200}]))
    saved = client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'1','rent':0,'start_date':'2024-02-29'}).json()
    result = client.get('/api/portfolio?month=2024-02').json()
    assert result['occupancy_rate'] == 3.45 and result['vacancy_loss'] == 1158.62
    assert client.get('/api/portfolio?month=2024-03').json()['vacancy_loss'] == 0
    client.put('/api/portfolio/rooms/'+saved['id'],json={'unit':'16-03','room':'1','rent':800,'active':False,'revision':saved['revision']})
    result = client.get('/api/portfolio?month=2024-03').json()
    assert result['occupancy_rate'] == 0 and result['vacancy_loss'] == 1200


def test_property_validation_and_atomic_link_guards(client):
    for patch in ({'rooms':[]},{'carparks':-1},{'bathrooms':1.5},
                  {'rooms':[{'room':'1','standard_rent':-1}]},
                  {'rooms':[{'room':'Room 01','standard_rent':10},{'room':'R1','standard_rent':20}]}):
        assert client.post('/api/portfolio/units',json=property_unit(**patch)).status_code == 422
    unit = client.post('/api/portfolio/units',json=property_unit()).json()
    assert len(client.get('/api/portfolio/units').json()['units']) == 1
    assert client.post('/api/portfolio/units',json=property_unit(unit=' Unit 16-03 ')).status_code == 409
    assert client.post('/api/portfolio/rooms',json={**rental(),'room':'3'}).status_code == 422
    tenant = client.post('/api/portfolio/rooms',json=rental()).json()
    url = '/api/portfolio/units/'+unit['id']
    assert client.delete(url,params={'revision':unit['revision']}).status_code == 422
    assert client.put(url,json={**property_unit(rooms=[{'room':'1','standard_rent':100}]),'revision':unit['revision']}).status_code == 422
    updated = client.put(url,json={**property_unit(notes='Updated'),'revision':unit['revision']})
    assert updated.status_code == 200
    assert client.put(url,json={**property_unit(),'revision':unit['revision']}).status_code == 409
    assert client.delete(url,params={'revision':unit['revision']}).status_code == 409
    assert client.delete('/api/portfolio/rooms/'+tenant['id'],params={'revision':tenant['revision']}).status_code == 200
    assert client.delete(url,params={'revision':updated.json()['revision']}).status_code == 200


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
    assert client.put('/api/portfolio/rooms/'+first['id'],json={**rental(),'room':'03','revision':first['revision']}).status_code == 200
    assert client.post('/api/portfolio/rooms',json={**rental(),'unit':'17-03'}).status_code == 200
    assert client.post('/api/portfolio/rooms',json={**rental(),'room':'04'}).status_code == 200
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


def test_property_expenses_fixed_and_monthly_breakdown(client):
    unit = property_unit(fixed_costs={'house_rental':'1800.50','wifi':100,'indah_water':8},
        monthly_costs={'2026-10':{'electricity':'210.25','water':'30.10','cleaning':80,'others':[{'name':'Repair','amount':'45.20'}]},
                       '2026-11':{'electricity':0,'water':0,'cleaning':0,'others':[]}})
    assert client.post('/api/portfolio/units',json=unit).status_code == 200
    client.post('/api/portfolio/rooms',json=rental())
    client.post('/api/portfolio/expenses',json={'name':'Legacy cost','amount':20})
    result = client.get('/api/portfolio?month=2026-10').json()
    assert result['fixed_expenses'] == 1928.50
    assert result['variable_expenses'] == 365.55
    assert result['total_expenses'] == 2294.05
    assert result['rental_income'] == 770 and result['net_income'] == -1524.05
    assert result['missing_expense_units'] == 0
    row = result['units'][0]
    assert row['fixed_expenses'] == 1908.50 and row['total_expenses'] == 2274.05
    assert row['net_income'] == -1504.05 and row['missing_expenses'] == []
    assert len(row['selected_month_costs']['others']) == 1
    assert row['selected_month_costs']['cleaning'] == '80'
    november = client.get('/api/portfolio?month=2026-11').json()
    assert november['variable_expenses'] == 0 and november['missing_expense_units'] == 0
    december = client.get('/api/portfolio?month=2026-12').json()
    assert december['variable_expenses'] == 0 and december['missing_expense_units'] == 1
    assert december['units'][0]['missing_expenses'] == ['electricity','water','cleaning','others']
    # Fixed costs continue for vacant months; variable costs never carry forward.
    empty = client.get('/api/portfolio?month=2027-06').json()
    assert empty['net_income'] == -1928.50


def test_expense_missing_values_and_multi_unit_totals(client):
    client.post('/api/portfolio/units',json=property_unit(fixed_costs={'house_rental':900},monthly_costs={'2026-10':{'electricity':0}}))
    client.post('/api/portfolio/units',json=property_unit(unit='B',fixed_costs={'house_rental':700},monthly_costs={'2026-10':{'water':12,'others':[]}}))
    result = client.get('/api/portfolio?month=2026-10').json()
    assert result['fixed_expenses'] == 1600 and result['variable_expenses'] == 12
    assert result['net_income'] == -1612 and result['missing_expense_units'] == 2
    assert result['units'][0]['missing_expenses'] == ['water','cleaning','others']
    assert result['units'][1]['missing_expenses'] == ['electricity','cleaning']
    # Older property records have valid zero fixed costs and missing variable costs.
    old = property_unit(unit='Old')
    old.update(kind='unit',id=portfolio.unit_key('Old'),revision='v1')
    projected = portfolio.project([old],'2026-10')
    assert projected['fixed_expenses'] == 0 and projected['missing_expense_units'] == 1


def test_expense_validation_and_revision_protection(client):
    for patch in ({'fixed_costs':{'wifi':-1}}, {'fixed_costs':{'indah_water':'1.001'}},
                  {'monthly_costs':{'2026-10':{'cleaning':-1}}}, {'monthly_costs':{'2026-10':{'cleaning':'1.001'}}}, {'monthly_costs':{'2026-13':{}}}, {'monthly_costs':{'2026-10':{'water':-1}}},
                  {'monthly_costs':{'2026-10':{'others':[{'name':' ','amount':1}]}}},
                  {'monthly_costs':{'2026-10':{'others':[{'name':'Repair','amount':None}]}}}):
        assert client.post('/api/portfolio/units',json=property_unit(**patch)).status_code == 422
    first = client.post('/api/portfolio/units',json=property_unit()).json()
    update = {**property_unit(monthly_costs={'2026-10':{'electricity':100}}),'revision':first['revision']}
    url = '/api/portfolio/units/'+first['id']
    assert client.put(url,json=update).status_code == 200
    stale = client.put(url,json={**update,'monthly_costs':{'2026-11':{'water':50}}})
    assert stale.status_code == 409
    assert stale.json()['detail']['record']['monthly_costs']['2026-10']['electricity'] == '100'
    assert client.get('/api/portfolio?month=2026-10').json()['variable_expenses'] == 100


def test_correct_rental_unit_moves_record_and_occupancy(client):
    client.post('/api/portfolio/units',json=property_unit())
    client.post('/api/portfolio/units',json=property_unit(unit='17-03'))
    saved = client.post('/api/portfolio/rooms',json=rental(tenant_name='Alex')).json()
    corrected = {**rental(tenant_name='Alex'),'unit':'17-03','revision':saved['revision']}
    result = client.put('/api/portfolio/rooms/'+saved['id'],json=corrected)
    assert result.status_code == 200
    moved = result.json()
    assert moved['id'] == portfolio.room_key('17-03','02') and moved['revision'] != saved['revision']
    dashboard = client.get('/api/portfolio?month=2026-10').json()
    assert len(dashboard['rooms']) == 1 and dashboard['rental_income'] == 770
    assert dashboard['rooms'][0]['tenant_name'] == 'Alex'
    assert dashboard['units'][0]['occupied_room_days'] == 0
    assert dashboard['units'][1]['occupied_room_days'] == 7
    assert client.put('/api/portfolio/rooms/'+saved['id'],json=corrected).status_code == 404
    assert client.post('/api/portfolio/rooms',json={**rental(),'unit':'17-03'}).status_code == 409
    # Inventory itself was not renamed or removed.
    assert {u['unit'] for u in dashboard['units']} == {'16-03','17-03'}


def test_rental_correction_duplicate_stale_and_inventory_guards(client):
    saved = client.post('/api/portfolio/rooms',json=rental()).json()
    other = client.post('/api/portfolio/rooms',json={**rental(),'unit':'17-03','rent':900}).json()
    url = '/api/portfolio/rooms/'+saved['id']
    correction = {**rental(),'unit':'17-03','revision':saved['revision']}
    duplicate = client.put(url,json=correction)
    assert duplicate.status_code == 409 and isinstance(duplicate.json()['detail'],str)
    assert len(client.get('/api/portfolio?month=2026-10').json()['rooms']) == 2
    client.post('/api/portfolio/units',json=property_unit(unit='B',rooms=[{'room':'1','standard_rent':1000}]))
    assert client.put(url,json={**correction,'unit':'B'}).status_code == 422
    updated = client.put(url,json={**rental(),'rent':3200,'revision':saved['revision']}).json()
    assert client.put(url,json={**correction,'unit':'C'}).status_code == 409
    current = client.get('/api/portfolio?month=2026-10').json()['rooms']
    assert next(r for r in current if r['id']==saved['id'])['rent'] == 3200
    assert next(r for r in current if r['id']==other['id'])['rent'] == 900
    # A text-format correction keeps the same normalised identity.
    normalised = client.put(url,json={**rental(),'unit':' Unit 16-03 ','revision':updated['revision']})
    assert normalised.status_code == 200 and normalised.json()['id'] == saved['id']


def test_concurrent_rental_corrections_do_not_overwrite_destination(client):
    a = client.post('/api/portfolio/rooms',json=rental()).json()
    b = client.post('/api/portfolio/rooms',json={**rental(),'unit':'B'}).json()
    def move(row):
        return client.put('/api/portfolio/rooms/'+row['id'],json={**rental(),'unit':'C','revision':row['revision']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(move,[a,b])) == [200,409]
    rows = client.get('/api/portfolio?month=2026-10').json()['rooms']
    assert len(rows) == 2 and sum(r['unit']=='C' for r in rows) == 1


def test_parking_loss_is_combined_with_room_loss_at_advertised_rate(client):
    client.post('/api/portfolio/units',json=property_unit(standard_parking_rent=310))
    client.post('/api/portfolio/rooms',json={**rental(),'parking':100})
    result = client.get('/api/portfolio?month=2026-10').json()
    # Room loss 3950 + 55 vacant parking-space days * 310 / 31.
    assert result['vacancy_loss'] == 4500
    assert result['units'][0]['vacancy_loss'] == 4500
    assert result['occupancy_rate'] == 11.29  # Bedroom occupancy unchanged.
    assert result['rental_income'] == 722.58  # Income uses the agreed 100, not advertised 310.
    assert result['parking_rate_missing_units'] == 0
    full = client.get('/api/portfolio?month=2026-11').json()
    assert full['vacancy_loss'] == 1860  # One vacant room plus one vacant space.
    expired = client.get('/api/portfolio?month=2027-05').json()
    assert expired['vacancy_loss'] == 5270
    client.post('/api/portfolio/units',json=property_unit(unit='B',carparks=1,standard_parking_rent=100,rooms=[{'room':'1','standard_rent':0}]))
    total = client.get('/api/portfolio?month=2026-10').json()
    assert total['vacancy_loss'] == 4600
    assert total['units'][1]['vacancy_loss'] == 100


@pytest.mark.parametrize('second_start,second_end,wanted,over_capacity',[
    ('2026-10-01','2026-10-10',210,True),
    ('2026-10-21','2026-10-31',100,False),
])
def test_parking_vacancy_counts_capacity_per_day(client,second_start,second_end,wanted,over_capacity):
    client.post('/api/portfolio/units',json=property_unit(carparks=1,standard_parking_rent=310,rooms=[{'room':'1','standard_rent':0},{'room':'2','standard_rent':0}]))
    client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'1','rent':0,'parking':50,'start_date':'2026-10-01','last_rental_date':'2026-10-10'})
    response = client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'2','rent':0,'parking':50,'start_date':second_start,'last_rental_date':second_end})
    assert response.status_code == (422 if over_capacity else 200)
    row = client.get('/api/portfolio?month=2026-10').json()['units'][0]
    assert row['vacancy_loss'] == wanted
    assert row['parking_over_capacity'] is False


def test_parking_rate_missing_zero_and_leap_month(client):
    for value in (-1,'1.001'):
        assert client.post('/api/portfolio/units',json=property_unit(standard_parking_rent=value)).status_code == 422
    saved = client.post('/api/portfolio/units',json=property_unit(carparks=1,rooms=[{'room':'1','standard_rent':0}])).json()
    missing = client.get('/api/portfolio?month=2024-02').json()
    assert missing['parking_rate_missing_units'] == 1 and missing['vacancy_loss'] == 0
    updated = client.put('/api/portfolio/units/'+saved['id'],json={**property_unit(carparks=1,standard_parking_rent=290,rooms=[{'room':'1','standard_rent':0}]),'revision':saved['revision']}).json()
    tenant = client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'1','rent':0,'parking':100,'start_date':'2024-02-29'}).json()
    assert client.get('/api/portfolio?month=2024-02').json()['vacancy_loss'] == 280
    assert client.get('/api/portfolio?month=2024-03').json()['vacancy_loss'] == 0
    client.put('/api/portfolio/rooms/'+tenant['id'],json={'unit':'16-03','room':'1','rent':0,'parking':100,'active':False,'revision':tenant['revision']})
    assert client.get('/api/portfolio?month=2024-03').json()['vacancy_loss'] == 290
    client.put('/api/portfolio/units/'+saved['id'],json={**property_unit(carparks=1,standard_parking_rent=0,rooms=[{'room':'1','standard_rent':0}]),'revision':updated['revision']})
    zero = client.get('/api/portfolio?month=2024-03').json()
    assert zero['vacancy_loss'] == 0 and zero['parking_rate_missing_units'] == 0


def test_parking_capacity_guard_for_updates_dates_and_property_count(client):
    unit = client.post('/api/portfolio/units',json=property_unit(carparks=1)).json()
    first_input = {'unit':'16-03','room':'1','rent':1000,'parking':100,'start_date':'2026-10-01','last_rental_date':'2026-10-15'}
    first = client.post('/api/portfolio/rooms',json=first_input).json()
    second_input = {**first_input,'room':'2','start_date':'2026-10-16','last_rental_date':'2026-10-31'}
    second = client.post('/api/portfolio/rooms',json=second_input).json()
    # Same-day overlaps are blocked; the next day is available.
    assert client.put('/api/portfolio/rooms/'+second['id'],json={**second_input,'start_date':'2026-10-15','revision':second['revision']}).status_code == 422
    assert client.put('/api/portfolio/units/'+unit['id'],json={**property_unit(carparks=0),'revision':unit['revision']}).status_code == 422
    # Editing one's own rental must not count it twice.
    assert client.put('/api/portfolio/rooms/'+first['id'],json={**first_input,'parking':120,'revision':first['revision']}).status_code == 200
    # Excluding a rental releases its capacity even with overlapping dates.
    assert client.put('/api/portfolio/rooms/'+second['id'],json={**second_input,'start_date':'2026-10-01','active':False,'revision':second['revision']}).status_code == 200


def test_parking_capacity_guard_for_concurrent_saves(client):
    client.post('/api/portfolio/units',json=property_unit(carparks=1))
    def save(room):
        return client.post('/api/portfolio/rooms',json={'unit':'16-03','room':room,'rent':1000,'parking':100}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(save,['1','2']))
    assert codes[0] == 200 and codes[1] in (409,422)
    result = client.get('/api/portfolio?month=2026-10').json()
    assert len(result['rooms']) == 1


def test_parking_capacity_blocks_unit_correction_and_legacy_registration(client):
    client.post('/api/portfolio/units',json=property_unit(carparks=1))
    client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'1','rent':1000,'parking':100})
    source = {'unit':'Typo','room':'2','rent':1000,'parking':100}
    saved = client.post('/api/portfolio/rooms',json=source).json()
    assert client.put('/api/portfolio/rooms/'+saved['id'],json={**source,'unit':'16-03','revision':saved['revision']}).status_code == 422
    rooms = client.get('/api/portfolio?month=2026-10').json()['rooms']
    assert any(r['unit']=='Typo' for r in rooms)
    # Creating inventory must also validate pre-existing rentals against capacity.
    assert client.post('/api/portfolio/units',json=property_unit(unit='Typo',carparks=0)).status_code == 422
    assert client.post('/api/portfolio/units',json=property_unit(unit='Typo',carparks=1)).status_code == 200


def test_parking_capacity_zero_charge_and_multiple_spaces(client):
    unit = client.post('/api/portfolio/units',json=property_unit(carparks=2)).json()
    for room in ('1','2'):
        assert client.post('/api/portfolio/rooms',json={'unit':'16-03','room':room,'rent':1000,'parking':100}).status_code == 200
    assert client.put('/api/portfolio/units/'+unit['id'],json={**property_unit(carparks=1),'revision':unit['revision']}).status_code == 422
    client.post('/api/portfolio/units',json=property_unit(unit='B',carparks=0))
    assert client.post('/api/portfolio/rooms',json={'unit':'B','room':'1','rent':1000,'parking':0}).status_code == 200
    assert client.post('/api/portfolio/rooms',json={'unit':'B','room':'2','rent':1000,'parking':100}).status_code == 422


def test_redis_capacity_snapshot_rejects_intervening_reservation(client,monkeypatch):
    if not portfolio.cloud_enabled():
        return  # The local path uses a single lock around check and write.
    client.post('/api/portfolio/units',json=property_unit(carparks=1))
    command = RedisStore.command
    injected = False
    def reserve_between_check_and_write(store,*args):
        nonlocal injected
        if args[0]=='EVAL' and not injected:
            injected = True
            competing = portfolio.Rental(unit='16-03',room='2',rent=1000,parking=100).model_dump(mode='json')
            competing.update(kind='room',id=portfolio.room_key('16-03','2'),revision='competing')
            command(store,'HSET',store.key('portfolio'),'room:'+competing['id'],json.dumps(competing))
        return command(store,*args)
    monkeypatch.setattr(RedisStore,'command',reserve_between_check_and_write)
    result = client.post('/api/portfolio/rooms',json={'unit':'16-03','room':'1','rent':1000,'parking':100})
    assert result.status_code == 409 and 'Try saving again' in result.json()['detail']
    rows = client.get('/api/portfolio?month=2026-10').json()['rooms']
    assert len(rows)==1 and rows[0]['room']=='2'


def test_room_number_correction_preserves_income_and_guards(client):
    client.post('/api/portfolio/units',json=property_unit())
    saved = client.post('/api/portfolio/rooms',json=rental()).json()
    url = '/api/portfolio/rooms/'+saved['id']
    correction = {**rental(),'room':'01','revision':saved['revision']}
    moved = client.put(url,json=correction)
    assert moved.status_code == 200
    row = moved.json()
    assert row['id'] == portfolio.room_key('16-03','01')
    data = client.get('/api/portfolio?month=2026-10').json()
    assert len(data['rooms']) == 1 and data['rental_income'] == 770
    assert next(r for r in data['units'][0]['room_rows'] if r['room']=='01')['rental']['id'] == row['id']
    assert client.put(url,json=correction).status_code == 404
    client.post('/api/portfolio/rooms',json={**rental(),'parking':0})
    url = '/api/portfolio/rooms/'+row['id']
    assert client.put(url,json={**rental(),'revision':row['revision']}).status_code == 409
    assert client.put(url,json={**correction,'room':'99','revision':row['revision']}).status_code == 422
    assert client.put(url,json={**correction,'revision':saved['revision']}).status_code == 409
