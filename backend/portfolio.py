"""Shared rental projections; no identity documents or payment history are stored."""
import hashlib
import json
import re
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, StringConstraints, model_validator
from .models import StrictModel, Money
from .cloud_store import RedisStore, StorageError, cloud_enabled

router = APIRouter(prefix='/api/portfolio')
FILE = Path(__file__).resolve().parents[1]/'.local/portfolio.json'
LOCK = Lock()
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RentalPeriod(StrictModel):
    unit: Label
    rent: Money
    start_date: date | None = None
    last_rental_date: date | None = None
    active: bool = True
    tenant_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ''

    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date and self.last_rental_date and self.last_rental_date < self.start_date:
            raise ValueError('Last rental day must be on or after the move-in date.')
        return self


class Rental(RentalPeriod):
    room: Label
    parking: Money = Decimal('0')
    security_deposit: Money | None = None
    access_deposit: Money | None = None


class ParkingRental(RentalPeriod):
    space: Label
    carpark_deposit: Money | None = None


class ParkingUpdate(ParkingRental):
    revision: str = Field(min_length=1, max_length=40)


class PropertyRoom(StrictModel):
    room: Label
    standard_rent: Money


class FixedCosts(StrictModel):
    house_rental: Money = Decimal('0')
    wifi: Money = Decimal('0')
    indah_water: Money = Decimal('0')


class OtherCost(StrictModel):
    name: Label
    amount: Money


class MonthlyCosts(StrictModel):
    electricity: Money | None = None
    water: Money | None = None
    cleaning: Money | None = None
    # None means not entered; [] explicitly confirms no other expenses.
    others: list[OtherCost] | None = Field(default=None, max_length=50)


Month = Annotated[str, StringConstraints(pattern=r'^(?:19|[2-9]\d)\d{2}-(?:0[1-9]|1[0-2])$')]


class PropertyUnit(StrictModel):
    unit: Label
    property_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ''
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ''
    bathrooms: int = Field(default=0, ge=0, le=30)
    carparks: int = Field(default=0, ge=0, le=100)
    standard_parking_rent: Money | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ''
    rooms: list[PropertyRoom] = Field(min_length=1, max_length=30)
    fixed_costs: FixedCosts = Field(default_factory=FixedCosts)
    monthly_costs: dict[Month, MonthlyCosts] = Field(default_factory=dict, max_length=1200)

    @model_validator(mode='after')
    def unique_rooms(self):
        keys = [room_key(self.unit, room.room) for room in self.rooms]
        if len(set(keys)) != len(keys):
            raise ValueError('Room numbers must be unique within a unit.')
        return self


class PropertyUpdate(PropertyUnit):
    revision: str = Field(min_length=1, max_length=40)


class Expense(StrictModel):
    name: Label
    amount: Money


class RentalUpdate(Rental):
    revision: str = Field(min_length=1, max_length=40)


class ExpenseUpdate(Expense):
    revision: str = Field(min_length=1, max_length=40)


def room_key(unit, room):
    unit = re.sub(r'\s+', '', re.sub(r'^(?:unit\s+|#)', '', unit.strip(), flags=re.I)).casefold()
    room = re.sub(r'^(?:room\s*|r(?=\s*\d))', '', room.strip(), flags=re.I)
    room = re.sub(r'\s+', '', room).casefold()
    if room.isdecimal():
        room = str(int(room))
    if not unit or not room:
        raise HTTPException(422, 'Enter a unit and room number.')
    return hashlib.sha256(json.dumps([unit, room]).encode()).hexdigest()


def unit_key(unit):
    return room_key(unit, '__property__')


def parking_key(unit, space):
    space = re.sub(r'^(?:lot|space)\s+', '', space.strip(), flags=re.I)
    space = re.sub(r'\s+', '', space).casefold()
    if not space:
        raise HTTPException(422, 'Enter a car-park space number.')
    if space.isdecimal():
        space = str(int(space))
    return room_key(unit, '__parking__'+space)


