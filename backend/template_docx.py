"""Fill existing OOXML text slots without recreating paragraphs, tables or styles."""
from copy import deepcopy
from datetime import timedelta, date
from calendar import monthrange
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from .models import Details

ROOT=Path(__file__).resolve().parents[1]
SOURCES={'move_in':'1. Move in Form - quantity.docx','rules':'2. House Rules.docx','ac':'3. Room TA_AC.docx','noac':'3. Room TA_NOAC.docx'}
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','v':'urn:schemas-microsoft-com:vml','mc':'http://schemas.openxmlformats.org/markup-compatibility/2006'}
W='{'+NS['w']+'}'
XML_SPACE='{http://www.w3.org/XML/1998/namespace}space'
class TemplateError(ValueError):pass

def text(node):return ''.join(node.xpath('.//w:t/text()',namespaces=NS))
def put(node,value):
    """Retain all run/paragraph/cell properties and existing empty runs."""
    value=str(value) if value is not None and str(value).strip() else '-'
    nodes=node.xpath('.//w:t',namespaces=NS)
    if not nodes:
        p=node if node.tag==W+'p' else node.find('w:p',NS)
        if p is None:raise TemplateError('Missing paragraph in template slot.')
        run=E.SubElement(p,W+'r')
        fmt=p.find('w:pPr/w:rPr',NS)
        if fmt is not None:run.append(deepcopy(fmt))
        nodes=[E.SubElement(run,W+'t')]
    nodes[0].text=value;nodes[0].set(XML_SPACE,'preserve')
    for n in nodes[1:]:n.text=''

def replace(node,old,new):
    """Replace across split runs; retain surrounding labels, tabs, and formatting."""
    if old==new:return
    for p in node.xpath('.//w:p',namespaces=NS):
        nodes=p.xpath('./w:r/w:t',namespaces=NS)
        full=''.join(n.text or '' for n in nodes)
        # Right-to-left keeps offsets stable, including repeated dates on a signature line.
        starts=[];at=0
        while (at:=full.find(old,at))>=0:starts.append(at);at+=len(old)
        for start in reversed(starts):
            pos=0;inserted=False
            for n in nodes:
                raw=n.text or '';end=pos+len(raw)
                if end>start and pos<start+len(old):
                    left=max(0,start-pos);right=min(len(raw),start+len(old)-pos)
                    n.text=raw[:left]+(new if not inserted else '')+raw[right:]
                    n.set(XML_SPACE,'preserve');inserted=True
                pos=end

def cell(table,row,col):return table.findall('w:tr',NS)[row].findall('w:tc',NS)[col]
def date_text(d,upper=False):
    value=f'{d.day} {d.strftime("%B %Y")}'
    return value.upper() if upper else value

def tenure(d):
    months=(d.end_date.year-d.start_date.year)*12+d.end_date.month-d.start_date.month
    if d.end_date.day>=d.start_date.day:months+=1
    if months>0:
        year,month=divmod(d.start_date.year*12+d.start_date.month-1+months,12)
        month+=1
        last=monthrange(year,month)[1]
        expected=date(year,month,min(d.start_date.day,last))
        if d.start_date.day<=last:expected-=timedelta(days=1)
        if expected==d.end_date:
            if months%12==0:return f'{months//12} Year'+('s' if months!=12 else '')
            return f'{months} Months'
    return f'{(d.end_date-d.start_date).days+1} Days'
def amount(v,zero='-'):return f'RM{v:,.2f}' if v else zero

INVENTORY_NAMES=['Bedframe / Divan','Mattress','Pillow','Makeup table','Chair','Plant decor','Curtain','Wardrobe','Wall decor frame','Rubbish bin','Blanket','Mattress cover','Air conditioner','Air conditioner remote','Ceiling fan','Fan remote','Access card','Room key','Main door key']

