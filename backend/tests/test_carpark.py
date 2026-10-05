from io import BytesIO
from zipfile import ZipFile
from decimal import Decimal
import pytest
from pydantic import ValidationError
import pymupdf as fitz
from backend.models import Details, GenerateRequest
from backend.template_docx import fill_docx
from backend.converted_pdf import fill_converted
from backend.main import generate


def details(**overrides):
    return Details(**(dict(tenant_name='Alex Tan', tenant_id='TEST-123',
        carpark_lot='CP-7', carpark_address='Parking Address',
        carpark_agreement_date='2026-10-06', carpark_start_date='2026-10-17',
        carpark_end_date='2027-04-16', carpark_deposit=150,
        property='16-03',room='02',address='Residential Address',
        agreement_date='2026-09-01',start_date='2026-09-01',end_date='2027-08-31',rent=1200)|overrides))


def test_independent_payments_and_defaults():
    d=details(carpark_earnest_deposit=999)
    assert d.carpark_rent==300
    assert d.carpark_earnest_deposit==Decimal('145.16')
    assert d.advance_rent==1200
    assert Details(carpark_start_date='2028-02-17').carpark_earnest_deposit==Decimal('134.48')


def test_separate_required_dates_and_lot():
    with pytest.raises(ValidationError):GenerateRequest(details=details(carpark_lot=''),documents=['carpark'])
    with pytest.raises(ValidationError):GenerateRequest(details=details(carpark_start_date=None),documents=['carpark'])
    with pytest.raises(ValidationError):details(carpark_end_date='2026-10-01')


def test_placeholder_word_and_pdf():
    d=details()
    with ZipFile(BytesIO(fill_docx('carpark',d))) as z:
        xml=z.read('word/document.xml').decode()
        for text in ('CP-7','Parking Address','17/10/2026','16/04/2027','145.16','300.00','150.00','Alex Tan','TEST-123'):
            assert text in xml
        assert '{{' not in xml
        assert '15/5/2025' not in xml
    with fitz.open(stream=fill_converted('carpark',d),filetype='pdf') as pdf:
        text=''.join(p.get_text() for p in pdf)
        for value in ('CP-7','Parking Address','17/10/2026','16/04/2027','145.16','300.00','Alex Tan','TEST-123'):
            assert value in text
        assert '{{' not in text
        assert 'Residential Address' not in text
        assert len(pdf)==1


def test_download_and_five_document_bundle(monkeypatch):
    monkeypatch.setattr('backend.main.pdf',lambda kind,d:kind.encode())
    d=details()
    response=generate(GenerateRequest(details=d,documents=['carpark']))
    assert response.headers['content-disposition']=='attachment; filename="CP-7_CPA.pdf"'
    response=generate(GenerateRequest(details=d,documents=['carpark','tenancy','rules','move_in','offer']))
    with ZipFile(BytesIO(response.body)) as archive:
        assert len(archive.namelist())==5
        assert 'CP-7_CPA.pdf' in archive.namelist()
