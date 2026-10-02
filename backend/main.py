from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse
from .models import GenerateRequest,Company
from .template_docx import INVENTORY_NAMES as INVENTORY, TemplateError
from .renderers import pdf,docx
from .auth import StaffAuth
auth = StaffAuth()
app=FastAPI(title='Nest & Nook document studio',docs_url=None,redoc_url=None,openapi_url=None)
app.middleware('http')(auth.dispatch)
from .addresses import router as address_router
app.include_router(address_router)
@app.middleware('http')
async def no_cache(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    # Form POSTs need their real Origin for the staff-login CSRF check.
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response
@app.get('/api/health')
def health():
    from .converted_pdf import available
    return {'status':'ok','word_pdf_available':available()}
@app.get('/api/defaults')
def defaults():return {'company':Company().model_dump(),'inventory':INVENTORY}
@app.post('/api/generate')
def generate(req:GenerateRequest):
    stem=re.sub(r'[^a-zA-Z0-9_-]+','-',req.details.tenant_name).strip('-')[:60] or 'tenant'
    files=[]
    try:
        for kind in req.documents:
            # The only source for the offer is PDF. Never reconstruct it as a Word document.
            extension='pdf' if req.format=='pdf' or kind=='offer' else 'docx'
            render=pdf if extension=='pdf' else docx
            variant=('-ac' if req.details.aircon else '-noac') if kind=='tenancy' else ''
            files.append((f'{stem}-{kind}{variant}.{extension}',render(kind,req.details)))
    except TemplateError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    # Word export uses a private temporary directory that is removed after conversion.
    if len(files)==1:
        name,data=files[0]
        mime='application/pdf' if name.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        buf=BytesIO()
        with ZipFile(buf,'w',ZIP_DEFLATED) as z:
            for name,data in files:z.writestr(name,data)
        name=f'{stem}-document-pack.zip';data=buf.getvalue();mime='application/zip'
    return Response(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="{name}"'})
DIST=Path(__file__).resolve().parents[1]/'frontend/dist/nest-and-nook/browser'
# Serve through authenticated Python routes. StaticFiles/public assets may be
# promoted to Vercel's CDN and would bypass the staff middleware.
@app.get('/{asset_path:path}',include_in_schema=False)
def website(asset_path:str):
    target=(DIST/(asset_path or 'index.html')).resolve()
    if not target.is_relative_to(DIST.resolve()) or not target.is_file():
        raise HTTPException(404,'Not found')
    if any(part.startswith('.') for part in Path(asset_path).parts):
        raise HTTPException(404,'Not found')
    return FileResponse(target)
