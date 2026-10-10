from io import BytesIO
from zipfile import ZipFile

from lxml import etree as E
import pymupdf as fitz

from backend.models import Details
from backend.placeholders import fields_for
from backend.template_docx import fill_docx, NS, INVENTORY_NAMES
from backend.converted_pdf import fill_converted


def test_inventory_fields_and_legacy_migration():
    d = Details(room_condition='Damaged', room_remarks='Paint chipped', makeup_table_drawer='with', inventory=[
        dict(name='Makeup table', quantity=1, condition='Fair', remarks='Small mark'),
        dict(name='Main door key', quantity=2),
        dict(name='Lamp', quantity=3, condition='Damaged', remarks='Shade cracked'),
    ])
    assert d.inventory[0].name == 'Study table'
    assert 'makeup_table_drawer' not in d.model_dump()
    fields = fields_for('move_in', d)
    assert fields['r0'] == 'Damaged: Paint chipped'
    assert fields['r4'] == 'Fair: Small mark'
    assert fields['q19'] == '2'
    assert (fields['q20'], fields['g20'], fields['r20']) == ('3', 'NO', 'Damaged: Shade cracked')
    assert not any(key.startswith('drawer_') or key == 'b20' for key in fields)


def test_updated_inventory_in_both_word_copies_and_pdf():
    d = Details(tenant_name='Alex Tan', tenant_id='TEST-123', agreement_date='2026-10-10', inventory=[
        dict(name='Study table', quantity=1, condition='Good', remarks='Desk checked'),
        dict(name='Main door key', quantity=2),
        dict(name='Lamp', quantity=3, condition='Damaged', remarks='Shade cracked'),
    ])
    with ZipFile(BytesIO(fill_docx('move_in', d))) as archive:
        root = E.fromstring(archive.read('word/document.xml'))
    tables = root.xpath('//w:tbl[w:tr/w:tc//w:t[text()="Lamp"]]', namespaces=NS)
    assert len(tables) == 2
    for table in tables:
        rows = [[''.join(c.xpath('.//w:t/text()', namespaces=NS)) for c in row.findall('w:tc', NS)]
                for row in table.findall('w:tr', NS)]
        assert rows[0] == ['Items', 'Qty', 'Good Condition', 'Remarks:']
        assert ['Study Table', '1', 'YES', 'Desk checked'] in rows
        assert ['Main Door Key', '2', 'YES', '-'] in rows
        assert ['Lamp', '3', 'NO', 'Damaged: Shade cracked'] in rows
    with fitz.open(stream=fill_converted('move_in', d), filetype='pdf') as doc:
        assert len(doc) == 1
        content = '\n'.join(page.get_text() for page in doc)
        assert all(value in content for value in ['Study Table', 'Lamp', 'Desk checked', 'Damaged: Shade cracked'])
        assert not any(value in content.lower() for value in ['broken', 'makeup', 'drawer', '{{'])
        lamp = doc[0].search_for('Lamp')[0]
        line = doc[0].get_textbox(fitz.Rect(0, lamp.y0-1, doc[0].rect.width, lamp.y1+1))
        assert '3' in line and 'NO' in line
    assert len(INVENTORY_NAMES) == 20
