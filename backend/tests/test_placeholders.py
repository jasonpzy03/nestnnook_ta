from io import BytesIO
from zipfile import ZipFile
import pytest
from lxml import etree as E
from backend.template_docx import ROOT, SOURCES, NS, W, TemplateError, text
from backend.placeholders import fill_package, fields_for, paragraph_text, substitute
from backend.models import Details


def package(xml):
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    return data.getvalue()


def document(data):
    with ZipFile(BytesIO(data)) as archive:
        return E.fromstring(archive.read('word/document.xml'))


def test_split_runs_are_filled_without_reinterpreting_input():
    source = package(f'<w:document xmlns:w="{NS["w"]}"><w:body><w:p><w:r><w:t>Name: {{{{tenant_</w:t></w:r><w:r><w:t>name}}}} / {{{{tenant_id}}}}</w:t></w:r></w:p></w:body></w:document>')
    result = document(fill_package(source, {'tenant_name': 'A & <B> {{tenant_id}}', 'tenant_id': 'ID-123'}))
    assert text(result) == 'Name: A & <B> {{tenant_id}} / ID-123'


def test_unknown_field_reports_name():
    with pytest.raises(TemplateError, match='tenant_nmae'):
        substitute('{{tenant_nmae}}', {'tenant_name': 'Alex'})


def test_word_fit_text_spacing_is_removed_for_actual_values():
    source=package(f'<w:document xmlns:w="{NS["w"]}"><w:body><w:p><w:r><w:rPr><w:fitText w:val="1500"/><w:spacing w:val="183"/></w:rPr><w:t>{{{{g0}}}}</w:t></w:r></w:p></w:body></w:document>')
    result=document(fill_package(source,{'g0':'YES'}))
    assert text(result)=='YES'
    assert not result.xpath('//w:fitText | //w:rPr/w:spacing',namespaces=NS)


def test_move_in_pdf_signature_columns_and_final_inventory_row():
    import pymupdf as fitz
    from backend.converted_pdf import fill_converted
    details=Details(tenant_name='Alex Tan',tenant_id='TEST-P12345',agreement_date='2026-10-01',meter_reading='123.45')
    with fitz.open(stream=fill_converted('move_in',details),filetype='pdf') as doc:
        page=next(page for page in doc if page.search_for('Starting Electricity Meter Reading'))
        assert page.search_for('Starting Electricity Meter Reading')
        assert page.search_for('123.45')
        ssm=[rect for p in doc for rect in p.search_for('SSM No.')]
        assert ssm and all(rect.x0>300 for rect in ssm)
        signature_ids=[rect for p in doc for ssm_rect in p.search_for('SSM No.')
                       for rect in p.search_for('TEST-P12345') if abs(rect.y0-ssm_rect.y0)<3]
        assert signature_ids and all(rect.x1<310 for rect in signature_ids)


@pytest.mark.parametrize('key', list(SOURCES))
def test_migrated_templates_have_fields_and_no_sample_identity(key):
    with ZipFile(ROOT/'agreements'/SOURCES[key]) as archive:
        parts = [E.fromstring(archive.read(name)) for name in archive.namelist()
                 if name.startswith('word/') and name.endswith('.xml')]
    content = ''.join(text(root) for root in parts)
    assert '{{tenant_name}}' in content and '{{tenant_id}}' in content
    for sample in ('DI CHIA SENG', 'TENG YING YING', 'HII HUI CHIN', '961004-01-5879'):
        assert sample not in content


def test_fields_follow_reordered_and_relabelled_rows():
    with ZipFile(ROOT/'agreements'/SOURCES['ac']) as archive:
        parts = {i.filename: archive.read(i.filename) for i in archive.infolist()}
    root = E.fromstring(parts['word/document.xml'])
    table = root.find('w:body/w:tbl', NS)
    rows = table.findall('w:tr', NS)
    for row in rows:
        table.remove(row)
    for row in reversed(rows):
        table.append(row)
    for p in table.xpath('.//w:tc[1]//w:p', namespaces=NS):
        for node in p.xpath('.//w:t', namespaces=NS):
            node.text = 'Custom label'
    parts['word/document.xml'] = E.tostring(root)
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    fields = fields_for('tenancy', Details(property='16-03', address='Example Street', rent=1234))
    result = document(fill_package(data.getvalue(), fields))
    filled_rows = result.find('w:body/w:tbl', NS).findall('w:tr', NS)
    for before, after in zip(reversed(rows), filled_rows):
        expression = text(before.findall('w:tc', NS)[1])
        assert text(after.findall('w:tc', NS)[1]) == substitute(expression, fields)
    assert 'RM1,234.00' in text(result)
    assert '16-03, Example Street' in text(result)


def test_inventory_and_guardian_fields_keep_existing_rules():
    details = Details(agreement_date='2026-10-01', inventory=[
        {'name': 'Bedframe / Divan', 'quantity': 0, 'condition': 'Not supplied'},
        {'name': 'Mattress', 'quantity': 1, 'condition': 'Fair', 'remarks': 'Small mark'}], makeup_table_drawer='with')
    fields = fields_for('move_in', details)
    assert (fields['q1'], fields['g1'], fields['b1']) == ('-', '-', '-')
    assert fields['r2'] == 'Fair: Small mark'
    assert fields['q3'] == '1' and fields['g3'] == 'YES'
    assert fields['drawer_with'] == '[X]' and fields['drawer_without'] == '[ ]'
    assert fields['guardian_date'] == '-'
