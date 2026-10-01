"""Shared address options stored separately from tenant form data."""
import json
from pathlib import Path
from threading import Lock
from typing import Annotated
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,StringConstraints,ConfigDict
from .cloud_store import RedisStore, StorageError, cloud_enabled
router=APIRouter()
FILE=Path(__file__).resolve().parents[1]/'.local/addresses.json'
LOCK=Lock()
class AddressInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    address:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=600)]
def read_addresses():
    if not FILE.exists():return []
    try:
        data=json.loads(FILE.read_text(encoding='utf-8'))
        if not isinstance(data,list) or any(not isinstance(a,str) for a in data):raise ValueError()
        return data
    except (ValueError,OSError):raise HTTPException(503,'Saved addresses could not be read. Contact the host administrator.')
@router.get('/api/addresses')
def list_addresses():
    if cloud_enabled():
        try:return {'addresses':RedisStore().addresses()}
        except StorageError:raise HTTPException(503,'Saved addresses are temporarily unavailable.')
    with LOCK:return {'addresses':read_addresses()}
@router.post('/api/addresses')
def add_address(value:AddressInput):
    if cloud_enabled():
        try:
            store=RedisStore();selected=store.add_address(value.address)
            if not selected:raise HTTPException(422,'The saved address list is full.')
            return {'addresses':store.addresses(),'selected':selected}
        except StorageError:raise HTTPException(503,'Address storage is temporarily unavailable. Try again later.')
    with LOCK:
        addresses=read_addresses()
        match=next((a for a in addresses if a.casefold()==value.address.casefold()),None)
        if not match:
            if len(addresses)>=500:raise HTTPException(422,'The saved address list is full.')
            addresses.append(value.address)
            FILE.parent.mkdir(parents=True,exist_ok=True)
            temporary=FILE.with_suffix('.tmp')
            try:
                temporary.write_text(json.dumps(addresses,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(FILE)
            except OSError:raise HTTPException(503,'Address could not be saved. Try again or contact the host administrator.')
        return {'addresses':addresses,'selected':match or value.address}
