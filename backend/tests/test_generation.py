from io import BytesIO
from zipfile import ZipFile
import pytest
import pymupdf as fitz
from lxml import etree as E
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Details
from backend.template_docx import fill_docx, ROOT, SOURCES, NS, header_parts
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
    return dict(tenant_name='Alex Tan',tenant_id='TEST-P12345',phone='+60 12-3456789',email='alex@example.test',property='16-03',room='Room 2',address='16-03 Trellis Residences, Johor Bahru, Johor',agreement_date='2026-10-01',start_date='2026-10-10',end_date='2027-10-09',rent=1200,security_deposit=1200,access_deposit=150,advance_rent=800,agreement_fee=50,inventory=[dict(name='Access card',quantity=1,condition='Good',remarks='CARD-123')])
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
            if 'offer' in name:assert name.endswith('.docx') and 'RM2,200.00' in t
            if 'move_in' in name:assert t.count('CARD-123')==2
@pytest.mark.parametrize('kind,key',[('tenancy','ac'),('tenancy','noac'),('rules','rules'),('move_in','move_in')])
def test_original_structure_and_parts(details,kind,key):
    d=Details(**details);d.aircon=key!='noac'
    data=fill_docx(kind,d)
    with ZipFile(ROOT/'agreements'/SOURCES[key]) as original, ZipFile(BytesIO(data)) as filled:
        assert original.namelist()==filled.namelist()
        headers=header_parts(original,E.fromstring(original.read('word/document.xml')))
        for name in original.namelist():
            if name!='word/document.xml' and name not in headers:assert original.read(name)==filled.read(name),name
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
def test_offer_word_based_pdf_pages(details,include):
    d=Details(**details);d.include_aml=include
    with fitz.open(stream=fill_offer(d),filetype='pdf') as result,fitz.open(ROOT/'agreements/letter of offer to rent.pdf') as original:
        assert len(result)==(3 if include else 2)
        for i,page in enumerate(result):
            assert page.rect==original[i].rect
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
    assert r.status_code==422 and 'too long for the PDF template' in r.json()['detail']
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

@pytest.mark.parametrize('aircon',[True,False])
def test_pdf_pack_without_word(details,aircon,monkeypatch):
    from backend import renderers
    def no_word(*args):raise AssertionError('Runtime must not invoke Word')
    monkeypatch.setattr(renderers,'word_pdf',no_word)
    details['aircon']=aircon
    response=client.post('/api/generate',json={'details':details,'documents':['tenancy','rules','move_in','offer'],'format':'pdf'})
    assert response.status_code==200,response.text
    with ZipFile(BytesIO(response.content)) as pack:
        assert len(pack.namelist())==4
        for name in pack.namelist():
            data=pack.read(name);content=text(data)
            assert name.endswith('.pdf')
            assert 'Alex Tan' in content and 'TEST-P12345' in content
            for stale in ['DI CHIA SENG','TENG YING YING','HII HUI CHIN','Shamsunder','VANGUARD','Vanguard','1102047977','961004-01-5879','PCR0033666']:
                assert stale not in content,(name,stale)
            with fitz.open(stream=data,filetype='pdf') as doc:
                assert len(doc)==((4 if aircon else 3) if 'tenancy' in name else 3 if 'offer' in name else 2)
            if 'tenancy' in name:
                assert '150' in content and 'transfer' in content.lower()
                assert 'Refundable Room Deposit' in content
            if 'move_in' in name:assert 'CARD-123' in content


def test_rules_pdf_without_details():
    response=client.post('/api/generate',json={'details':{},'documents':['rules'],'format':'pdf'})
    assert response.status_code==200,response.text
    assert 'Name : -' in text(response.content)


@pytest.mark.parametrize('choice,count',[('not_applicable',0),('with',1),('without',1)])
def test_pdf_drawer_mark(details,choice,count):
    from backend.converted_pdf import fill_converted
    data=fill_converted('move_in',Details(**details,makeup_table_drawer=choice))
    with fitz.open(stream=data,filetype='pdf') as doc:
        marks=[drawing for drawing in doc[1].get_drawings() if fitz.Rect(62,141,82,176).contains(drawing['rect']) and any(item[0]=='l' and item[1].x!=item[2].x and item[1].y!=item[2].y for item in drawing['items'])]
        assert len(marks)==count
        if marks:assert abs(marks[0]['rect'].y0-(148.1 if choice=='with' else 159.8))<1


def test_converted_pdf_overflow(details):
    details['address']='Long address '*45
    response=client.post('/api/generate',json={'details':details,'documents':['tenancy'],'format':'pdf'})
    assert response.status_code==422
    assert 'too long for the PDF template' in response.json()['detail']


def test_converted_pdf_unicode(details):
    from backend.converted_pdf import fill_converted
    details['tenant_name']='陈小明'
    assert '陈小明' in text(fill_converted('rules',Details(**details)))


def test_converted_pdf_rejects_stale_background(details,tmp_path,monkeypatch):
    from backend import converted_pdf
    mapping=(converted_pdf.FOLDER/'rules.json').read_bytes()
    (tmp_path/'rules.json').write_bytes(mapping)
    (tmp_path/'rules.pdf').write_bytes(b'changed background')
    monkeypatch.setattr(converted_pdf,'FOLDER',tmp_path)
    with pytest.raises(ValueError,match='template changed'):
        converted_pdf.fill_converted('rules',Details(**details))


