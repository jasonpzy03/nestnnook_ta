"""Named Word placeholders shared by every document and converted PDF."""
from io import BytesIO
import re
import secrets
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from .template_docx import NS, W, TemplateError, date_text, tenure, amount, INVENTORY_NAMES

TOKEN = re.compile(r'\{\{([^{}]+)\}\}')


def fields_for(kind, d):
    fields = {key: str(value).strip() or '-' for key, value in d.model_dump().items()
              if isinstance(value, str)}
    fields.update({'company.'+key: value for key, value in d.company.model_dump().items()})
    for key in ('rent', 'parking', 'security_deposit', 'access_deposit', 'advance_rent', 'agreement_fee', 'total'):
        fields[key] = amount(getattr(d, key))
    for key in ('agreement_date', 'start_date', 'end_date'):
        value = getattr(d, key)
        fields[key] = (value.strftime('%d/%m/%Y') if kind == 'offer' else
                       date_text(value, kind == 'move_in' or d.aircon)) if value else '-'
    fields['tenure'] = tenure(d) if d.start_date and d.end_date else '-'
    fields['property_address'] = d.property_address or '-'
    fields['guardian_date'] = fields['agreement_date'] if d.guardian_name else '-'
    if kind == 'offer' and not d.reference.strip():
        if not d.agreement_date:
            raise TemplateError('An agreement date is required for the offer invoice.')
        d.reference = f'NN-{d.agreement_date:%Y%m%d}-{secrets.token_hex(5).upper()}'
        fields['reference'] = d.reference
    items = {item.name: item for item in d.inventory}
    unknown = items.keys() - set(INVENTORY_NAMES)
    if kind == 'move_in' and unknown:
        raise TemplateError('The move-in template has no row for: '+', '.join(sorted(unknown)))
    fields.update(q0='-', g0='YES' if d.room_condition.lower() == 'good' else 'NO' if d.room_condition else '-',
                  b0='YES' if d.room_condition.lower() == 'damaged' else '-',
                  r0=d.room_remarks or (d.room_condition if d.room_condition.lower() not in ('good', 'damaged') else '') or '-')
    for index, name in enumerate(INVENTORY_NAMES, 1):
        item = items.get(name)
        qty, condition = (item.quantity, item.condition) if item else (1, 'Good')
        supplied = qty > 0 and condition != 'Not supplied'
        notes = item.remarks if item else ''
        if supplied and condition == 'Fair':
            notes = 'Fair'+(': '+notes if notes else '')
        for prefix, value in [('q', str(qty) if supplied else '-'),
                              ('g', 'YES' if supplied and condition == 'Good' else 'NO' if supplied else '-'),
                              ('b', 'YES' if supplied and condition == 'Damaged' else '-'), ('r', notes or '-')]:
            fields[f'{prefix}{index}'] = value
    fields['drawer_with'] = '[X]' if d.makeup_table_drawer == 'with' else '[ ]'
    fields['drawer_without'] = '[X]' if d.makeup_table_drawer == 'without' else '[ ]'
    return fields


def substitute(expression, fields):
    def value(match):
        key = match[1]
        if key not in fields:
            raise TemplateError('Unknown template field: '+key)
        return fields[key]
    return TOKEN.sub(value, expression)


def paragraph_nodes(p):
    # A paragraph can contain a drawing with its own paragraphs. Do not treat those
    # nested text boxes as part of the surrounding paragraph's text.
    return [n for n in p.xpath('.//w:t', namespaces=NS)
            if next(n.iterancestors(W+'p'), None) is p]


def paragraph_text(p):
    return ''.join(n.text or '' for n in paragraph_nodes(p))


def paragraph_segments(p):
    """Separate columns and lines within a paragraph without losing tab positioning."""
    segments = [[]]
    for node in p.iter():
        if next(node.iterancestors(W+'p'), None) is not p:
            continue
        if node.tag == W+'t':
            segments[-1].append(node)
        elif node.tag in (W+'tab', W+'br', W+'cr'):
            segments.append([])
    return [nodes for nodes in segments if any(n.text for n in nodes)]


def fill_package(source, fields, include_aml=True):
    out = BytesIO()
    with ZipFile(BytesIO(source)) as archive, ZipFile(out, 'w', ZIP_DEFLATED) as target:
        for item in archive.infolist():
            data = archive.read(item.filename)
            if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                root = E.fromstring(data)
                changed = False
                if not include_aml:
                    for block in root.xpath('//w:sdt[w:sdtPr/w:tag[@w:val="offer_aml"]]', namespaces=NS):
                        block.getparent().remove(block)
                        changed = True
                for p in root.xpath('//w:p', namespaces=NS):
                    nodes = paragraph_nodes(p)
                    original = ''.join(n.text or '' for n in nodes)
                    matches = list(TOKEN.finditer(original))
                    for match in reversed(matches):
                        value = substitute(match[0], fields)
                        offset = 0
                        inserted = False
                        for node in nodes:
                            raw = node.text or ''; end = offset + len(raw)
                            if end > match.start() and offset < match.end():
                                left = max(0, match.start()-offset)
                                right = min(len(raw), match.end()-offset)
                                node.text = raw[:left]+(value if not inserted else '')+raw[right:]
                                node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                                inserted = True
                                run = node.getparent()
                                if run.xpath('./w:rPr/w:fitText', namespaces=NS):
                                    # Word materializes Fit Text as character spacing
                                    # when saving. Remove both forms for actual values.
                                    for fit in run.xpath('./w:rPr/w:fitText | ./w:rPr/w:spacing | ./w:rPr/w:w', namespaces=NS):
                                        fit.getparent().remove(fit)
                            offset = end
                    changed |= bool(matches)
                if changed:
                    data = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            target.writestr(item, data)
    return out.getvalue()
