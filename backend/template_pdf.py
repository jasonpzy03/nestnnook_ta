"""Edit only variable regions of the original offer PDF; preserve all other page objects."""
from pathlib import Path
import re
import secrets
import pymupdf as fitz
from .template_docx import ROOT,TemplateError,tenure

class OfferEditor:
    def __init__(self,doc):self.doc=doc;self.edits={};self.fonts={}
    def font(self,name):
        if name not in self.fonts:
            filename={'times':'times.ttf','times-bold':'timesbd.ttf','arial':'arial.ttf','arial-bold':'arialbd.ttf'}[name]
            path=Path('C:/Windows/Fonts')/filename
            self.fonts[name]=fitz.Font(fontfile=str(path)) if path.exists() else fitz.Font({'times':'tiro','times-bold':'tibo','arial':'helv','arial-bold':'hebo'}[name])
        return self.fonts[name]
    def add(self,page,rect,value,baseline,size=10,font='times',align='left',lines=1,leading=None,label='Field'):
        rect=fitz.Rect(rect);value=str(value);fontobj=self.font(font)
        words=value.split();rows=[];line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if fontobj.text_length(candidate,fontsize=size)<=rect.width:
                line=candidate
            else:
                if line:rows.append(line)
                line=word
                if fontobj.text_length(line,fontsize=size)>rect.width:raise TemplateError(f'{label} is too long for the original offer template. Shorten this value.')
        if line:rows.append(line)
        if len(rows)>lines:raise TemplateError(f'{label} is too long for the original offer template ({lines} line'+('s' if lines!=1 else '')+'). Shorten this value.')
        self.edits.setdefault(page,[]).append((rect,rows,baseline,size,font,align,leading or size*1.15))
    def apply(self):
        for index,edits in self.edits.items():
            page=self.doc[index]
            for rect,*_ in edits:page.add_redact_annot(rect,fill=False,cross_out=False)
            # Remove original text, not merely paint over it. Keep table rules and other artwork intact.
            page.apply_redactions(images=0,graphics=0)
            for rect,rows,y,size,font,align,leading in edits:
                face=self.font(font);alias='NN'+font.replace('-','')
                page.insert_font(fontname=alias,fontbuffer=face.buffer)
                for row in rows:
                    width=face.text_length(row,fontsize=size)
                    x=rect.x0+(rect.width-width)/2 if align=='center' else rect.x0
                    page.insert_text((x,y),row,fontsize=size,fontname=alias,color=(0,0,0))
                    y+=leading

def money(v):return f'RM{v:,.2f}' if v else '-'
def source_line(page,y):
    lines=[]
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            if abs(line['bbox'][1]-y)<.3:lines.append(''.join(s['text'] for s in line['spans']).strip())
    return ' '.join(lines)

