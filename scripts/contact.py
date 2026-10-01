from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
out=Path('tmp/qa')
for prefix in ['tenancy-ac','tenancy-noac','house-rules','move-in','offer']:
 files=sorted(out.glob(prefix+'-*.png'));images=[Image.open(f) for f in files]
 canvas=Image.new('RGB',(sum(i.width for i in images),max(i.height for i in images)), '#ddd')
 x=0
 for im in images:canvas.paste(im,(x,0));x+=im.width
 canvas.save(out/f'{prefix}-contact.jpg')
