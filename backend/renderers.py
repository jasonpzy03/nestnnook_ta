"""Generate documents from original Word templates and mapped PDF backgrounds."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
import os
import subprocess
from .template_docx import fill_docx,TemplateError
from .template_pdf import fill_offer

WORD_LOCK=Lock()
SCRIPT=Path(__file__).with_name('word_to_pdf.ps1')

def docx(kind,details):return fill_docx(kind,details)

def word_pdf(data):
    if os.name!='nt':raise TemplateError('PDF export of Word templates requires Microsoft Word on Windows. Select Original formats to download the filled templates.')
    # Word renders the actual edited template. There is no substitute layout or silent fallback.
    with WORD_LOCK, TemporaryDirectory(prefix='nest-nook-') as folder:
        source=Path(folder)/'document.docx';target=Path(folder)/'document.pdf'
        source.write_bytes(data)
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(SCRIPT),'-InputPath',str(source),'-OutputPath',str(target)],capture_output=True,timeout=90,creationflags=flags)
        except subprocess.TimeoutExpired as exc:
            raise TemplateError('Word PDF export timed out. Close any Word startup dialogs and try again, or select Original formats.') from exc
        if result.returncode or not target.exists():
            raise TemplateError('Microsoft Word could not export the template. Check that Word opens normally, or select Original formats to download it.')
        return target.read_bytes()

def pdf(kind,details):
    from .converted_pdf import fill_converted
    return fill_offer(details) if kind=='offer' else fill_converted(kind,details)