def fill_docx(kind,d:Details):
    key=('ac' if d.aircon else 'noac') if kind=='tenancy' else kind
    if key not in SOURCES:raise TemplateError('The offer letter is a PDF template and remains PDF.')
    original=ROOT/'agreements'/SOURCES[key]
    with ZipFile(original) as archive:
        root=E.fromstring(archive.read('word/document.xml'))
        body=root.find('w:body',NS);tables=body.findall('w:tbl',NS)
        if kind=='tenancy':
            values={
                'Date':date_text(d.agreement_date,d.aircon),'Room Type':f'{d.room} {d.property}',
                'Address':d.property_address,'Commencement Date':date_text(d.start_date,d.aircon),
                'Expiry Date':date_text(d.end_date,d.aircon),'Tenure':tenure(d),
                'Rental':amount(d.rent),'Car Park Rental':amount(d.parking),
                'Room Deposit':amount(d.security_deposit),'Access Card Deposit':amount(d.access_deposit),
                'Earnest Deposit (the Earnest Deposit shall form the 1st month Rental)':amount(d.advance_rent),
                'Agreement Fee':amount(d.agreement_fee),
            }
            for row in tables[0].findall('w:tr',NS):
                cells=row.findall('w:tc',NS);label=text(cells[0]).strip()
                if label not in values:raise TemplateError(f'Unmapped tenancy template field: {label}')
                put(cells[1],values[label])
                if label=='Room Deposit':put(cells[0],'Refundable Room Deposit')
                elif label=='Access Card Deposit':put(cells[0],'Refundable Access Card Deposit')
            for row,val in enumerate([d.company.account_name,d.company.bank,d.company.account_number]):put(cell(tables[1],row,1),val)
            put(cell(tables[2],2,0),'Name: '+d.tenant_name)
            put(cell(tables[2],3,0),('IC No.: ' if d.aircon else 'Passport No.: ')+d.tenant_id)
            put(cell(tables[2],2,1),'Name: '+d.company.name)
            put(cell(tables[2],3,1),'SSM No.: '+d.company.registration)
            for col in (0,1):put(cell(tables[2],4,col),'Date: '+date_text(d.agreement_date,d.aircon))
            # Original guardian section stays in place, even when left blank.
            if d.guardian_name:
                put(cell(tables[3],2,0),'Name: '+d.guardian_name)
                put(cell(tables[3],3,0),'IC: '+(d.guardian_id or '-'))
                put(cell(tables[3],4,0),'Date: '+date_text(d.agreement_date,d.aircon))
            else:
                for row,label in [(2,'Name: '),(3,'IC: '),(4,'Date: ')]:put(cell(tables[3],row,0),label+'-')
            if d.company.name != 'NEST & NOOK PROPERTY CARE':
                replace(root,'Nest & Nook Property Care',d.company.name)
            replace(root,'NEST & NOOK PROPERTY CARE',d.company.name)
            replace(root,'PUA ZHEN YING',d.company.name)
        elif kind=='rules':
            replace(root,'DI CHIA SENG',d.tenant_name or '-');replace(root,'961004-01-5879',d.tenant_id or '-')
            # The rules and their existing operational contacts are not rewritten.
        elif kind=='move_in':
            for row,col,val in [(0,1,d.tenant_name),(0,3,d.tenant_id),(1,1,d.nationality),(1,3,d.phone),(2,1,d.email),(2,3,d.occupation),(3,1,d.employer),(3,3,d.vehicle)]:put(cell(tables[0],row,col),val)
            for row,col,val in [(0,1,d.emergency_name),(0,3,d.emergency_id),(1,1,d.emergency_relationship),(1,3,d.emergency_phone)]:put(cell(tables[1],row,col),val)
            items={i.name:i for i in d.inventory}
            unknown=set(items)-set(INVENTORY_NAMES)
            if unknown:raise TemplateError('The move-in template has no row for: '+', '.join(sorted(unknown)))
            # Update both DrawingML and legacy VML copies of each text box.
            for box in root.xpath('//w:txbxContent',namespaces=NS):
                table=box.find('w:tbl',NS)
                if table is None:continue
                put(cell(table,1,1),'-')
                put(cell(table,1,2),'YES' if d.room_condition.lower()=='good' else 'NO' if d.room_condition else '-')
                put(cell(table,1,3),'YES' if d.room_condition.lower()=='damaged' else '-')
                room_notes=d.room_remarks or (d.room_condition if d.room_condition.lower() not in ('good','damaged') else '')
                put(cell(table,1,4),room_notes)
                for row,name in enumerate(INVENTORY_NAMES,2):
                    item=items.get(name);qty=item.quantity if item else 1;condition=item.condition if item else 'Good'
                    supplied=qty>0 and condition!='Not supplied'
                    put(cell(table,row,1),str(qty) if supplied else '-')
                    put(cell(table,row,2),'YES' if supplied and condition=='Good' else 'NO' if supplied else '-')
                    put(cell(table,row,3),'YES' if supplied and condition=='Damaged' else '-')
                    notes=item.remarks if item else ''
                    if supplied and condition=='Fair':notes='Fair'+(': '+notes if notes else '')
                    put(cell(table,row,4),notes)
                for col in (1,2,3):put(cell(table,21,col),'-')
                put(cell(table,21,4),d.meter_reading)
            for old,new in [('DI CHIA SENG',d.tenant_name),('961004-01-5879',d.tenant_id),('1 JULY 2026',date_text(d.agreement_date,True)),('NEST & NOOK PROPERTY CARE',d.company.name),('202603156166 (KT0615852-M)',d.company.registration),('7101403930',d.company.account_number),('OCBC BANK',d.company.bank)]:replace(root,old,new)
            # Bank beneficiary is independently editable from the company legal name.
            for box in root.xpath('//w:txbxContent',namespaces=NS):
                if box.find('w:tbl',NS) is None:replace(box,d.company.name,d.company.account_name)
            # The sample's diagonal mark selects 'without drawer'. It is field data, not decoration.
            for drawing in list(root.xpath('//w:drawing[.//a:prstGeom[@prst="line"]]',namespaces=NS)):
                if d.makeup_table_drawer=='not_applicable':
                    parent=drawing.getparent()
                    if parent.getparent().tag=='{'+NS['mc']+'}Choice':parent.getparent().getparent().getparent().remove(parent.getparent().getparent())
                    else:parent.remove(drawing)
                elif d.makeup_table_drawer=='with':
                    offset=drawing.find('wp:anchor/wp:positionV/wp:posOffset',NS)
                    offset.text=str(int(offset.text)-141605)
            # Legacy fallback line, if present, must not retain the sample's selection.
            for line in list(root.xpath('//v:line',namespaces=NS)):
                if d.makeup_table_drawer=='not_applicable':line.getparent().remove(line)
        updated=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        out=BytesIO()
        with ZipFile(out,'w') as result:
            for info in archive.infolist():
                data=updated if info.filename=='word/document.xml' else archive.read(info.filename)
                if info.filename=='word/nest-header.xml':
                    header=E.fromstring(data)
                    for mark in header.xpath('//w:bookmarkStart',namespaces=NS):
                        name=mark.get(W+'name','')
                        if name.startswith('NestHeader_'):
                            field=name.removeprefix('NestHeader_')
                            put(mark.getparent(),('TEL NO.: ' if field=='phone' else '')+getattr(d.company,field))
                    data=E.tostring(header,xml_declaration=True,encoding='UTF-8',standalone=True)
                result.writestr(info,data)
        return out.getvalue()
