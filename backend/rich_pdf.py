"""Preserve bold emphasis when a mapped clause contains editable fields."""
import re
from itertools import groupby
from .placeholders import TOKEN, substitute
from .template_docx import NS, W, TemplateError


def inherited_bold(node, styles):
    if styles is None:
        return None
    lookup={s.get(W+'styleId'):s for s in styles.findall('w:style',NS)}
    default=styles.find('w:docDefaults/w:rPrDefault/w:rPr/w:b',NS)
    value=default is not None and default.get(W+'val') not in ('0','false','off')
    def apply(style_id, seen):
        nonlocal value
        if not style_id or style_id in seen or style_id not in lookup:return
        seen.add(style_id);style=lookup[style_id]
        parent=style.find('w:basedOn',NS)
        if parent is not None:apply(parent.get(W+'val'),seen)
        bold=style.find('w:rPr/w:b',NS)
        # Bold is a toggle property in Word styles; direct run formatting is
        # an absolute override and is applied separately below.
        if bold is not None and bold.get(W+'val') not in ('0','false','off'):value=not value
    p=next(node.iterancestors(W+'p'),None)
    paragraph_style=p.find('w:pPr/w:pStyle',NS) if p is not None else None
    default_style=next((s.get(W+'styleId') for s in lookup.values()
                        if s.get(W+'type')=='paragraph' and s.get(W+'default')=='1'),None)
    apply(paragraph_style.get(W+'val') if paragraph_style is not None else default_style,set())
    run_style=node.getparent().find('w:rPr/w:rStyle',NS)
    if run_style is not None:apply(run_style.get(W+'val'),set())
    return value


def styled_expression(nodes, base_font, style_tree=None):
    text='';styles=[]
    for node in nodes:
        value=node.text or '';bold=node.getparent().find('w:rPr/w:b',NS)
        alias=base_font
        inherited=inherited_bold(node,style_tree)
        if inherited is not None:alias='NNBold' if inherited else 'NNBody'
        if bold is not None:
            alias='NNBody' if bold.get(W+'val') in ('0','false','off') else 'NNBold'
        text+=value;styles.extend([alias]*len(value))
    # A placeholder split across runs is one value and takes its opening run's style.
    for match in TOKEN.finditer(text):
        styles[match.start():match.end()]=[styles[match.start()]]*len(match[0])
    result=[];offset=0
    for alias,group in groupby(styles):
        count=len(list(group));result.append({'expression':text[offset:offset+count],'font':alias});offset+=count
    return result


def rich_layout(parts, fields, fonts, rect, size, label):
    content='';styles=[]
    for part in parts:
        value=substitute(part['expression'],fields)
        content+=value;styles.extend([part['font']]*len(value))
    words=[]
    for match in re.finditer(r'\S+',content):
        runs=[];offset=match.start()
        for alias,group in groupby(styles[match.start():match.end()]):
            count=len(list(group));runs.append((content[offset:offset+count],alias));offset+=count
        words.append(runs)
    minimum=min(7,size)
    while size>=minimum:
        rows=[];row=[];width=0;too_wide=False
        for word in words:
            word_width=sum(fonts[alias].text_length(text,fontsize=size) for text,alias in word)
            if word_width>rect.width:too_wide=True;break
            gap=fonts[word[0][1]].text_length(' ',fontsize=size) if row else 0
            if row and width+gap+word_width>rect.width:
                rows.append(row);row=[];width=0;gap=0
            if row:row.append((' ',word[0][1]))
            row.extend(word);width+=gap+word_width
        if row:rows.append(row)
        ascent=max(fonts[part['font']].ascender for part in parts)*size
        descent=min(fonts[part['font']].descender for part in parts)*size
        leading=size*1.2
        if not too_wide and ascent-descent+max(0,len(rows)-1)*leading<=rect.height:
            return rows,size,leading,ascent
        size=round(size-.25,2)
    raise TemplateError(f'{label} is too long for the PDF template. Shorten this value or download Word format.')
