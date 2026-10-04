from datetime import date
import builtins
import re
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
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
    aircon_kwh: int = Field(default=40, ge=0, le=100000, strict=True)
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
    makeup_table_drawer: Literal['not_applicable','with','without'] = 'not_applicable'
    meter_reading: Text = ''
    inventory: list[InventoryItem] = Field(default_factory=list,max_length=30)
    include_aml: bool = True
    company: Company = Field(default_factory=Company)
    @model_validator(mode='after')
    def dates(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError('Expiry date must be on or after the commencement date.')
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
    documents: list[Literal['tenancy','rules','move_in','offer']] = Field(min_length=1,max_length=4)
    format: Literal['pdf','source','docx'] = 'pdf'
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.documents))!=len(self.documents): raise ValueError('Select each document only once.')
        needed = []
        if any(kind in self.documents for kind in ('tenancy','offer')):
            needed = ['tenant_name','tenant_id','property','room','address','agreement_date','start_date','end_date']
        elif 'move_in' in self.documents:
            needed = ['tenant_name','tenant_id','agreement_date']
        missing = [key for key in needed if not getattr(self.details,key)]
        if missing: raise ValueError('Required details: '+', '.join(missing))
        return self
