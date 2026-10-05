from lxml import etree as E
from backend.rich_pdf import styled_expression
from backend.template_docx import NS


def test_heading_bold_and_direct_override():
    styles=E.fromstring(f'''<w:styles xmlns:w="{NS['w']}">
      <w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>
      <w:style w:styleId="Heading"><w:basedOn w:val="Normal"/><w:rPr><w:b/></w:rPr></w:style>
      <w:style w:styleId="Signature"><w:basedOn w:val="Heading"/></w:style>
    </w:styles>''')
    p=E.fromstring(f'''<w:p xmlns:w="{NS['w']}">
      <w:pPr><w:pStyle w:val="Signature"/></w:pPr>
      <w:r><w:t>Signature by {{{{company.name}}}}</w:t></w:r>
      <w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t> regular</w:t></w:r>
    </w:p>''')
    runs=styled_expression(p.findall('w:r/w:t',NS),'NNBody',styles)
    assert runs==[{'expression':'Signature by {{company.name}}','font':'NNBold'},
                  {'expression':' regular','font':'NNBody'}]
