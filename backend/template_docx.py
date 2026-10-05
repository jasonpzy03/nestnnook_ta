"""Fill existing OOXML text slots without recreating paragraphs, tables or styles."""
from copy import deepcopy
from datetime import timedelta, date
from calendar import monthrange
from io import BytesIO
from pathlib import Path
import posixpath
from zipfile import ZipFile
from lxml import etree as E
from .models import Details

ROOT=Path(__file__).resolve().parents[1]
SOURCES={'move_in':'1. Move in Form - quantity.docx','rules':'2. House Rules.docx','ac':'3. Room TA_AC.docx','noac':'3. Room TA_NOAC.docx','carpark':'Car Park Rental Agreement.docx'}
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','v':'urn:schemas-microsoft-com:vml','mc':'http://schemas.openxmlformats.org/markup-compatibility/2006'}
W='{'+NS['w']+'}'
XML_SPACE='{http://www.w3.org/XML/1998/namespace}space'
class TemplateError(ValueError):pass

def header_parts(archive,root):
    """Resolve referenced headers through OOXML relationships; Word renames parts on save."""
    rel_ns='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    ids={ref.get('{'+rel_ns+'}id') for ref in root.xpath('//w:headerReference',namespaces=NS)}
    relationships=E.fromstring(archive.read('word/_rels/document.xml.rels'))
    parts={}
    for rel in relationships:
        if rel.get('Id') not in ids or not rel.get('Type','').endswith('/header'):continue
        if rel.get('TargetMode')=='External':raise TemplateError('External Word headers are not supported.')
        target=rel.get('Target','')
        name=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('word',target))
        if not name.startswith('word/') or name not in archive.namelist():
            raise TemplateError('A referenced Word header is missing from the template.')
        parts[name]=E.fromstring(archive.read(name))
    return parts

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
    from .placeholders import fields_for,fill_package
    if kind=='offer':
        from .offer_docx import fill_offer_docx
        return fill_offer_docx(d)
    key=('ac' if d.aircon else 'noac') if kind=='tenancy' else kind
    if key not in SOURCES:raise TemplateError('Unknown document template.')
    source=(ROOT/'agreements'/SOURCES[key]).read_bytes()
    return fill_package(source,fields_for(kind,d))
