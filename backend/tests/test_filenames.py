from io import BytesIO
from zipfile import ZipFile
import pytest
from backend.models import Details, GenerateRequest
from backend.filenames import pdf_filename
from backend.main import generate


@pytest.mark.parametrize('aircon', [True, False])
@pytest.mark.parametrize('kind,code', [('tenancy','TA'), ('move_in','MIF'), ('rules','HR'), ('offer','LOF')])
def test_pdf_names(kind, code, aircon):
    assert pdf_filename(kind, Details(property='16-03', room='02', aircon=aircon)) == f'16-03_R02_{code}.pdf'


def test_filename_cannot_contain_paths_or_header_injection():
    name = pdf_filename('rules', Details(property='../../A:*"\r\n', room='02/03'))
    assert name == 'A_R02-03_HR.pdf'
    assert pdf_filename('rules', Details()) == '-_R-_HR.pdf'


def test_response_and_zip_use_same_names(monkeypatch):
    monkeypatch.setattr('backend.main.pdf', lambda kind, details: b'%PDF-test')
    details = Details(property='16-03', room='02', tenant_name='Test', tenant_id='TEST',
                      address='Test address', agreement_date='2026-10-05',
                      start_date='2026-10-17', end_date='2027-10-16')
    single = generate(GenerateRequest(details=details, documents=['rules']))
    assert single.headers['content-disposition'] == 'attachment; filename="16-03_R02_HR.pdf"'
    pack = generate(GenerateRequest(details=details, documents=['tenancy','move_in','rules','offer']))
    with ZipFile(BytesIO(pack.body)) as archive:
        assert archive.namelist() == ['16-03_R02_TA.pdf','16-03_R02_MIF.pdf','16-03_R02_HR.pdf','16-03_R02_LOF.pdf']
