"""Build checked PDF field maps from Word exports. Run only when templates change."""
from pathlib import Path
from zipfile import ZipFile
import argparse,hashlib,json
from io import BytesIO
from fontTools import subset
from fontTools.ttLib import TTFont
import pymupdf as fitz
from lxml import etree as E
from backend.template_docx import ROOT,SOURCES,NS,cell,text

FOLDER=ROOT/'agreements/pdf'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--export',action='store_true',help='Export fresh originals using Microsoft Word on Windows.')
args=parser.parse_args()
FOLDER.mkdir(parents=True,exist_ok=True)
for key,source in SOURCES.items():
    path=FOLDER/(key+'.pdf')
    backup=ROOT/'tmp/pdfs'/(key+'-original.pdf')
    if args.export:
        from backend.renderers import word_pdf
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(word_pdf((ROOT/'agreements'/source).read_bytes()))
    if not backup.exists():raise SystemExit('Native Word exports are missing. Run with --export on Windows with Word installed.')
    doc=fitz.open(backup)
    with ZipFile(ROOT/'agreements'/source) as archive:root=E.fromstring(archive.read('word/document.xml'))
    tables=root.find('w:body',NS).findall('w:tbl',NS)
    tree=root.getroottree();slots=[]
    def add(page,rect,label,node=None,value=None,prefix='',align=0,size=10):
        r=fitz.Rect(rect)
        slots.append(dict(page=page,rect=list(r),label=label,xpath=tree.getpath(node) if node is not None else None,value=value,prefix=prefix,align=align,size=size))
    def table(pi,pdf_table,xml_table,rows,cols):
        for row in rows:
            for col in cols:
                r=fitz.Rect(pdf_table.rows[row].cells[col]);r.x0+=3;r.x1-=3;r.y0+=.25;r.y1-=.25
                add(pi,r,f'Table {pi+1} row {row+1} column {col+1}',cell(xml_table,row,col),align=1 if key=='move_in' and col!=4 else 0,size=9.5)
    if key in ('ac','noac'):
        pdf_tables=[p.find_tables().tables for p in doc]
        table(0,pdf_tables[0][0],tables[0],range(len(tables[0].findall('w:tr',NS))),[1])
        table(0,pdf_tables[0][0],tables[0],[8]+([9] if key=='ac' else []),[0])
        bank_page=2 if key=='ac' else 1
        table(bank_page,pdf_tables[bank_page][0],tables[1],range(3),[1])
        signature_tables=pdf_tables[2][1:] if key=='ac' else pdf_tables[2]
        table(2,signature_tables[0],tables[2],[2,3,4],[0,1])
        table(2,signature_tables[1],tables[3],[2,3,4],[0])
        paras=root.find('w:body',NS).findall('w:p',NS)
        note=next(p for p in paras if 'All the documents requested' in text(p))
        add(2,(68.5,566.8,532,635) if key=='ac' else (68.5,392.4,532,458),'Company privacy notice',note,size=9.5)
        if key=='ac':
            para=next(p for p in paras if 'is renting the premise' in text(p))
            add(1,(86.5,417.5,532,477.5),'Company tenancy clause',para,size=9.5)
    elif key=='rules':
        add(0,(98.4,679.7,516,691.6),'Tenant name',value='tenant_name',prefix='Name : ')
        add(0,(98.4,691.6,516,704),'Tenant ID',value='tenant_id',prefix='NRIC: ')
    else:
        pdf_tables=doc[0].find_tables().tables
        table(0,pdf_tables[0],tables[0],range(4),[1,3])
        table(0,pdf_tables[1],tables[1],range(2),[1,3])
        inv=root.xpath('//w:txbxContent/w:tbl',namespaces=NS)[0]
        table(0,pdf_tables[2],inv,range(1,22),[1,2,3,4])
        for rect,name,prefix in [((193,571.5,451,582),'company.account_name','Account Name: '),((193,582.4,451,593.5),'company.account_number','Account Number: '),((229,593.5,451,604),'company.bank',''),((86.5,706.6,310,718.4),'tenant_name','Name: '),((86.5,718.4,310,730.3),'tenant_id','NRIC No.: '),((86.5,730.3,310,742.2),'signing_date','Date: '),((338.5,706.6,550,718.4),'company.name','Name: '),((338.5,718.4,550,730.3),'company.registration','SSM No.: '),((338.5,730.3,550,742.2),'signing_date','Date: ')]:
            add(0,rect,name,value=name,prefix=prefix,size=9)
        # Remove the original diagonal drawer mark, preserving its checkbox and borders.
        doc[0].add_redact_annot((62,320,82,339),fill=False)
        doc[0].apply_redactions(images=0,graphics=1,text=1)
    # Only text in variable slots is cleared; all template lines and artwork remain.
    for slot in slots:doc[slot['page']].add_redact_annot(slot['rect'],fill=False)
    for page in doc:page.apply_redactions(images=0,graphics=0)
    # Embed document fonts once, subset to Latin/Greek/Cyrillic and punctuation.
    # Unicode outside that set uses PyMuPDF's bundled Unicode font at fill time.
    font_files={'NNBody':'times.ttf' if key=='move_in' else 'cambria.ttc','NNBold':'timesbd.ttf' if key=='move_in' else 'cambriab.ttf'}
    if key=='move_in':font_files['NNBank']='simsun.ttc'
    for alias,filename in font_files.items():
        font=TTFont('C:/Windows/Fonts/'+filename,fontNumber=0)
        options=subset.Options();options.name_IDs=['*'];subsetter=subset.Subsetter(options=options)
        subsetter.populate(unicodes=list(range(32,0x530))+list(range(0x2000,0x2070))+list(range(0x20a0,0x20d0)))
        subsetter.subset(font)
        # Keep ASCII glyphs unambiguous in PDF text extraction (e.g. hyphen vs NB hyphen).
        ascii_glyphs={glyph for code,glyph in font.getBestCmap().items() if 32<=code<127}
        for cmap in font['cmap'].tables:
            if cmap.isUnicode():
                cmap.cmap={code:glyph for code,glyph in cmap.cmap.items() if code<127 or glyph not in ascii_glyphs}
        buffer=BytesIO();font.save(buffer)
        doc[0].insert_font(fontname=alias,fontbuffer=buffer.getvalue())
    clean=doc.tobytes(garbage=4,deflate=True);doc.close();path.write_bytes(clean)
    manifest={'source':source,'source_sha256':hashlib.sha256((ROOT/'agreements'/source).read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(clean).hexdigest(),'slots':slots}
    (FOLDER/(key+'.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(key,len(slots),'mapped fields')
