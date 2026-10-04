import pymupdf as fitz
import pytest
from backend.converted_pdf import layout
from backend.template_docx import TemplateError
from scripts.pdf_marker import marker_font_size
from scripts.pdf_marker import paragraph_alignment
from lxml import etree as E
from backend.template_docx import NS


@pytest.mark.parametrize('size', [6, 8, 9, 10.5, 14])
def test_marker_reads_word_exported_size(size):
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_text((50,50),'ZAA',fontsize=size)
        page.insert_text((50,80),'Unrelated text',fontsize=20)
        assert marker_font_size(page,page.search_for('ZAA')[0])==size


def test_small_template_font_stays_small():
    _,size,_=layout('Company name',fitz.Font('helv'),fitz.Rect(0,0,300,30),6,'Header',True)
    assert size==6


def test_header_size_is_not_silently_reduced_to_fit():
    font=fitz.Font('helv');rect=fitz.Rect(0,0,80,14)
    _,size,_=layout('Company name',font,rect,14,'Header')
    assert size<14
    with pytest.raises(TemplateError):
        layout('Company name',font,rect,14,'Header',True)


def test_header_alignment_uses_word_styles_and_defaults():
    namespace=NS['w']
    styles=E.fromstring(f'<w:styles xmlns:w="{namespace}"><w:style w:styleId="Centered"><w:pPr><w:jc w:val="center"/></w:pPr></w:style><w:style w:styleId="Header"><w:basedOn w:val="Centered"/></w:style></w:styles>')
    p=E.fromstring(f'<w:p xmlns:w="{namespace}"/>')
    assert paragraph_alignment(p,styles)==0
    p=E.fromstring(f'<w:p xmlns:w="{namespace}"><w:pPr><w:pStyle w:val="Header"/></w:pPr></w:p>')
    assert paragraph_alignment(p,styles)==1