def read_local():
    try:
        if not FILE.exists():
            return {}
        data = json.loads(FILE.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, OSError):
        raise StorageError('Rental portfolio could not be read.') from None


def records():
    try:
        if cloud_enabled():
            store = RedisStore()
            values = store.command('HVALS', store.key('portfolio'))
            if not isinstance(values, list):
                raise ValueError()
            data = [json.loads(value) for value in values]
        else:
            with LOCK:
                data = list(read_local().values())
        for row in data:
            model = {'room':Rental,'parking':ParkingRental,'expense':Expense,'unit':PropertyUnit}.get(row['kind'])
            if model is None or not isinstance(row['id'], str) or not isinstance(row['revision'], str):
                raise ValueError()
            model.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision','room_ids','unit_id')})
        return data
    except (StorageError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Rental portfolio is unavailable. Please try again.') from None


def validate_parking_capacity(data, field, record):
    if not record or record['kind'] not in ('unit', 'room', 'parking'):
        return
    candidate = {key:value for key,value in data.items() if key != field}
    candidate[record['kind']+':'+record['id']] = record
    unit_id = record['id'] if record['kind']=='unit' else unit_key(record['unit'])
    unit = candidate.get('unit:'+unit_id)
    if not unit:
        if record['kind']=='parking':
            raise HTTPException(422, 'Register the property unit before adding a car-park rental.')
        return  # Legacy rentals may be entered before their property is registered.
    events = {}
    for rental in candidate.values():
        if rental['kind'] not in ('room','parking') or unit_key(rental['unit'])!=unit_id or not rental.get('active',True):
            continue
        if rental['kind']=='room' and Decimal(str(rental.get('parking',0)))<=0:
            continue
        start = date.fromisoformat(rental['start_date']).toordinal() if rental.get('start_date') else date.min.toordinal()
        end = date.fromisoformat(rental['last_rental_date']).toordinal() if rental.get('last_rental_date') else date.max.toordinal()
        events[start] = events.get(start,0)+1
        events[end+1] = events.get(end+1,0)-1
    occupied = 0
    for day in sorted(events):
        occupied += events[day]
        if occupied > unit['carparks']:
            raise HTTPException(422, 'Parking rentals overlap beyond this unit’s car-park capacity. Correct the parking amounts, tenancy dates or space count before saving.')


def mutate(kind, identifier, payload=None, expected=None, delete=False, destination=None):
    """Compare revisions atomically, so re-sharing cannot duplicate or overwrite a room silently."""
    field = kind+':'+identifier
    destination = destination or identifier
    destination_field = kind+':'+destination
    record = None if delete else {**payload, 'kind':kind, 'id':destination, 'revision':uuid.uuid4().hex}
    if record and kind == 'unit':
        record['room_ids'] = [room_key(payload['unit'], room['room']) for room in payload['rooms']]
    if record and kind == 'parking':
        record['unit_id'] = unit_key(payload['unit'])
    unit_field = 'unit:'+unit_key(payload['unit']) if payload and kind == 'room' else ''
    try:
        if cloud_enabled():
            store = RedisStore()
            snapshot = {}
            if record and kind in ('unit','room','parking'):
                for raw in store.command('HVALS', store.key('portfolio')):
                    row = json.loads(raw)
                    snapshot[row['kind']+':'+row['id']] = raw
                validate_parking_capacity({key:json.loads(raw) for key,raw in snapshot.items()}, field, record)
            script = """local old=redis.call('HGET',KEYS[1],ARGV[1])
            if ARGV[2]=='' then
                if old then return {409,old} end
                if redis.call('HLEN',KEYS[1])>=2000 then return {422,''} end
            else
                if not old then return {404,''} end
                if cjson.decode(old).revision~=ARGV[2] then return {409,old} end
            end
            if ARGV[9]~='' then
                local expected=cjson.decode(ARGV[9])
                local count=0
                for key,value in pairs(expected) do
                    count=count+1
                    if redis.call('HGET',KEYS[1],key)~=value then return {426,''} end
                end
                if redis.call('HLEN',KEYS[1])~=count then return {426,''} end
            end
            if ARGV[8]~=ARGV[1] and redis.call('HEXISTS',KEYS[1],ARGV[8])==1 then return {425,''} end
            if ARGV[5]=='room' and ARGV[3]~='delete' then
                local unit=redis.call('HGET',KEYS[1],ARGV[6])
                if unit then
                    local found=false
                    for _,id in ipairs(cjson.decode(unit).room_ids) do if id==ARGV[7] then found=true end end
                    if not found then return {423,''} end
                end
            end
            if ARGV[5]=='unit' and old then
                if ARGV[3]=='delete' then
                    for _,raw in ipairs(redis.call('HVALS',KEYS[1])) do
                        local rental=cjson.decode(raw)
                        if rental.kind=='parking' and rental.unit_id==cjson.decode(old).id then return {427,''} end
                    end
                end
                local keep={}
                if ARGV[3]~='delete' then for _,id in ipairs(cjson.decode(ARGV[4]).room_ids) do keep[id]=true end end
                for _,id in ipairs(cjson.decode(old).room_ids) do
                    if not keep[id] and redis.call('HEXISTS',KEYS[1],'room:'..id)==1 then return {424,''} end
                end
            end
            if ARGV[3]=='delete' then redis.call('HDEL',KEYS[1],ARGV[1])
            else
                redis.call('HSET',KEYS[1],ARGV[8],ARGV[4])
                if ARGV[8]~=ARGV[1] then redis.call('HDEL',KEYS[1],ARGV[1]) end
            end
            return {200,''}"""
            code, old = store.command('EVAL', script, 1, store.key('portfolio'), field,
                                      expected or '', 'delete' if delete else 'save', json.dumps(record), kind, unit_field, destination, destination_field,
                                      json.dumps(snapshot) if record and kind in ('unit','room','parking') else '')
            old = json.loads(old) if old else None
        else:
            with LOCK:
                data = read_local()
                old = data.get(field)
                code = (409 if old else 422 if len(data)>=2000 else 200) if expected is None else (
                    404 if not old else 409 if old['revision'] != expected else 200)
                if code == 200:
                    if destination_field != field and destination_field in data:
                        raise HTTPException(409, 'A rental already exists for the corrected unit and space. No records were changed.' if kind=='parking' else 'A rental already exists for the corrected unit and room. No records were changed.')
                    if kind == 'room' and not delete and unit_field in data and destination not in data[unit_field]['room_ids']:
                        raise HTTPException(422, 'This room is not in the property inventory. Add the room to the unit first.')
                    if kind == 'unit' and old:
                        if delete and any(row['kind']=='parking' and unit_key(row['unit'])==identifier for row in data.values()):
                            raise HTTPException(422, 'Remove linked car-park rentals before removing this property.')
                        removed = set(old['room_ids']) - set(record['room_ids'] if record else [])
                        if any('room:'+key in data for key in removed):
                            raise HTTPException(422, 'Remove linked rental records before removing their rooms or property.')
                    validate_parking_capacity(data, field, record)
                    if delete:
                        data.pop(field)
                    else:
                        data[destination_field] = record
                        if destination_field != field:
                            data.pop(field)
                    FILE.parent.mkdir(parents=True, exist_ok=True)
                    temporary = FILE.with_suffix('.tmp')
                    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                    temporary.replace(FILE)
        if code == 409:
            raise HTTPException(409, {'message':'This record already exists or was changed. Review the saved values before updating.', 'record':old})
        if code == 404:
            raise HTTPException(404, 'This record no longer exists. Refresh the dashboard.')
        if code == 423:
            raise HTTPException(422, 'This room is not in the property inventory. Add the room to the unit first.')
        if code == 424:
            raise HTTPException(422, 'Remove linked rental records before removing their rooms or property.')
        if code == 425:
            raise HTTPException(409, 'A rental already exists for the corrected unit and space. No records were changed.' if kind=='parking' else 'A rental already exists for the corrected unit and room. No records were changed.')
        if code == 426:
            raise HTTPException(409, 'The portfolio changed while checking parking availability. Try saving again.')
        if code == 427:
            raise HTTPException(422, 'Remove linked car-park rentals before removing this property.')
        if code != 200:
            raise HTTPException(422, 'The rental portfolio is full.')
        return record or {'deleted':True}
    except (StorageError, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Could not save the rental portfolio. Please try again.') from None


def money(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def project(data, month):
    year, number = map(int, month.split('-'))
    first = date(year, number, 1)
    last = date(year, number, monthrange(year, number)[1])
    rooms, parking, expenses = [], [], []
    total_rent = Decimal('0')
    total_expenses = Decimal('0')
    for row in data:
        if row['kind'] == 'room':
            rental = Rental.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision')})
            start, end = max(first, rental.start_date or first), min(last, rental.last_rental_date or last)
            days = max(0, (end-start).days+1) if rental.active else 0
            # Match the document's pro-rated room rent; round each charge to cents.
            expected = money(rental.rent*days/last.day) + money(rental.parking*days/last.day)
            rooms.append({**row, 'security_deposit':float(rental.security_deposit) if rental.security_deposit is not None else None,
                          'access_deposit':float(rental.access_deposit) if rental.access_deposit is not None else None,
                          'rent':float(rental.rent), 'parking':float(rental.parking), 'rental_days':days, 'expected':float(expected)})
            total_rent += expected
        elif row['kind'] == 'parking':
            rental = ParkingRental.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision','unit_id')})
            start, end = max(first, rental.start_date or first), min(last, rental.last_rental_date or last)
            days = max(0, (end-start).days+1) if rental.active else 0
            expected = money(rental.rent*days/last.day)
            parking.append({**row, 'carpark_deposit':float(rental.carpark_deposit) if rental.carpark_deposit is not None else None,
                            'rent':float(rental.rent), 'rental_days':days, 'expected':float(expected)})
            total_rent += expected
        elif row['kind'] == 'expense':
            amount = Decimal(str(row['amount']))
            total_expenses += amount
            expenses.append({**row, 'amount':float(amount)})
    occupancy = occupancy_projection(data, rooms, first, last.day, parking)
    variable_total = Decimal('0')
    for unit in occupancy['units']:
        costs = property_costs(unit, month)
        unit.update(costs)
        unit['net_income'] = float(Decimal(str(unit['expected_income']))-Decimal(str(costs['total_expenses'])))
        total_expenses += Decimal(str(costs['fixed_expenses']))
        variable_total += Decimal(str(costs['variable_expenses']))
    return {**occupancy, 'month':month, 'rooms':sorted(rooms, key=lambda r:(r['unit'].casefold(),r['room'].casefold())),
            'parking':sorted(parking, key=lambda r:(r['unit'].casefold(),r['space'].casefold())),
            'earning_parking':sum(r['rental_days']>0 for r in parking),
            'expenses':sorted(expenses, key=lambda e:e['name'].casefold()),
            'rental_income':float(total_rent), 'fixed_expenses':float(total_expenses),
            'variable_expenses':float(variable_total), 'total_expenses':float(total_expenses+variable_total),
            'missing_expense_units':sum(bool(u['missing_expenses']) for u in occupancy['units']),
            'net_income':float(total_rent-total_expenses-variable_total), 'earning_rooms':sum(r['rental_days']>0 for r in rooms)}


def property_costs(unit, month):
    fixed = FixedCosts.model_validate(unit.get('fixed_costs', {}))
    monthly = MonthlyCosts.model_validate(unit.get('monthly_costs', {}).get(month, {}))
    fixed_total = sum((fixed.house_rental, fixed.wifi, fixed.indah_water), Decimal('0'))
    variable_total = (monthly.electricity or Decimal('0')) + (monthly.water or Decimal('0'))
    variable_total += monthly.cleaning or Decimal('0')
    variable_total += sum((item.amount for item in monthly.others or []), Decimal('0'))
    return {'fixed_costs':fixed.model_dump(mode='json'), 'selected_month_costs':monthly.model_dump(mode='json'),
            'fixed_expenses':float(fixed_total), 'variable_expenses':float(variable_total),
            'total_expenses':float(fixed_total+variable_total),
            'missing_expenses':[name for name in ('electricity','water','cleaning','others') if getattr(monthly,name) is None]}


def parking_vacancy(unit, rentals, first, days_in_month):
    capacity = unit['carparks']
    daily = [0]*days_in_month
    for rental in rentals:
        if unit_key(rental['unit']) != unit['id'] or not rental['rental_days']:
            continue
        if rental['kind']=='room' and rental['parking'] <= 0:
            continue
        # Both bundled parking and standalone parking occupy one space during their rental dates.
        start = max(first, date.fromisoformat(rental['start_date']) if rental.get('start_date') else first)
        last = first.replace(day=days_in_month)
        end = min(last, date.fromisoformat(rental['last_rental_date']) if rental.get('last_rental_date') else last)
        for day in range(start.day-1, end.day):
            daily[day] += 1
    vacant_days = sum(max(0, capacity-count) for count in daily)
    rate = unit.get('standard_parking_rent')
    loss = money(Decimal(str(rate))*vacant_days/days_in_month) if rate is not None else Decimal('0')
    occupied_days = capacity*days_in_month-vacant_days
    return loss, bool(capacity and rate is None), any(count>capacity for count in daily), occupied_days


def occupancy_projection(data, rentals, first, days_in_month, parking=()):
    by_room = {row['id']:row for row in rentals}
    units = []
    linked = set()
    for row in data:
        if row['kind'] != 'unit':
            continue
        room_rows = []
        loss = Decimal('0')
        potential = Decimal('0')
        expected = Decimal('0')
        occupied_days = 0
        for room in row['rooms']:
            identifier = room_key(row['unit'], room['room'])
            linked.add(identifier)
            rental = by_room.get(identifier)
            days = rental['rental_days'] if rental else 0
            standard = Decimal(str(room['standard_rent']))
            vacancy = money(standard*(days_in_month-days)/days_in_month)
            amount = Decimal(str(rental['expected'])) if rental else Decimal('0')
            room_rows.append({'id':identifier, 'room':room['room'], 'standard_rent':float(standard),
                              'tenant_name':rental.get('tenant_name','') if rental else '',
                              'rental':rental, 'occupied_days':days, 'vacant_days':days_in_month-days,
                              'vacancy_loss':float(vacancy), 'expected_income':float(amount)})
            occupied_days += days
            loss += vacancy
            potential += standard
            expected += amount
        available_days = len(room_rows)*days_in_month
        expected += sum((Decimal(str(r['expected'])) for r in parking if unit_key(r['unit'])==row['id']),Decimal('0'))
        parking_loss, missing_rate, over_capacity, occupied_parking_days = parking_vacancy(row, [*rentals,*parking], first, days_in_month)
        available_parking_days = row['carparks']*days_in_month
        occupied_capacity_days = occupied_days+occupied_parking_days
        available_capacity_days = available_days+available_parking_days
        loss += parking_loss
        units.append({**row, 'rooms':[{**r,'standard_rent':float(r['standard_rent'])} for r in row['rooms']],
                      'room_rows':room_rows, 'bedrooms':len(room_rows), 'occupied_room_days':occupied_days,
                      'available_room_days':available_days,
                      'occupied_parking_days':occupied_parking_days, 'available_parking_days':available_parking_days,
                      'occupied_capacity_days':occupied_capacity_days, 'available_capacity_days':available_capacity_days,
                      'occupancy_rate':round(100*occupied_capacity_days/available_capacity_days,2),
                      'vacancy_loss':float(loss), 'potential_room_rent':float(potential), 'expected_income':float(expected),
                      'parking_rate_missing':missing_rate, 'parking_over_capacity':over_capacity})
    occupied = sum(unit['occupied_capacity_days'] for unit in units)
    available = sum(unit['available_capacity_days'] for unit in units)
    return {'units':sorted(units,key=lambda u:u['unit'].casefold()), 'total_bedrooms':sum(u['bedrooms'] for u in units),
            'total_carparks':sum(u['carparks'] for u in units), 'occupancy_rate':round(100*occupied/available,2) if available else None,
            'occupied_capacity_days':occupied, 'available_capacity_days':available,
            'occupied_room_days':sum(u['occupied_room_days'] for u in units),
            'available_room_days':sum(u['available_room_days'] for u in units),
            'occupied_parking_days':sum(u['occupied_parking_days'] for u in units),
            'available_parking_days':sum(u['available_parking_days'] for u in units),
            'vacancy_loss':float(sum((Decimal(str(u['vacancy_loss'])) for u in units),Decimal('0'))),
            'parking_rate_missing_units':sum(u['parking_rate_missing'] for u in units),
            'unlinked_rentals':sum(row['id'] not in linked for row in rentals)}


@router.get('/units')
def list_units():
    return {'units':[row for row in records() if row['kind']=='unit']}


@router.post('/units')
def add_unit(value: PropertyUnit):
    return mutate('unit',unit_key(value.unit),value.model_dump(mode='json'))


@router.put('/units/{identifier}')
def update_unit(identifier: str, value: PropertyUpdate):
    if unit_key(value.unit) != identifier:
        raise HTTPException(422, 'The unit number cannot be changed. Add a different property instead.')
    return mutate('unit',identifier,value.model_dump(mode='json',exclude={'revision'}),value.revision)


@router.get('')
def dashboard(month: Annotated[str, Query(pattern=r'^(?:19|[2-9]\d)\d{2}-(?:0[1-9]|1[0-2])$')]):
    return project(records(), month)


@router.post('/rooms')
def add_room(value: Rental):
    return mutate('room', room_key(value.unit, value.room), value.model_dump(mode='json'))


@router.put('/rooms/{identifier}')
def update_room(identifier: str, value: RentalUpdate):
    destination = room_key(value.unit, value.room)
    return mutate('room', identifier, rental_update_payload(value, identifier, 'room'), value.revision, destination=destination)


def rental_update_payload(value, identifier, kind):
    payload = value.model_dump(mode='json', exclude={'revision'})
    fields = ('security_deposit','access_deposit') if kind=='room' else ('carpark_deposit',)
    missing = [name for name in fields if name not in value.model_fields_set]
    if missing:
        # Older open clients omit these fields. Preserve them; revisions still protect the write.
        old = next((row for row in records() if row['kind']==kind and row['id']==identifier), {})
        for name in missing:
            payload[name] = old.get(name)
    return payload


@router.post('/expenses')
def add_expense(value: Expense):
    return mutate('expense', uuid.uuid4().hex, value.model_dump(mode='json'))


@router.post('/parking')
def add_parking(value: ParkingRental):
    return mutate('parking', parking_key(value.unit, value.space), value.model_dump(mode='json'))


@router.put('/parking/{identifier}')
def update_parking(identifier: str, value: ParkingUpdate):
    return mutate('parking', identifier, rental_update_payload(value, identifier, 'parking'), value.revision,
                  destination=parking_key(value.unit, value.space))


@router.put('/expenses/{identifier}')
def update_expense(identifier: str, value: ExpenseUpdate):
    return mutate('expense', identifier, value.model_dump(mode='json', exclude={'revision'}), value.revision)


@router.delete('/{collection}/{identifier}')
def remove_record(collection: str, identifier: str, revision: Annotated[str, Query(min_length=1, max_length=40)]):
    if collection not in ('rooms', 'parking', 'expenses', 'units'):
        raise HTTPException(404, 'Not found')
    return mutate({'rooms':'room','parking':'parking','expenses':'expense','units':'unit'}[collection], identifier, expected=revision, delete=True)
