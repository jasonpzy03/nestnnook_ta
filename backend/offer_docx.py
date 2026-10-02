"""Fill the editable offer template, including tokens split across Word runs."""
from copy import deepcopy
from io import BytesIO
import re
import secrets
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from .template_docx import ROOT, NS, W, TemplateError, replace, tenure, amount

SOURCE = '4. Letter of Offer to Rent.docx'
TOKEN = re.compile(r'\{\{([^{}]+)\}\}')


def values(details):
    if not details.reference.strip():
        details.reference = f'NN-{details.agreement_date:%Y%m%d}-{secrets.token_hex(5).upper()}'
    result = {name: str(getattr(details, name)).strip() or '-' for name in (
        'tenant_name', 'tenant_id', 'property', 'room', 'reference', 'special_conditions')}
    for name in ('rent', 'security_deposit', 'advance_rent', 'access_deposit', 'agreement_fee', 'total'):
        result[name] = amount(getattr(details, name))
    for name in ('agreement_date', 'start_date', 'end_date'):
        result[name] = getattr(details, name).strftime('%d/%m/%Y')
    result['tenure'] = tenure(details)
    result.update({'company.' + key: value for key, value in details.company.model_dump().items()})
    return result


def fill_offer_docx(details):
    fields = values(details)
    out = BytesIO()
    with ZipFile(ROOT / 'agreements' / SOURCE) as source, ZipFile(out, 'w', ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                root = E.fromstring(data)
                if not details.include_aml:
                    for block in root.xpath('//w:sdt[w:sdtPr/w:tag[@w:val="offer_aml"]]', namespaces=NS):
                        block.getparent().remove(block)
                # Snapshot all tokens before replacement so tenant input is never interpreted as a token.
                for p in root.xpath('//w:p', namespaces=NS):
                    original = ''.join(p.xpath('.//w:t/text()', namespaces=NS))
                    tokens = TOKEN.findall(original)
                    unknown = set(tokens) - fields.keys()
                    if unknown:
                        raise TemplateError('Unknown offer template field: ' + ', '.join(sorted(unknown)))
                    # Temporary sentinels avoid recursive replacement of user-supplied values.
                    wrapper = E.Element('wrapper'); wrapper.append(deepcopy(p))
                    for index, key in enumerate(dict.fromkeys(tokens)):
                        replace(wrapper, '{{' + key + '}}', f'\ue000{index}\ue001')
                    for index, key in enumerate(dict.fromkeys(tokens)):
                        replace(wrapper, f'\ue000{index}\ue001', fields[key])
                    updated = wrapper[0]
                    # Reserved template lines are for PDF mapping; Word reflows actual text.
                    if tokens:
                        for br in updated.xpath('.//w:br[not(@w:type)]', namespaces=NS):
                            br.getparent().remove(br)
                    p.getparent().replace(p, updated)
                data = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            target.writestr(item, data)
    return out.getvalue()
