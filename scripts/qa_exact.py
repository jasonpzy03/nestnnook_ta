from pathlib import Path
from backend.models import Details
from backend.template_docx import fill_docx,INVENTORY_NAMES
from backend.template_pdf import fill_offer
import pymupdf as f
p=Path('tmp/exact-qa');p.mkdir(parents=True,exist_ok=True)
d=Details(tenant_name='ALEX TAN',tenant_id='TEST-P12345',phone='+60 12-3456789',email='alex@example.test',nationality='MALAYSIAN',occupation='Software Engineer',property='Unit A7-1-2404',room='Room 06',address='Unit A7-1-2404, R&F Princess Cove, Jalan Tanjung Puteri, 1, R&F, Tanjung Puteri, 80300, Johor Bahru, Johor.',agreement_date='2026-10-01',start_date='2026-10-01',end_date='2027-09-30',rent=1200,security_deposit=1200,advance_rent=1200,access_deposit=150,room_condition='Good',room_remarks='Light scuffs near door',meter_reading='125.40',inventory=[dict(name=n,quantity=1,condition='Good',remarks='CARD-123' if n=='Access card' else '') for n in INVENTORY_NAMES],reference='NN-2026-001')
for kind in ['tenancy','rules','move_in']:
 (p/f'{kind}.docx').write_bytes(fill_docx(kind,d))
d.aircon=False;(p/'tenancy-noac.docx').write_bytes(fill_docx('tenancy',d))
data=fill_offer(d);(p/'offer.pdf').write_bytes(data)
for i,pg in enumerate(f.open(stream=data,filetype='pdf')):pg.get_pixmap(matrix=f.Matrix(1.5,1.5)).save(str(p/f'offer-{i+1}.png'))
print('Wrote template QA documents')
