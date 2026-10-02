"""Fill pre-converted PDF templates without Word, using the existing DOCX field logic."""
from io import BytesIO
from zipfile import ZipFile
import hashlib,json
import pymupdf as fitz
from lxml import etree as E
from .template_docx import ROOT,NS,TemplateError,fill_docx,text,date_text

FOLDER=ROOT/'agreements/pdf'

def available():
    return all((FOLDER/(key+ext)).is_file() for key in ('ac','noac','rules','move_in') for ext in ('.pdf','.json'))

def field_value(slot,root,details):
    if slot['xpath']:
        namespaces={**NS,**{k:v for k,v in root.nsmap.items() if k}}
        found=root.xpath(slot['xpath'],namespaces=namespaces)
        if len(found)!=1:raise TemplateError('The Word template structure changed. Rebuild the PDF field map.')
        return text(found[0]) or '-'
    key=slot['value']
    value=date_text(details.agreement_date,True) if key=='signing_date' else getattr(details.company,key.split('.')[1]) if key.startswith('company.') else getattr(details,key)
    return slot['prefix']+(str(value).strip() or '-')

def layout(value,font,rect,size,label):
    # Fit within the original cell; never silently clip or truncate entered text.
    while size>=7:
        rows=[]
        for paragraph in value.splitlines() or ['-']:
            line=''
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if font.text_length(candidate,fontsize=size)<=rect.width:line=candidate
                else:
                    if line:rows.append(line)
                    line=word
            if line:rows.append(line)
        leading=size*1.2
        height=(font.ascender-font.descender)*size+max(0,len(rows)-1)*leading
        if height<=rect.height and all(font.text_length(row,fontsize=size)<=rect.width for row in rows):return rows,size,leading
        size=round(size-.25,2)
    raise TemplateError(f'{label} is too long for the PDF template. Shorten this value or download Word format.')

def fill_converted(kind,details,blank=False):
    key=('ac' if details.aircon else 'noac') if kind=='tenancy' else kind
    try:
        mapping=json.loads((FOLDER/(key+'.json')).read_text(encoding='utf-8'))
        source=(ROOT/'agreements'/mapping['source']).read_bytes()
        data=(FOLDER/(key+'.pdf')).read_bytes()
    except (OSError,ValueError,KeyError) as exc:raise TemplateError('Converted PDF template is missing. Rebuild the PDF templates.') from exc
    if hashlib.sha256(source).hexdigest()!=mapping['source_sha256'] or hashlib.sha256(data).hexdigest()!=mapping['pdf_sha256']:
        raise TemplateError('A document template changed. Rebuild and verify the PDF field map before generating PDFs.')
    with ZipFile(BytesIO(fill_docx(kind,details))) as archive:root=E.fromstring(archive.read('word/document.xml'))
    with fitz.open(stream=data,filetype='pdf') as doc:
        fonts={name:fitz.Font(fontbuffer=doc.extract_font(xref)[3]) for xref,_,_,_,name,*_ in doc[0].get_fonts() if name.startswith('NN')}
        for slot in mapping['slots']:
            value=field_value(slot,root,details)
            # Downloadable blank copies retain company details, clause text and labels.
            if blank and slot['xpath'] and '/w:tbl[1]/' in slot['xpath'] and kind=='tenancy' and slot['xpath'].endswith('/w:tc[2]'):value='-'
            if blank and slot['value']=='signing_date':value='Date: -'
            if blank and kind=='tenancy' and slot['xpath'] and '/w:tbl[3]/w:tr[5]/' in slot['xpath']:value='Date: -'
            rect=fitz.Rect(slot['rect']);page=doc[slot['page']]
            alias='NNBank' if key=='move_in' and slot['value'] and slot['value'].startswith('company.') and rect.y0<605 else 'NNBold' if (key=='move_in' and rect.y0>700) or (kind=='tenancy' and '/w:tbl[1]/' in (slot['xpath'] or '') and slot['xpath'].endswith('/w:tc[1]')) else 'NNBody'
            font=fonts[alias]
            if any(not font.has_glyph(ord(c)) for c in value if not c.isspace()):
                alias='NNUnicode';font=fonts.setdefault(alias,fitz.Font('cjk'))
                if any(not font.has_glyph(ord(c)) for c in value if not c.isspace()):raise TemplateError(f"{slot['label']} contains a character unsupported by the PDF fonts.")
            rows,size,leading=layout(value,font,rect,slot['size'],slot['label'])
            page.insert_font(fontname=alias,fontbuffer=font.buffer)
            y=rect.y0+font.ascender*size
            for row in rows:
                x=rect.x0+(rect.width-font.text_length(row,fontsize=size))/2 if slot['align']==1 else rect.x0
                page.insert_text((x,y),row,fontsize=size,fontname=alias)
                y+=leading
        if key=='move_in' and details.makeup_table_drawer!='not_applicable':
            y=313.5 if details.makeup_table_drawer=='with' else 325.2
            doc[0].draw_line((68,y+8),(76.8,y),width=.8)
        doc.set_metadata({})
        doc.subset_fonts()
        return doc.tobytes(garbage=4,deflate=True)
