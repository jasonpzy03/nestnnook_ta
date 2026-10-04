from io import BytesIO
from zipfile import ZipFile
import re
import pytest
import pymupdf as fitz
from lxml import etree as E
from pydantic import ValidationError
from backend.models import Details
from backend.template_docx import fill_docx, ROOT, SOURCES, NS
from backend.placeholders import paragraph_text, fields_for
from backend.converted_pdf import fill_converted
from backend.rich_pdf import styled_expression


@pytest.mark.parametrize('value',[0,40,65,100000])
def test_allowance_values(value):
    assert fields_for('tenancy',Details(aircon_kwh=value))['aircon_kwh']==str(value)


@pytest.mark.parametrize('value',[-1,1.5,100001,None,True])
def test_allowance_rejects_invalid_values(value):
    with pytest.raises(ValidationError):Details(aircon_kwh=value)


@pytest.mark.parametrize('aircon',[True,False])
def test_every_added_company_field_is_filled_in_word_and_pdf(aircon):
    key='ac' if aircon else 'noac'
    details=Details(aircon=aircon,aircon_kwh=65,company={'name':'EXAMPLE PROPERTY'})
    with ZipFile(ROOT/'agreements'/SOURCES[key]) as source:
        paragraphs=E.fromstring(source.read('word/document.xml')).xpath('//w:p',namespaces=NS)
        expected=sum(paragraph_text(p).count('{{company.name}}') for p in paragraphs)
    with ZipFile(BytesIO(fill_docx('tenancy',details))) as result:
        text=' '.join(paragraph_text(p) for p in E.fromstring(result.read('word/document.xml')).xpath('//w:p',namespaces=NS))
        assert text.count('EXAMPLE PROPERTY')==expected
        assert '{{' not in text
        assert ('65 kWh' in text)==aircon
    with fitz.open(stream=fill_converted('tenancy',details),filetype='pdf') as pdf:
        text=' '.join(page.get_text() for page in pdf)
        normalized=' '.join(text.split())
        assert normalized.count('EXAMPLE PROPERTY')>=expected
        assert '{{' not in normalized
        assert ('65 kWh' in normalized)==aircon
        assert '150' in normalized and 'transfer' in normalized.lower()
        bold=[span['text'] for page in pdf for block in page.get_text('dict')['blocks'] for line in block.get('lines',[]) for span in line['spans'] if 'Bold' in span['font']]
        assert any('Major' in text for text in bold)


def test_split_placeholder_keeps_emphasis_without_breaking_token():
    root=E.fromstring(f'<w:p xmlns:w="{NS["w"]}"><w:r><w:t>{{{{company.</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>name}}}} Major</w:t></w:r></w:p>')
    parts=styled_expression(root.xpath('./w:r/w:t',namespaces=NS),'NNBody')
    assert parts==[{'expression':'{{company.name}}','font':'NNBody'},{'expression':' Major','font':'NNBold'}]
