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


class Rental(StrictModel):
    unit: Label
    room: Label
    rent: Money
    parking: Money = Decimal('0')
    start_date: date | None = None
    last_rental_date: date | None = None
    active: bool = True
    tenant_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ''

    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date and self.last_rental_date and self.last_rental_date < self.start_date:
            raise ValueError('Last rental day must be on or after the move-in date.')
        return self


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
    # None means not entered; [] explicitly confirms no other expenses.
    others: list[OtherCost] | None = Field(default=None, max_length=50)


Month = Annotated[str, StringConstraints(pattern=r'^(?:19|[2-9]\d)\d{2}-(?:0[1-9]|1[0-2])$')]


class PropertyUnit(StrictModel):
    unit: Label
    property_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ''
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ''
    bathrooms: int = Field(default=0, ge=0, le=30)
    carparks: int = Field(default=0, ge=0, le=100)
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
            model = {'room':Rental,'expense':Expense,'unit':PropertyUnit}.get(row['kind'])
            if model is None or not isinstance(row['id'], str) or not isinstance(row['revision'], str):
                raise ValueError()
            model.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision','room_ids')})
        return data
    except (StorageError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Rental portfolio is unavailable. Please try again.') from None


def mutate(kind, identifier, payload=None, expected=None, delete=False):
    """Compare revisions atomically, so re-sharing cannot duplicate or overwrite a room silently."""
    field = kind+':'+identifier
    record = None if delete else {**payload, 'kind':kind, 'id':identifier, 'revision':uuid.uuid4().hex}
    if record and kind == 'unit':
        record['room_ids'] = [room_key(payload['unit'], room['room']) for room in payload['rooms']]
    unit_field = 'unit:'+unit_key(payload['unit']) if payload and kind == 'room' else ''
    try:
        if cloud_enabled():
            store = RedisStore()
            script = """local old=redis.call('HGET',KEYS[1],ARGV[1])
            if ARGV[2]=='' then
                if old then return {409,old} end
                if redis.call('HLEN',KEYS[1])>=2000 then return {422,''} end
            else
                if not old then return {404,''} end
                if cjson.decode(old).revision~=ARGV[2] then return {409,old} end
            end
            if ARGV[5]=='room' and ARGV[3]~='delete' then
                local unit=redis.call('HGET',KEYS[1],ARGV[6])
                if unit then
                    local found=false
                    for _,id in ipairs(cjson.decode(unit).room_ids) do if id==ARGV[7] then found=true end end
                    if not found then return {423,''} end
                end
            end
            if ARGV[5]=='unit' and old then
                local keep={}
                if ARGV[3]~='delete' then for _,id in ipairs(cjson.decode(ARGV[4]).room_ids) do keep[id]=true end end
                for _,id in ipairs(cjson.decode(old).room_ids) do
                    if not keep[id] and redis.call('HEXISTS',KEYS[1],'room:'..id)==1 then return {424,''} end
                end
            end
            if ARGV[3]=='delete' then redis.call('HDEL',KEYS[1],ARGV[1])
            else redis.call('HSET',KEYS[1],ARGV[1],ARGV[4]) end
            return {200,''}"""
            code, old = store.command('EVAL', script, 1, store.key('portfolio'), field,
                                      expected or '', 'delete' if delete else 'save', json.dumps(record), kind, unit_field, identifier)
            old = json.loads(old) if old else None
        else:
            with LOCK:
                data = read_local()
                old = data.get(field)
                code = (409 if old else 422 if len(data)>=2000 else 200) if expected is None else (
                    404 if not old else 409 if old['revision'] != expected else 200)
                if code == 200:
                    if kind == 'room' and not delete and unit_field in data and identifier not in data[unit_field]['room_ids']:
                        raise HTTPException(422, 'This room is not in the property inventory. Add the room to the unit first.')
                    if kind == 'unit' and old:
                        removed = set(old['room_ids']) - set(record['room_ids'] if record else [])
                        if any('room:'+key in data for key in removed):
                            raise HTTPException(422, 'Remove linked rental records before removing their rooms or property.')
                    if delete:
                        data.pop(field)
                    else:
                        data[field] = record
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
    rooms, expenses = [], []
    total_rent = Decimal('0')
    total_expenses = Decimal('0')
    for row in data:
        if row['kind'] == 'room':
            rental = Rental.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision')})
            start, end = max(first, rental.start_date or first), min(last, rental.last_rental_date or last)
            days = max(0, (end-start).days+1) if rental.active else 0
            # Match the document's pro-rated room rent; round each charge to cents.
            expected = money(rental.rent*days/last.day) + money(rental.parking*days/last.day)
            rooms.append({**row, 'rent':float(rental.rent), 'parking':float(rental.parking), 'rental_days':days, 'expected':float(expected)})
            total_rent += expected
        elif row['kind'] == 'expense':
            amount = Decimal(str(row['amount']))
            total_expenses += amount
            expenses.append({**row, 'amount':float(amount)})
    occupancy = occupancy_projection(data, rooms, last.day)
    variable_total = Decimal('0')
    for unit in occupancy['units']:
        costs = property_costs(unit, month)
        unit.update(costs)
        unit['net_income'] = float(Decimal(str(unit['expected_income']))-Decimal(str(costs['total_expenses'])))
        total_expenses += Decimal(str(costs['fixed_expenses']))
        variable_total += Decimal(str(costs['variable_expenses']))
    return {**occupancy, 'month':month, 'rooms':sorted(rooms, key=lambda r:(r['unit'].casefold(),r['room'].casefold())),
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
    variable_total += sum((item.amount for item in monthly.others or []), Decimal('0'))
    return {'fixed_costs':fixed.model_dump(mode='json'), 'selected_month_costs':monthly.model_dump(mode='json'),
            'fixed_expenses':float(fixed_total), 'variable_expenses':float(variable_total),
            'total_expenses':float(fixed_total+variable_total),
            'missing_expenses':[name for name in ('electricity','water','others') if getattr(monthly,name) is None]}


def occupancy_projection(data, rentals, days_in_month):
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
        units.append({**row, 'rooms':[{**r,'standard_rent':float(r['standard_rent'])} for r in row['rooms']],
                      'room_rows':room_rows, 'bedrooms':len(room_rows), 'occupied_room_days':occupied_days,
                      'available_room_days':available_days, 'occupancy_rate':round(100*occupied_days/available_days,2),
                      'vacancy_loss':float(loss), 'potential_room_rent':float(potential), 'expected_income':float(expected)})
    occupied = sum(unit['occupied_room_days'] for unit in units)
    available = sum(unit['available_room_days'] for unit in units)
    return {'units':sorted(units,key=lambda u:u['unit'].casefold()), 'total_bedrooms':sum(u['bedrooms'] for u in units),
            'total_carparks':sum(u['carparks'] for u in units), 'occupancy_rate':round(100*occupied/available,2) if available else None,
            'occupied_room_days':occupied, 'available_room_days':available,
            'vacancy_loss':float(sum((Decimal(str(u['vacancy_loss'])) for u in units),Decimal('0'))),
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
    if room_key(value.unit, value.room) != identifier:
        raise HTTPException(422, 'Unit and room identify this rental and cannot be changed. Add a different room instead.')
    return mutate('room', identifier, value.model_dump(mode='json', exclude={'revision'}), value.revision)


@router.post('/expenses')
def add_expense(value: Expense):
    return mutate('expense', uuid.uuid4().hex, value.model_dump(mode='json'))


@router.put('/expenses/{identifier}')
def update_expense(identifier: str, value: ExpenseUpdate):
    return mutate('expense', identifier, value.model_dump(mode='json', exclude={'revision'}), value.revision)


@router.delete('/{collection}/{identifier}')
def remove_record(collection: str, identifier: str, revision: Annotated[str, Query(min_length=1, max_length=40)]):
    if collection not in ('rooms', 'expenses', 'units'):
        raise HTTPException(404, 'Not found')
    return mutate({'rooms':'room','expenses':'expense','units':'unit'}[collection], identifier, expected=revision, delete=True)