def fill_offer(d):
    if not d.reference.strip():
        d.reference=f'NN-{d.agreement_date:%Y%m%d}-{secrets.token_hex(5).upper()}'
    doc=fitz.open(ROOT/'agreements/letter of offer to rent.pdf');e=OfferEditor(doc)
    # Source field underlines are independent paths that do not move with filled text.
    # Table borders are wider; enclosure headings have fixed text and retain their styling.
    for page in list(doc)[:2]:
        for drawing in page.get_drawings():
            rect=drawing['rect']
            if drawing['type']=='s' and rect.height<.1 and 2<rect.width<200:
                page.add_redact_annot(rect+(-2,-2,2,2),fill=False,cross_out=False)
        page.apply_redactions(images=0,graphics=1,text=1)
    # Remove the sample officer signature everywhere, leaving blank signing spaces.
    signature_xrefs={info['xref'] for p in doc for info in p.get_image_info(xrefs=True) if info['width']==751 and info['height']==321}
    for xref in signature_xrefs:doc[0].delete_image(xref)
    logos=[info for info in doc[0].get_image_info(xrefs=True) if info['width']==640 and info['height']==640]
    if len(logos)!=1:raise TemplateError('The offer template logo has changed; update its field mapping.')
    logo=logos[0];doc[0].delete_image(logo['xref'])
    # Place the original business-card logo through a PDF clipping window; no raster redesign.
    card=fitz.open(ROOT/'assets/business_card.jpg');card_pdf=fitz.open('pdf',card.convert_to_pdf())
    # JPEG natural dimensions can differ from its PDF point size; scale the clip accordingly.
    cr=card_pdf[0].rect;clip=fitz.Rect(710/1050*cr.width,100/600*cr.height,985/1050*cr.width,335/600*cr.height)
    doc[0].show_pdf_page(fitz.Rect(logo['bbox']),card_pdf,0,clip=clip)
    e.add(0,(72,162.3,612,175),d.company.name,172.3,11,'arial-bold','center',label='Company name')
    # Preserve the header's centre line at x=306, independent of source padding spaces.
    e.edits[0][-1]=(fitz.Rect(72,162.3,540,175),*e.edits[0][-1][1:])
    e.add(0,(72,177,540,191),d.company.registration,187.8,12,'arial-bold','center',label='Company registration')
    e.add(0,(72,192.7,540,204.8),d.company.address,202.4,10.5,'times-bold','center',label='Company address')
    e.add(0,(72,206.6,540,219.7),'TEL NO.: '+d.company.phone,217,11.5,'times-bold','center',label='Company phone')
    invoice=doc[0].search_for('Invoice Number:INV-0560')[0]
    e.add(0,(280,236.2,540,249),'Invoice Number: '+d.reference,246.2,10,'arial',label='Invoice number')
    opening=f'I/We, {d.tenant_name} (IC/Passport No.: {d.tenant_id}), hereby offer to rent the premises stated below on an “as is where is basis”, subject to the Terms and Conditions contained in this Letter of Offer.'
    e.add(0,(72,280,540,303.4),opening,288.6,9.5,lines=2,leading=12.6,label='Tenant name and ID')
    # Keep the payment table footprint with the requested rows.
    doc[0].add_redact_annot((49,331,564,481),fill=False,cross_out=False)
    doc[0].apply_redactions(images=0,graphics=2)
    labels=['Unit number','Room number','Monthly Rental','Date of Commencement / Agreed Move-In Date','Tenancy Period','Refundable Room Deposit','1 Month Advance Rental / Pro-Rated Rental','Refundable Access Card Deposit','Agreement Fee','TOTAL PAYABLE']
    values=[d.property,d.room,money(d.rent),d.start_date.strftime('%d/%m/%Y'),tenure(d),money(d.security_deposit),money(d.advance_rent),money(d.access_deposit),money(d.agreement_fee),money(d.total)]
    row_height=14.7
    for x in [50.5,306.5,561.5]:doc[0].draw_line((x,332.5),(x,479.5),width=1)
    for i in range(11):doc[0].draw_line((50,332.5+i*row_height),(562,332.5+i*row_height),width=1)
    for i,(value,label) in enumerate(zip(values,labels)):
        top=333.0+i*row_height
        face='times-bold' if i==9 else 'times'
        e.add(0,(55.5,top,305,top+14),label,top+10,10,font=face,label=label+' label')
        e.add(0,(311.25,top,560,top+14),value,top+10,10,font=face,label=label)
    # Only clause 1's company name and defined abbreviation change; other clauses stay in place.
    paragraph=' '.join(source_line(doc[0],y) for y in [542.2,554.3,566.4])
    paragraph=paragraph.replace('Vanguard Property Asset Care Sdn. Bhd.',d.company.name).replace('VAC','N&N')
    e.add(0,(72,542,541,578.2),paragraph,551.6,10.5,lines=3,leading=12.1,label='Company name in clause 1')
    line=source_line(doc[1],96.6).replace('VAC','N&N')
    e.add(1,(72,96.4,540,108.4),line,106,10.5,label='Company reference in clause 3')
    e.add(1,(311.25,504.1,563,516.1),'Signature by Officer for and on behalf of N&N',513.3,9.5,'times-bold',label='Officer signature label')
    e.add(1,(55.5,571.3,305,583.1),'Name: '+d.tenant_name,580.3,9.5,label='Tenant name in signature')
    e.add(1,(55.5,584.8,305,595),'IC/Passport No.: '+d.tenant_id,593.6,9.5,label='Tenant ID in signature')
    e.add(1,(55.5,595,305,607),'Date: '+d.agreement_date.strftime('%d/%m/%Y'),604.2,9.5,label='Signing date')
    e.add(1,(311.25,584.8,563,595.2),'Registration No.: '+d.company.registration,593.6,9.5,label='Company registration in signature')
    e.add(1,(311.25,595.5,563,607.5),'Date: '+d.agreement_date.strftime('%d/%m/%Y'),604.8,9.5,label='Signing date')
    # Remove the transfer-fee clause and its acknowledgement reference.
    e.add(1,(71,237,543,301.5),'',247,10.5,label='Removed transfer fee clause')
    for y,title in [(304.4,'5. Binding Effect of Letter of Offer'),(370.6,'6. Special Conditions'),(412.6,'7. Tenant Acknowledgement')]:
        e.add(1,(72,y-.3,541,y+12),title,y+9.35,10.5,'times-bold',label='Renumbered heading')
    e.add(1,(72,451.4,543,463.5),'sign, and the applicable forfeiture/non-refund provisions.',461,10.5,label='Tenant acknowledgement')
    e.add(1,(72,385.2,540,409.4),d.special_conditions or '-',394.8,10.5,lines=2,leading=12.1,label='Special conditions')
    if d.include_aml:
        line=source_line(doc[2],174.3).replace('VAC X CIM SDN BHD',d.company.name)
        e.add(2,(72,174.1,540,186.7),line,184.1,11,label='Company name in enclosure')
    else:doc.delete_page(2)
    e.apply()
    # Close the removed clause's space while keeping the footer in place.
    compact=fitz.open()
    for i in range(len(doc)):
        if i!=1:
            compact.insert_pdf(doc,from_page=i,to_page=i)
            continue
        page=compact.new_page(width=doc[i].rect.width,height=doc[i].rect.height)
        page.show_pdf_page(fitz.Rect(0,0,page.rect.width,237),doc,i,clip=fitz.Rect(0,0,page.rect.width,237))
        page.show_pdf_page(fitz.Rect(0,237,page.rect.width,654),doc,i,clip=fitz.Rect(0,303,page.rect.width,720))
        page.show_pdf_page(fitz.Rect(0,720,page.rect.width,page.rect.height),doc,i,clip=fitz.Rect(0,720,page.rect.width,page.rect.height))
    result=compact.tobytes(garbage=4,deflate=True,clean=True)
    compact.close()
    doc.close();card.close();card_pdf.close()
    return result
