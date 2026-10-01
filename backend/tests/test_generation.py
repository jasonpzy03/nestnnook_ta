from io import BytesIO
from zipfile import ZipFile
import pytest
import pymupdf as fitz
from lxml import etree as E
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Details
from backend.template_docx import fill_docx, ROOT, SOURCES, NS
from backend.template_pdf import fill_offer
client=TestClient(app)
@pytest.fixture(autouse=True)
def staff_login(tmp_path, monkeypatch):
    from backend.main import auth
    from backend.auth import password_record
    import json
    config=tmp_path/'auth.json'
    config.write_text(json.dumps(password_record('test-staff-password')))
    monkeypatch.setattr(auth,'config',config)
    auth.sessions.clear();auth.attempts.clear();client.cookies.clear()
    assert client.post('/login',data={'password':'test-staff-password'},follow_redirects=False).status_code==303

@pytest.fixture
def details():
    return dict(tenant_name='Alex Tan',tenant_id='TEST-P12345',phone='+60 12-3456789',email='alex@example.test',property='Trellis Residences, 16-03',room='Room 2',address='16-03 Trellis Residences, Johor Bahru, Johor',agreement_date='2026-10-01',start_date='2026-10-10',end_date='2027-10-09',rent=1200,security_deposit=1200,access_deposit=150,advance_rent=800,agreement_fee=50,inventory=[dict(name='Access card',quantity=1,condition='Good',remarks='CARD-123')])
def xml(data):
    with ZipFile(BytesIO(data)) as z:return E.fromstring(z.read('word/document.xml'))
def text(data):
    if data.startswith(b'%PDF'):
        with fitz.open(stream=data,filetype='pdf') as doc:return '\n'.join(p.get_text() for p in doc).replace('\xa0',' ').replace('\xad','-')
    return ''.join(xml(data).xpath('//w:t/text()',namespaces=NS))
@pytest.mark.parametrize('aircon',[True,False])
def test_complete_source_pack(details,aircon):
    details['aircon']=aircon
    r=client.post('/api/generate',json={'details':details,'documents':['tenancy','rules','move_in','offer'],'format':'source'})
    assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    with ZipFile(BytesIO(r.content)) as z:
        assert len(z.namelist())==4
        assert f'Alex-Tan-tenancy-{"ac" if aircon else "noac"}.docx' in z.namelist()
        for name in z.namelist():
            t=text(z.read(name))
            for stale in ['DI CHIA SENG','TENG YING YING','HII HUI CHIN','Shamsunder','VANGUARD','Vanguard','VAC','CIM','1102047977','931205-06-5090','961004-01-5879','PCR0033666']:
                assert stale not in t,(name,stale)
            assert 'Alex Tan' in t and 'TEST-P12345' in t
            if 'offer' in name:assert name.endswith('.pdf') and 'RM2,200.00' in t
            if 'move_in' in name:assert t.count('CARD-123')==2
@pytest.mark.parametrize('kind,key',[('tenancy','ac'),('tenancy','noac'),('rules','rules'),('move_in','move_in')])
def test_original_structure_and_parts(details,kind,key):
    d=Details(**details);d.aircon=key!='noac'
    data=fill_docx(kind,d)
    with ZipFile(ROOT/'agreements'/SOURCES[key]) as original, ZipFile(BytesIO(data)) as filled:
        assert original.namelist()==filled.namelist()
        for name in original.namelist():
            if name!='word/document.xml':assert original.read(name)==filled.read(name),name
        before=E.fromstring(original.read('word/document.xml'));after=xml(data)
        for tag in ['sectPr','tblPr','trPr','tcPr','pPr']:
            def props(tree):return [E.tostring(n,method='c14n') for n in tree.xpath('//w:'+tag,namespaces=NS)]
            assert props(before)==props(after),tag
        assert len(before.xpath('//w:tbl',namespaces=NS))==len(after.xpath('//w:tbl',namespaces=NS))
        if kind in ('tenancy','rules'):
            # Every fixed body paragraph remains verbatim, except company substitutions.
            fixed=[''.join(p.xpath('.//w:t/text()',namespaces=NS)) for p in before.xpath('/w:document/w:body/w:p',namespaces=NS)]
            output=text(data)
            for line in fixed:
                if any(v in line for v in ['DI CHIA SENG','961004-01-5879','PUA ZHEN YING']):continue
                assert line in output,line
