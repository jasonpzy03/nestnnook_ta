"""Build checked PDF field maps from native Word exports after template changes."""
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
    path=FOLDER/(key+'.pdf');backup=ROOT/'tmp/pdfs'/(key+'-header-original.pdf')
    if args.export:
        from backend.renderers import word_pdf
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(word_pdf((ROOT/'agreements'/source).read_bytes()))
    if not backup.exists():raise SystemExit('Run with --export on Windows with Word installed.')
    doc=fitz.open(backup)
    with ZipFile(ROOT/'agreements'/source) as archive:
        root=E.fromstring(archive.read('word/document.xml'))
        header=E.fromstring(archive.read('word/nest-header.xml'))
    tables=root.find('w:body',NS).findall('w:tbl',NS)
    tree=root.getroottree();slots=[];drawer=None
    pdf_tables=[(i,t) for i,p in enumerate(doc) for t in p.find_tables().tables]
    def locate(phrase,last=False):
        matches=[(i,r) for i,p in enumerate(doc) for r in p.search_for(phrase)]
        if not matches:raise ValueError('PDF text anchor missing: '+phrase)
        return matches[-1 if last else 0]
    def add(page,rect,label,node=None,value=None,prefix='',align=0,size=10,font='NNBody'):
        slots.append(dict(page=page,rect=list(fitz.Rect(rect)),label=label,xpath=tree.getpath(node) if node is not None else None,value=value,prefix=prefix,align=align,size=size,font=font))
    def table(found,xml_table,rows,cols):
        pi,pdf_table=found
        for row in rows:
            for col in cols:
                r=fitz.Rect(pdf_table.rows[row].cells[col]);r.x0+=3;r.x1-=3;r.y0+=.25;r.y1-=.25
                label=text(cell(xml_table,row,0)).strip()
                add(pi,r,label or f'Table row {row+1}',cell(xml_table,row,col),align=1 if key=='move_in' and col!=4 else 0,size=9.5,font='NNBold' if key in ('ac','noac') and xml_table is tables[0] and col==0 else 'NNBody')
    if key in ('ac','noac'):
        count=len(tables[0].findall('w:tr',NS))
        first=next(x for x in pdf_tables if x[1].row_count==count)
        table(first,tables[0],range(count),[1]);table(first,tables[0],[8]+([9] if key=='ac' else []),[0])
        table(next(x for x in pdf_tables if x[1].row_count==3),tables[1],range(3),[1])
        signatures=[x for x in pdf_tables if x[1].row_count==5]
        assert len(signatures)==2
        table(signatures[0],tables[2],[2,3,4],[0,1]);table(signatures[1],tables[3],[2,3,4],[0])
        paras=root.find('w:body',NS).findall('w:p',NS)
        note=next(p for p in paras if 'All the documents requested' in text(p))
        pi,r=locate('**Note: All the documents requested')
        add(pi,(68.5,r.y0-.5,532,min(doc[pi].rect.height-30,r.y0+68)),'Company privacy notice',note,size=9.5)
        if key=='ac':
            para=next(p for p in paras if 'is renting the premise' in text(p))
            pi,r=locate('Nest & Nook Property Care is renting')
            add(pi,(86.5,r.y0-.5,532,r.y0+60),'Company tenancy clause',para,size=9.5)
    elif key=='rules':
        for phrase,field,prefix in [('Name : DI CHIA SENG','tenant_name','Name : '),('NRIC: 961004-01-5879','tenant_id','NRIC: ')]:
            pi,r=locate(phrase)
            add(pi,(98.4,r.y0-.3,516,r.y1+.6),'Tenant '+field,value=field,prefix=prefix)
    else:
        table(next(x for x in pdf_tables if x[1].row_count==4),tables[0],range(4),[1,3])
        table(next(x for x in pdf_tables if x[1].row_count==2),tables[1],range(2),[1,3])
        inventory=next(x for x in pdf_tables if x[1].row_count==22)
        inv=root.xpath('//w:txbxContent/w:tbl',namespaces=NS)[0]
        table(inventory,inv,range(1,22),[1,2,3,4])
        pi=inventory[0];row=inventory[1].rows[5].cells[0]
        # Drawer checkboxes are fixed offsets within the makeup-table item cell.
        drawer={'page':pi,'with':[68,row[1]+13.9],'without':[68,row[1]+25.6]}
        dy=drawer['without'][1]
        doc[pi].add_redact_annot((62,dy-5,82,dy+14),fill=False);doc[pi].apply_redactions(images=0,graphics=1,text=1)
        for phrase,name,prefix,x0,x1 in [('Account Name:','company.account_name','Account Name: ',193,451),('Account Number:','company.account_number','Account Number: ',193,451),('Bank:','company.bank','',229,451)]:
            pi,r=locate(phrase,last=True)
            add(pi,(x0,r.y0-.4,x1,r.y1+.5),name,value=name,prefix=prefix,size=9,font='NNBank')
        # Signature text can move onto another page; locate the actual native export.
        for phrase,name,prefix,x0,x1,which in [('DI CHIA SENG','tenant_name','Name: ',86.5,310,0),('961004-01-5879','tenant_id','NRIC No.: ',86.5,310,0),('NEST & NOOK PROPERTY CARE','company.name','Name: ',338.5,550,0),('202603156166 (KT0615852-M)','company.registration','SSM No.: ',338.5,550,0),('1 JULY 2026','signing_date','Date: ',86.5,310,0),('1 JULY 2026','signing_date','Date: ',338.5,550,1)]:
            matches=[(i,r) for i,p in enumerate(doc) for r in p.search_for(phrase)]
            pi,r=matches[-2+which] if name=='signing_date' else matches[-1]
            add(pi,(x0,r.y0-.3,x1,r.y1+.5),name,value=name,prefix=prefix,size=9,font='NNBold')
    margins=root.find('w:body/w:sectPr/w:pgMar',NS)
    left=int(margins.get('{'+NS['w']+'}left'))/20
    right=doc[0].rect.width-int(margins.get('{'+NS['w']+'}right'))/20
    for mark in header.xpath('//w:bookmarkStart',namespaces=NS):
        field=mark.get('{'+NS['w']+'}name').removeprefix('NestHeader_')
        pi,r=locate(text(mark.getparent()))
        size={'name':11,'registration':12,'address':10.5,'phone':11.5}[field]
        add(0,(left,r.y0-.3,right,r.y1+1),'Company header '+field,value='company.'+field,prefix='TEL NO.: ' if field=='phone' else '',align=1,size=size,font='NNHeaderSans' if field in ('name','registration') else 'NNHeaderSerif')
    for slot in slots:doc[slot['page']].add_redact_annot(slot['rect'],fill=False)
    for page in doc:page.apply_redactions(images=0,graphics=0)
    font_files={'NNBody':'times.ttf' if key=='move_in' else 'cambria.ttc','NNBold':'timesbd.ttf' if key=='move_in' else 'cambriab.ttf','NNHeaderSans':'arialbd.ttf','NNHeaderSerif':'timesbd.ttf'}
    if key=='move_in':font_files['NNBank']='simsun.ttc'
    for alias,filename in font_files.items():
        font=TTFont('C:/Windows/Fonts/'+filename,fontNumber=0)
        options=subset.Options();options.name_IDs=['*'];subsetter=subset.Subsetter(options=options)
        subsetter.populate(unicodes=list(range(32,0x530))+list(range(0x2000,0x2070))+list(range(0x20a0,0x20d0)))
        subsetter.subset(font)
        ascii_glyphs={glyph for code,glyph in font.getBestCmap().items() if 32<=code<127}
        for cmap in font['cmap'].tables:
            if cmap.isUnicode():cmap.cmap={code:glyph for code,glyph in cmap.cmap.items() if code<127 or glyph not in ascii_glyphs}
        buffer=BytesIO();font.save(buffer);doc[0].insert_font(fontname=alias,fontbuffer=buffer.getvalue())
    clean=doc.tobytes(garbage=4,deflate=True);doc.close();path.write_bytes(clean)
    manifest={'source':source,'source_sha256':hashlib.sha256((ROOT/'agreements'/source).read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(clean).hexdigest(),'slots':slots,'drawer':drawer}
    (FOLDER/(key+'.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(key,len(slots),'mapped fields')
