from io import BytesIO
from zipfile import ZipFile
from lxml import etree as E
import pytest
from backend import template_docx
from backend.models import Details, Company


@pytest.mark.parametrize('target', ['header1.xml', '/word/header1.xml', 'headers/company.xml'])
def test_word_renamed_header_is_resolved_and_filled(tmp_path, monkeypatch, target):
    source = template_docx.ROOT / 'agreements' / template_docx.SOURCES['rules']
    destination = tmp_path / 'agreements'
    destination.mkdir()
    new_name = target.lstrip('/') if target.startswith('/') else 'word/' + target
    with ZipFile(source) as original, ZipFile(destination / source.name, 'w') as edited:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == 'word/_rels/document.xml.rels':
                data = data.replace(b'Target="nest-header.xml"', ('Target="' + target + '"').encode())
            if item.filename == '[Content_Types].xml':
                data = data.replace(b'/word/nest-header.xml', ('/' + new_name).encode())
            edited.writestr(new_name if item.filename == 'word/nest-header.xml' else item.filename, data)
    monkeypatch.setattr(template_docx, 'ROOT', tmp_path)
    data = template_docx.fill_docx('rules', Details(company=Company(name='Custom Company', phone='+60123456789')))
    with ZipFile(BytesIO(data)) as output:
        root = E.fromstring(output.read('word/document.xml'))
        headers = template_docx.header_parts(output, root)
        assert list(headers) == [new_name]
        content = template_docx.text(headers[new_name])
        assert 'Custom Company' in content and '+60123456789' in content
        assert 'NEST & NOOK PROPERTY CARE' not in content