@pytest.mark.parametrize('include',[True,False])
def test_offer_original_pages_artwork(details,include):
    d=Details(**details);d.include_aml=include
    with fitz.open(stream=fill_offer(d),filetype='pdf') as result,fitz.open(ROOT/'agreements/letter of offer to rent.pdf') as original:
        assert len(result)==(3 if include else 2)
        for i,page in enumerate(result):
            assert page.rect==original[i].rect
            if i==2:assert [{k:v for k,v in x.items() if k!='seqno'} for x in page.get_drawings()]==[{k:v for k,v in x.items() if k!='seqno'} for x in original[i].get_drawings()]
            assert not any(im['width']==751 and im['height']==321 for im in page.get_image_info())
        assert ('decided to not provide' in ' '.join(p.get_text() for p in result))==include
@pytest.mark.parametrize('patch',[{'tenant_name':' '},{'end_date':'2026-01-01'},{'rent':-1},{'rent':'NaN'},{'rent':12.001},{'room':''},{'inventory':[{'name':'Key','quantity':-1}]}])
def test_validation(details,patch):
    details.update(patch)
    assert client.post('/api/generate',json={'details':details,'documents':['tenancy'],'format':'source'}).status_code==422
@pytest.mark.parametrize('docs',[[],['unknown'],['tenancy','tenancy']])
def test_invalid_documents(details,docs):
    assert client.post('/api/generate',json={'details':details,'documents':docs,'format':'source'}).status_code==422
def test_decimal_totals_and_escaping(details):
    details.update(tenant_name='A <B> & C',security_deposit='0.10',access_deposit='0.20',advance_rent=0,agreement_fee=0)
    t=text(fill_offer(Details(**details)));assert 'A <B> & C' in t and 'RM0.30' in t
def test_overflow_is_reported(details):
    details['special_conditions']='A long condition. '*100
    r=client.post('/api/generate',json={'details':details,'documents':['offer']})
    assert r.status_code==422 and 'too long for the original offer template' in r.json()['detail']
def test_word_failure_has_no_rebuilt_fallback(details,monkeypatch):
    from backend import renderers
    monkeypatch.setattr(renderers.os,'name','posix')
    with pytest.raises(ValueError,match='requires Microsoft Word'):renderers.word_pdf(b'')


def test_new_inventory_columns_and_dashes(details):
    d=Details(**details);d.phone='';d.parking=0
    r=xml(fill_docx('move_in',d))
    for table in r.xpath('//w:txbxContent/w:tbl',namespaces=NS):
        rows=table.findall('w:tr',NS)
        headers=[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in rows[0].findall('w:tc',NS)]
        assert headers==['Items','Qty','Good Condition','Broken','Remarks:']
        bed=[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in rows[2].findall('w:tc',NS)]
        assert bed[1:]==['1','YES','-','-']
    for kind in ['tenancy','move_in']:
        t=text(fill_docx(kind,d))
        assert 'NIL' not in t and '>NA<' not in t

def test_removed_offer_fees(details):
    t=text(fill_offer(Details(**details))).lower()
    for old in ['utilities deposit','room transfer','room-changing','other deposit','other charges']:
        assert old not in t,old
    for label in ['refundable room deposit','refundable access card deposit','agreement fee','7. tenant acknowledgement']:
        assert label in t


@pytest.mark.parametrize('start,end,wanted', [('2026-10-01','2027-03-31','6 Months'),('2026-08-31','2027-02-28','6 Months'),('2024-02-29','2025-02-28','1 Year')])
def test_tenure_matches_expiry_shortcuts(details,start,end,wanted):
    from backend.template_docx import tenure
    details.update(start_date=start,end_date=end)
    assert tenure(Details(**details))==wanted


def test_rules_without_tenancy_details():
    response=client.post('/api/generate',json={'details':{},'documents':['rules'],'format':'source'})
    assert response.status_code==200,response.text
    result=text(response.content)
    assert 'DI CHIA SENG' not in result and '961004-01-5879' not in result
    assert len(result)>500


def test_move_in_without_rental_terms():
    response=client.post('/api/generate',json={'details':{'tenant_name':'Alex Tan','tenant_id':'TEST-P12345','agreement_date':'2026-10-02'},'documents':['move_in'],'format':'source'})
    assert response.status_code==200,response.text
    assert 'Alex Tan' in text(response.content)


@pytest.mark.parametrize('documents',[['tenancy'],['offer'],['rules','offer'],['move_in','tenancy']])
def test_agreements_still_require_tenancy_details(documents):
    response=client.post('/api/generate',json={'details':{'tenant_name':'Alex Tan','tenant_id':'TEST-P12345'},'documents':documents,'format':'source'})
    assert response.status_code==422


def test_move_in_requires_identity_and_date():
    response=client.post('/api/generate',json={'details':{},'documents':['move_in'],'format':'source'})
    assert response.status_code==422
