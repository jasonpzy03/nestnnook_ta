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

    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date and self.last_rental_date and self.last_rental_date < self.start_date:
            raise ValueError('Last rental day must be on or after the move-in date.')
        return self


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
            model = Rental if row['kind'] == 'room' else Expense if row['kind'] == 'expense' else None
            if model is None or not isinstance(row['id'], str) or not isinstance(row['revision'], str):
                raise ValueError()
            model.model_validate({k:v for k,v in row.items() if k not in ('id','kind','revision')})
        return data
    except (StorageError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Rental portfolio is unavailable. Please try again.') from None


def mutate(kind, identifier, payload=None, expected=None, delete=False):
    """Compare revisions atomically, so re-sharing cannot duplicate or overwrite a room silently."""
    field = kind+':'+identifier
    record = None if delete else {**payload, 'kind':kind, 'id':identifier, 'revision':uuid.uuid4().hex}
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
            if ARGV[3]=='delete' then redis.call('HDEL',KEYS[1],ARGV[1])
            else redis.call('HSET',KEYS[1],ARGV[1],ARGV[4]) end
            return {200,''}"""
            code, old = store.command('EVAL', script, 1, store.key('portfolio'), field,
                                      expected or '', 'delete' if delete else 'save', json.dumps(record))
            old = json.loads(old) if old else None
        else:
            with LOCK:
                data = read_local()
                old = data.get(field)
                code = (409 if old else 422 if len(data)>=2000 else 200) if expected is None else (
                    404 if not old else 409 if old['revision'] != expected else 200)
                if code == 200:
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
        else:
            amount = Decimal(str(row['amount']))
            total_expenses += amount
            expenses.append({**row, 'amount':float(amount)})
    return {'month':month, 'rooms':sorted(rooms, key=lambda r:(r['unit'].casefold(),r['room'].casefold())),
            'expenses':sorted(expenses, key=lambda e:e['name'].casefold()),
            'rental_income':float(total_rent), 'fixed_expenses':float(total_expenses),
            'net_income':float(total_rent-total_expenses), 'earning_rooms':sum(r['rental_days']>0 for r in rooms)}


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
    if collection not in ('rooms', 'expenses'):
        raise HTTPException(404, 'Not found')
    return mutate('room' if collection == 'rooms' else 'expense', identifier, expected=revision, delete=True)
