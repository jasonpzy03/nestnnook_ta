from datetime import date
import builtins
import re
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Required = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, le=1000000, max_digits=12, decimal_places=2)]
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Company(StrictModel):
    name: Required = 'NEST & NOOK PROPERTY CARE'
    registration: Required = '202603156166 (KT0615852-M)'
    address: Required = '#16-03, Trellis Residences, 80100, J.B, Johor.'
    contact: Required = 'Cheryl Pua'
    phone: Required = '+60111-3380335'
    email: Required = 'pzhenying@gmail.com'
    bank: Required = 'OCBC BANK'
    account_name: Required = 'NEST & NOOK PROPERTY CARE'
    account_number: Required = '7101403930'
class InventoryItem(StrictModel):
    name: Required
    quantity: int = Field(default=1,ge=0,le=100)
    condition: Literal['Not supplied','Good','Fair','Damaged'] = 'Good'
    remarks: Text = ''
    @field_validator('name')
    @classmethod
    def migrate_table_name(cls, value):
        return 'Study table' if value == 'Makeup table' else value
class Details(StrictModel):
    tenant_name: Text = ''
    tenant_id: Text = ''
    nationality: Text = ''
    phone: Text = ''
    email: Text = ''
    occupation: Text = ''
    employer: Text = ''
    vehicle: Text = ''
    emergency_name: Text = ''
    emergency_id: Text = ''
    emergency_relationship: Text = ''
    emergency_phone: Text = ''
    guardian_name: Text = ''
    guardian_id: Text = ''
    property: Text = ''
    room: Text = ''
    address: Annotated[str, StringConstraints(strip_whitespace=True,max_length=600)] = ''
    agreement_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    aircon: bool = True
    tenancy_type: Literal['new','renewal'] = 'new'
    aircon_kwh: Decimal = Field(default=Decimal('40'), ge=0, le=100000, allow_inf_nan=False)
    rent: Money = Decimal('0')
    parking: Money = Decimal('0')
    security_deposit: Money = Decimal('0')
    access_deposit: Money = Decimal('0')
    advance_rent: Money = Decimal('0')
    agreement_fee: Money = Decimal('0')
    reference: Text = ''
    special_conditions: Annotated[str, StringConstraints(strip_whitespace=True,max_length=3000)] = ''
    room_condition: Text = ''
    room_remarks: Text = ''
    meter_reading: Text = ''
    inventory: list[InventoryItem] = Field(default_factory=list,max_length=30)
    include_aml: bool = True
    company: Company = Field(default_factory=Company)
    carpark_lot: Text = ''
    carpark_address: Annotated[str, StringConstraints(strip_whitespace=True,max_length=600)] = ''
    carpark_agreement_date: date | None = None
    carpark_start_date: date | None = None
    carpark_end_date: date | None = None
    carpark_rent: Money = Decimal('300')
    carpark_deposit: Money = Decimal('0')
    carpark_earnest_deposit: Money = Decimal('0')
    @model_validator(mode='before')
    @classmethod
    def discard_legacy_drawer(cls, value):
        if isinstance(value, dict) and 'makeup_table_drawer' in value:
            value = {key: item for key, item in value.items() if key != 'makeup_table_drawer'}
        return value
    @model_validator(mode='after')
    def dates(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError('Expiry date must be on or after the commencement date.')
        days = monthrange(self.start_date.year, self.start_date.month)[1] if self.start_date else 0
        self.advance_rent = ((self.rent * (days - self.start_date.day + 1) / days)
                             .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if days else Decimal('0')
        if self.carpark_end_date and self.carpark_start_date and self.carpark_end_date < self.carpark_start_date:
            raise ValueError('Car park expiry date must be on or after its commencement date.')
        days = monthrange(self.carpark_start_date.year, self.carpark_start_date.month)[1] if self.carpark_start_date else 0
        self.carpark_earnest_deposit = ((self.carpark_rent * (days-self.carpark_start_date.day+1)/days)
                                      .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if days else Decimal('0')
        return self
    @builtins.property
    def property_address(self):
        address=self.address.strip();unit=self.property.strip()
        if not unit:return address
        if not address:return unit
        # Recognise existing unit prefixes without mistaking 16-030 for 16-03.
        bare=re.sub(r'^(?:unit\s+|no\.?\s+)?#?\s*','',unit,flags=re.I)
        prefix=r'^(?:unit\s+|no\.?\s+)?#?\s*'+re.escape(bare)+r'(?=$|[\s,;])'
        if bare and re.match(prefix,address,flags=re.I):return address
        return f'{unit}, {address}'

    @builtins.property
    def total(self):
        return sum((self.security_deposit,self.access_deposit,self.advance_rent,self.agreement_fee),Decimal('0'))
class GenerateRequest(StrictModel):
    details: Details
    documents: list[Literal['tenancy','rules','move_in','offer','carpark']] = Field(min_length=1,max_length=5)
    format: Literal['pdf','source','docx'] = 'pdf'
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.documents))!=len(self.documents): raise ValueError('Select each document only once.')
        needed = []
        if any(kind in self.documents for kind in ('tenancy','offer')):
            needed = ['tenant_name','tenant_id','property','room','address','agreement_date','start_date','end_date']
        elif 'move_in' in self.documents:
            needed = ['tenant_name','tenant_id','agreement_date']
        if 'carpark' in self.documents:
            needed += ['tenant_name','tenant_id','carpark_lot','carpark_address','carpark_agreement_date','carpark_start_date','carpark_end_date']
        missing = [key for key in needed if not getattr(self.details,key)]
        if missing: raise ValueError('Required details: '+', '.join(missing))
        return self
