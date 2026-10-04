"""Read effective formatting from Word's PDF export, including inherited styles."""
import pymupdf as fitz
from backend.template_docx import TemplateError
from backend.template_docx import NS, W


def paragraph_alignment(paragraph, styles):
    """Resolve header alignment using Word's paragraph style inheritance."""
    direct=paragraph.find('w:pPr/w:jc',NS)
    if direct is not None:
        return {'center':1,'right':2,'end':2}.get(direct.get(W+'val'),0)
    style=paragraph.find('w:pPr/w:pStyle',NS)
    style_id=style.get(W+'val') if style is not None else None
    if style_id is None:
        default=styles.xpath('./w:style[@w:type="paragraph"][@w:default="1"]',namespaces=NS)
        style_id=default[0].get(W+'styleId') if default else None
    seen=set()
    while style_id and style_id not in seen:
        seen.add(style_id)
        matches=styles.xpath('./w:style[@w:styleId=$id]',id=style_id,namespaces=NS)
        if not matches:break
        node=matches[0];alignment=node.find('w:pPr/w:jc',NS)
        if alignment is not None:return {'center':1,'right':2,'end':2}.get(alignment.get(W+'val'),0)
        parent=node.find('w:basedOn',NS)
        style_id=parent.get(W+'val') if parent is not None else None
    return 0


def marker_font_size(page, rect):
    candidates = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                overlap = fitz.Rect(span['bbox']) & rect
                if not overlap.is_empty:
                    candidates.append((overlap.get_area(), span['size']))
    if not candidates:
        raise TemplateError('Could not read the Word font size for a PDF field.')
    return round(max(candidates)[1], 2)