@pytest.mark.parametrize('kind,aircon',[('tenancy',True),('tenancy',False),('rules',True),('move_in',True)])
def test_company_header_in_word_and_pdf(details,kind,aircon):
    from backend.renderers import pdf
    details.update(aircon=aircon,company={'name':'TEST PROPERTY COMPANY','registration':'TEST-SSM-123','address':'123 Example Street, Johor','phone':'+60 123456789'})
    d=Details(**details)
    with ZipFile(BytesIO(fill_docx(kind,d))) as z:
        h=E.fromstring(z.read('word/nest-header.xml'))
        content=''.join(h.xpath('//w:t/text()',namespaces=NS))
        for value in details['company'].values():assert value in content
        assert 'NEST & NOOK PROPERTY CARE' not in content
        assert 'word/media/nest-header-logo.jpg' in z.namelist()
    with fitz.open(stream=pdf(kind,d),filetype='pdf') as result:
        content=result[0].get_text(clip=fitz.Rect(0,0,620,210))
        for value in details['company'].values():assert value in content
        assert result[0].get_images()
        assert 'NEST & NOOK PROPERTY CARE' not in content


def test_offer_auto_invoice_number(details):
    import re
    d=Details(**details)
    result=text(fill_offer(d))
    assert re.fullmatch(r'NN-20261001-[A-F0-9]{10}',d.reference)
    assert 'Invoice Number: '+d.reference in result
    reference=d.reference
    assert reference in text(fill_offer(d))
    assert d.reference==reference
    another=Details(**details)
    fill_offer(another)
    assert another.reference!=reference


def test_offer_keeps_manual_invoice_number(details):
    d=Details(**details,reference='MY-OFFER-007')
    assert 'Invoice Number: MY-OFFER-007' in text(fill_offer(d))
    assert d.reference=='MY-OFFER-007'


@pytest.mark.parametrize('address,expected',[
    ('Trellis Residences, Johor','16-03, Trellis Residences, Johor'),
    ('16-03, Trellis Residences','16-03, Trellis Residences'),
    ('#16-03 Trellis Residences','#16-03 Trellis Residences'),
    ('Unit 16-03, Trellis Residences','Unit 16-03, Trellis Residences'),
    ('16-030, Trellis Residences','16-03, 16-030, Trellis Residences'),
])
def test_unit_prefix_in_property_address(details,address,expected):
    from backend.converted_pdf import fill_converted
    d=Details(**{**details,'property':'16-03','address':address})
    for aircon in [True,False]:
        d.aircon=aircon
        assert expected in text(fill_docx('tenancy',d))
        assert expected in text(fill_converted('tenancy',d))
    assert d.address==address
    assert d.company.address==Details().company.address


@pytest.mark.parametrize('include', [True, False])
def test_offer_word_download_and_optional_enclosure(details, include):
    details['include_aml'] = include
    r = client.post('/api/generate', json={'details': details, 'documents': ['offer'], 'format': 'source'})
    assert r.status_code == 200, r.text
    assert r.headers['content-disposition'].endswith('offer.docx"')
    content = text(r.content)
    assert 'Alex Tan' in content and 'RM2,200.00' in content
    assert '{{' not in content
    assert ('ENCLOSURE' in content) == include
    assert ('decided to not provide' in content) == include
    assert 'room transfer' not in content.lower()


def test_offer_edits_are_used_and_pdf_requires_refresh(details, tmp_path, monkeypatch):
    from backend import offer_docx, converted_pdf
    from backend.template_docx import TemplateError
    source = ROOT / 'agreements' / offer_docx.SOURCE
    destination = tmp_path / 'agreements'
    destination.mkdir()
    with ZipFile(source) as before, ZipFile(destination / offer_docx.SOURCE, 'w') as after:
        for item in before.infolist():
            data = before.read(item.filename)
            if item.filename == 'word/document.xml':
                data = data.replace(b'TENANCY DETAILS &amp; PAYMENT BREAKDOWN', b'CUSTOM PAYMENT HEADING')
            after.writestr(item, data)
    monkeypatch.setattr(offer_docx, 'ROOT', tmp_path)
    monkeypatch.setattr(converted_pdf, 'ROOT', tmp_path)
    assert 'CUSTOM PAYMENT HEADING' in text(fill_docx('offer', Details(**details)))
    with pytest.raises(TemplateError, match='template changed'):
        fill_offer(Details(**details))


def test_offer_fields_split_across_runs_and_literal_input(details, tmp_path, monkeypatch):
    from backend import offer_docx
    source = ROOT / 'agreements' / offer_docx.SOURCE
    destination = tmp_path / 'agreements'
    destination.mkdir()
    with ZipFile(source) as before, ZipFile(destination / offer_docx.SOURCE, 'w') as after:
        for item in before.infolist():
            data = before.read(item.filename)
            if item.filename == 'word/document.xml':
                data = data.replace(b'{{tenant_name}}', b'{{tenant_</w:t></w:r><w:r><w:t>name}}')
            after.writestr(item, data)
    monkeypatch.setattr(offer_docx, 'ROOT', tmp_path)
    details['tenant_name'] = 'Alex {{rent}} & <B>'
    assert 'Alex {{rent}} & <B>' in text(fill_docx('offer', Details(**details)))
