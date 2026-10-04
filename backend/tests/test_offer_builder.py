from lxml import etree as E
import pytest

from backend.template_docx import NS, TemplateError
from scripts.build_offer_pdf import offer_fields
from backend.placeholders import fill_package
from io import BytesIO
from zipfile import ZipFile


def test_text_box_container_is_not_a_second_field():
    root = E.fromstring(f'''<w:document xmlns:w="{NS['w']}">
      <w:body><w:p><w:r><w:pict><w:txbxContent><w:p>
        <w:bookmarkStart w:id="1" w:name="OfferSlot_24_L3"/>
        <w:r><w:t>Company: {{{{company.name}}}}</w:t></w:r>
      </w:p></w:txbxContent></w:pict></w:r></w:p></w:body>
    </w:document>''')
    fields = list(offer_fields(root))
    assert len(fields) == 1
    assert fields[0][1:] == ('Company: {{company.name}}', 3)


def test_unrelated_bookmark_does_not_hide_offer_bookmark():
    root = E.fromstring(f'''<w:p xmlns:w="{NS['w']}">
      <w:bookmarkStart w:id="9" w:name="_GoBack"/>
      <w:bookmarkStart w:id="1" w:name="OfferSlot_1_L1"/>
      <w:r><w:t>{{{{tenant_name}}}}</w:t></w:r>
    </w:p>''')
    assert list(offer_fields(root))[0][2] == 1


def test_missing_bookmark_identifies_the_actual_paragraph():
    root = E.fromstring(f'''<w:p xmlns:w="{NS['w']}">
      <w:r><w:t>Name: {{{{tenant_name}}}}</w:t></w:r>
    </w:p>''')
    with pytest.raises(TemplateError, match='Name:'):
        list(offer_fields(root))


def test_omitting_trailing_enclosure_keeps_signing_section_footer():
    xml = f'''<w:document xmlns:w="{NS['w']}"><w:body>
      <w:p><w:r><w:t>Signing page</w:t></w:r></w:p>
      <w:sdt><w:sdtPr><w:tag w:val="offer_aml"/></w:sdtPr><w:sdtContent>
        <w:p><w:pPr><w:sectPr><w:pgMar w:bottom="1200"/></w:sectPr></w:pPr></w:p>
        <w:p><w:r><w:t>ENCLOSURE</w:t></w:r></w:p>
      </w:sdtContent></w:sdt>
      <w:sectPr><w:pgMar w:bottom="1440"/></w:sectPr>
    </w:body></w:document>'''
    source = BytesIO()
    with ZipFile(source, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    with ZipFile(BytesIO(fill_package(source.getvalue(), {}, include_aml=False))) as archive:
        result = E.fromstring(archive.read('word/document.xml'))
    assert not result.xpath('//w:sdt', namespaces=NS)
    assert result.xpath('//w:body/w:sectPr/w:pgMar/@w:bottom', namespaces=NS) == ['1200']
