"""Refresh the offer PDF and field map after editing its Word template.

Run: .venv/Scripts/python.exe -m scripts.build_offer_pdf
Requires Windows and Microsoft Word; deployed generation does not.
"""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re
import pymupdf as fitz
from lxml import etree as E
from backend.offer_docx import SOURCE, TOKEN
from backend.template_docx import ROOT, NS, W, TemplateError
from backend.renderers import word_pdf
from scripts.pdf_marker import marker_font_size
from backend.placeholders import paragraph_text


def offer_fields(root):
    """Read each paragraph's own text, excluding nested text box paragraphs."""
    for p in root.xpath('//w:p', namespaces=NS):
        expression = paragraph_text(p)
        if not TOKEN.search(expression):
            continue
        matches = [re.fullmatch(r'OfferSlot_\d+_L(\d+)', mark.get(W+'name', ''))
                   for mark in p.findall('w:bookmarkStart', NS)]
        match = next((match for match in matches if match), None)
        if match is None:
            raise TemplateError('Offer paragraph needs an OfferSlot bookmark: '+expression[:180])
        yield p, expression, int(match[1])


def build():
    source = (ROOT / 'agreements' / SOURCE).read_bytes()
    with ZipFile(BytesIO(source)) as archive:
        root = E.fromstring(archive.read('word/document.xml'))
        tree = root.getroottree()
        margins = root.find('w:body/w:sectPr/w:pgMar', NS)
        page_size = root.find('w:body/w:sectPr/w:pgSz', NS)
        page_width = (int(page_size.get(W+'w')) - int(margins.get(W+'left')) - int(margins.get(W+'right'))) / 20
        slots = []
        for p, expression, lines in offer_fields(root):
            index = len(slots)
            rpr = p.find('w:r/w:rPr', NS)
            size_node = rpr.find('w:sz', NS) if rpr is not None else None
            size = int(size_node.get(W+'val')) / 2 if size_node is not None else 10.5
            bold = rpr is not None and rpr.find('w:b', NS) is not None and rpr.find('w:b', NS).get(W+'val') != '0'
            align_node = p.find('w:pPr/w:jc', NS)
            align = {'center': 1, 'right': 2}.get(align_node.get(W+'val'), 0) if align_node is not None else 0
            if align_node is not None:
                align_node.set(W+'val', 'left')
            cell = p.getparent()
            width = page_width
            shapes = p.xpath('ancestor::*[local-name()="wsp"]')
            if shapes:
                shape = shapes[0]
                extents = shape.xpath('./*[local-name()="spPr"]/*[local-name()="xfrm"]/*[local-name()="ext"]')
                body = shape.xpath('./*[local-name()="bodyPr"]')
                if extents:
                    insets = sum(int(body[0].get(k, '91440')) for k in ('lIns', 'rIns')) if body else 182880
                    width = (int(extents[0].get('cx')) - insets) / 12700
            if cell.tag == W+'tc':
                width = int(cell.find('w:tcPr/w:tcW', NS).get(W+'w')) / 20 - 10.8
            indent = p.find('w:pPr/w:ind', NS)
            if indent is not None:
                width -= sum(int(indent.get(W+k, '0')) / 20 for k in ('left', 'right'))
            marker = f'NNSLOT{index:03d}'
            slots.append(dict(xpath=tree.getpath(p), label=expression.strip(), width=width, size=size,
                              fallback=bool(p.xpath('ancestor::mc:Fallback', namespaces=NS)),
                              align=align, font='NNBold' if bold else 'NNBody', marker=marker))
            # Replace the entire variable paragraph. Its surrounding text remains editable
            # in Word and is read from the filled DOCX at runtime.
            for child in list(p):
                if child.tag != W+'pPr':
                    p.remove(child)
            run = E.SubElement(p, W+'r')
            if rpr is not None:
                run.append(deepcopy(rpr))
            E.SubElement(run, W+'t').text = marker+'START'
            for _ in range(lines-1):
                E.SubElement(run, W+'br')
            if lines > 1:
                E.SubElement(run, W+'t').text = marker+'END'
        buffer = BytesIO()
        with ZipFile(buffer, 'w', ZIP_DEFLATED) as probe:
            for item in archive.infolist():
                probe.writestr(item, E.tostring(root) if item.filename == 'word/document.xml' else archive.read(item.filename))
    pdf = fitz.open(stream=word_pdf(buffer.getvalue()), filetype='pdf')
    mapped = []
    for slot in slots:
        marker = slot.pop('marker')
        starts = [(i, r) for i, page in enumerate(pdf) for r in page.search_for(marker+'START')]
        ends = [(i, r) for i, page in enumerate(pdf) for r in page.search_for(marker+'END')]
        if slot.pop('fallback') and not starts and not ends:
            continue  # Word renders the DrawingML copy, not its legacy VML fallback.
        if len(starts) != 1 or len(ends) > 1 or (ends and starts[0][0] != ends[0][0]):
            raise TemplateError('Offer field spans pages or is missing: '+slot['label'])
        index, first = starts[0]
        slot['size'] = marker_font_size(pdf[index], first)
        last = ends[0][1] if ends else first
        slot['page'] = index
        slot['rect'] = [first.x0, first.y0-.2, first.x0+slot.pop('width'), last.y1+.8]
        for _, rect in starts+ends:
            pdf[index].add_redact_annot(rect, fill=False)
        mapped.append(slot)
    aml = [i for i, page in enumerate(pdf) if page.search_for('ENCLOSURE')]
    if len(aml) != 1:
        raise TemplateError('Keep the ENCLOSURE heading on a separate page.')
    for page in pdf:
        page.apply_redactions(images=0, graphics=0)
    for alias, filename in [('NNBody', 'times.ttf'), ('NNBold', 'timesbd.ttf')]:
        pdf[0].insert_font(fontname=alias, fontfile='C:/Windows/Fonts/'+filename)
    data = pdf.tobytes(garbage=4, deflate=True)
    folder = ROOT/'agreements/pdf'
    manifest = dict(source=SOURCE, source_sha256=hashlib.sha256(source).hexdigest(),
                    pdf_sha256=hashlib.sha256(data).hexdigest(), slots=mapped, aml_page=aml[0])
    (folder/'offer.pdf').write_bytes(data)
    (folder/'offer.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Offer: {len(pdf)} pages, {len(mapped)} mapped paragraphs')
    pdf.close()


if __name__ == '__main__':
    build()
