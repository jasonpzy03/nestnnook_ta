"""Locate placeholder paragraphs by temporary markers in a native Word export."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re
from lxml import etree as E
import pymupdf as fitz
from backend.template_docx import ROOT, NS, W, TemplateError
from backend.placeholders import TOKEN, paragraph_text, paragraph_segments, fields_for, substitute
from backend.models import Details
from backend.renderers import word_pdf
from scripts.pdf_marker import marker_font_size, paragraph_alignment
from backend.rich_pdf import styled_expression

META = re.compile(r'NNF_\d+_(\d+)_(\d+)_(\d+)_([012])_([BDKST])$')
ALIASES = dict(B='NNBody', D='NNBold', K='NNBank', S='NNHeaderSans', T='NNHeaderSerif')


def set_property(parent, tag, **attributes):
    child = parent.find('w:'+tag, NS)
    if child is None:
        child = E.SubElement(parent, W+tag)
    for key, value in attributes.items():
        child.set(W+key, str(value))
    return child


def build(key, source_name):
    source = (ROOT/'agreements'/source_name).read_bytes()
    kind = 'tenancy' if key in ('ac', 'noac') else key
    valid = fields_for(kind, Details())
    slots = []
    with ZipFile(BytesIO(source)) as archive:
        parts = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    styles=E.fromstring(parts['word/styles.xml'])
    for part, data in list(parts.items()):
        if not part.startswith('word/') or not part.endswith('.xml'):
            continue
        root = E.fromstring(data)
        changed = False
        for p in root.xpath('//w:p', namespaces=NS):
            segments = paragraph_segments(p)
            # Short probe markers must not jump to an earlier tab stop than
            # the real left-column signature text. Keep the explicit right
            # column stops, using the reserved first-column width as boundary.
            if len(segments)==2 and all(TOKEN.search(''.join(n.text or '' for n in group)) for group in segments):
                marks=[META.fullmatch(m.get(W+'name','')) for m in p.findall('w:bookmarkStart',NS)]
                meta=next((m for m in marks if m),None)
                tabs=p.find('w:pPr/w:tabs',NS)
                if meta is not None and tabs is not None:
                    stops=list(tabs)
                    if any(int(stop.get(W+'pos','0'))>=int(meta[1]) for stop in stops):
                        for stop in stops:
                            if int(stop.get(W+'pos','0'))<int(meta[1]):tabs.remove(stop)
            for nodes in segments:
                expression = ''.join(n.text or '' for n in nodes)
                if not TOKEN.search(expression):
                    continue
                substitute(expression, valid)
                marks = [META.fullmatch(m.get(W+'name', '')) for m in p.findall('w:bookmarkStart', NS)]
                meta = next((m for m in marks if m), None)
                if meta is None:
                    raise TemplateError(f'{source_name}: PDF space is not defined for {expression}. Keep the NNF bookmark or add one using agreements/README.md.')
                width, height = int(meta[1])/20, int(meta[2])/20
                # Bookmark size is legacy spacing metadata only. Word determines
                # the field's actual font size from its run and inherited styles.
                size = int(meta[3])/2
                index = len(slots)
                marker = 'Z'+chr(65+index//26)+chr(65+index%26)
                in_cell = bool(p.xpath('ancestor::w:tc', namespaces=NS))
                fallback = bool(p.xpath('ancestor::mc:Fallback', namespaces=NS))
                slots.append(dict(marker=marker, expression=expression, label=', '.join(dict.fromkeys(TOKEN.findall(expression))),
                                  width=width, height=height, size=size,
                                  align=paragraph_alignment(p,styles) if root.tag==W+'hdr' else int(meta[4]), font=ALIASES[meta[5]],
                                  in_cell=in_cell, fallback=fallback, shared=len(segments)>1,
                                  preserve_size=root.tag == W+'hdr'))
                if key in ('ac','noac') and part=='word/document.xml':
                    rich=styled_expression(nodes,ALIASES[meta[5]])
                    if any(run['font']!=ALIASES[meta[5]] for run in rich):slots[-1]['rich']=rich
                pr = p.find('w:pPr', NS)
                if pr is None:
                    pr = E.Element(W+'pPr'); p.insert(0, pr)
                set_property(pr, 'jc', val='left')
                # Preserve tabs and manual line breaks: some forms place two
                # signature columns or bank lines inside a single paragraph.
                nodes[0].text=marker
                for node in nodes[1:]:node.text=''
                run=nodes[0].getparent();rpr=run.find('w:rPr',NS)
                if rpr is None:rpr=E.Element(W+'rPr');run.insert(0,rpr)
                for node in nodes:
                    for fit in node.getparent().xpath('./w:rPr/w:fitText | ./w:rPr/w:spacing | ./w:rPr/w:w',namespaces=NS):
                        fit.getparent().remove(fit)
                set_property(rpr,'rFonts',ascii='Arial',hAnsi='Arial')
                if not in_cell and len(segments)==1 and height>20:
                    leading=size*1.2
                    set_property(pr,'spacing',line=round(leading*20),lineRule='exact')
                    for _ in range(max(0,round(height/leading)-1)):
                        E.SubElement(run,W+'br')
                changed=True
        if changed:
            parts[part] = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    probe = BytesIO()
    with ZipFile(probe, 'w', ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    native = word_pdf(probe.getvalue())
    debug = ROOT/'tmp/placeholder-migration'; debug.mkdir(parents=True, exist_ok=True)
    (debug/(key+'-probe.pdf')).write_bytes(native)
    doc = fitz.open(stream=native, filetype='pdf')
    cells = {i: [fitz.Rect(cell) for table in page.find_tables().tables for cell in table.cells if cell]
             for i, page in enumerate(doc)}
    mapped = []
    for slot in slots:
        matches = [(i, rect) for i, page in enumerate(doc) for rect in page.search_for(slot['marker'])]
        if not matches and slot['fallback']:
            continue  # Word renders DrawingML; its legacy VML copy is still filled in DOCX.
        if not matches:
            raise TemplateError('A placeholder is hidden or clipped in the Word template: '+slot['label'])
        for index, marker_rect in matches:
            slot['size'] = marker_font_size(doc[index], marker_rect)
            x, y = marker_rect.x0, marker_rect.y0
            width, height = slot['width'], slot['height']
            containing = [r for r in cells[index] if r.contains(marker_rect)] if slot['in_cell'] else []
            if containing:
                cell = min(containing, key=lambda r: r.get_area())
                # Keep separate paragraphs in a shared cell (drawer choices) at
                # their own position; ordinary value cells use their full width.
                if slot['label'].startswith('drawer_') or slot['shared']:
                    width = min(width, cell.x1-x-2)
                else:
                    x, y = cell.x0+3, cell.y0+.25
                    width, height = cell.width-6, cell.height-.5
            rect = [x, y, x+width, y+height]
            mapped.append({**{k: slot[k] for k in ('expression', 'label', 'size', 'align', 'font', 'preserve_size')}, 'page': index, 'rect': rect})
            if 'rich' in slot:mapped[-1]['rich']=slot['rich']
            doc[index].add_redact_annot(marker_rect, fill=False)
    for page in doc:
        page.apply_redactions(images=0, graphics=0)
    font_files = {'NNBody': 'times.ttf' if key=='move_in' else 'cambria.ttc',
                  'NNBold': 'timesbd.ttf' if key=='move_in' else 'cambriab.ttf',
                  'NNBank': 'simsun.ttc', 'NNHeaderSans': 'arialbd.ttf', 'NNHeaderSerif': 'timesbd.ttf'}
    # Embed portable fonts, as runtime PDF generation on Vercel has no Word install.
    from fontTools.ttLib import TTFont
    from fontTools import subset
    for alias in sorted({slot['font'] for slot in mapped}|{run['font'] for slot in mapped for run in slot.get('rich',[])}):
        font = TTFont('C:/Windows/Fonts/'+font_files[alias], fontNumber=0)
        options = subset.Options(); options.name_IDs=['*']
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=list(range(32,0x530))+list(range(0x2000,0x2070)))
        sub.subset(font)
        ascii_glyphs = {g for c,g in font.getBestCmap().items() if 32<=c<127}
        for cmap in font['cmap'].tables:
            if cmap.isUnicode():
                cmap.cmap = {c:g for c,g in cmap.cmap.items() if c<127 or g not in ascii_glyphs}
        buffer = BytesIO(); font.save(buffer)
        doc[0].insert_font(fontname=alias, fontbuffer=buffer.getvalue())
    data = doc.tobytes(garbage=4, deflate=True)
    manifest = dict(version=2, source=source_name, source_sha256=hashlib.sha256(source).hexdigest(),
                    pdf_sha256=hashlib.sha256(data).hexdigest(), slots=mapped)
    folder = ROOT/'agreements/pdf'
    (folder/(key+'.pdf')).write_bytes(data)
    (folder/(key+'.json')).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(key, len(doc), 'pages,', len(mapped), 'placeholder fields', flush=True)
    doc.close()
