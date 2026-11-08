from pathlib import Path
from PIL import Image,ImageEnhance,ImageOps,ImageFilter
import numpy as np
import json,os,sys
R=Path(os.environ["CK_RUN"])
asset=sys.argv[-1]
doc=json.loads((R/f"{asset}-materials.json").read_bytes())
out=R/f"{asset}-atlas"
out.mkdir(exist_ok=True)
SIZE=2048
ATLAS_SPECS={"albedo":(56,42,28,255),"normal":(128,128,255,255),"roughness":(211,211,211,255),"metalness":(0,0,0,255),"pattern":(0,0,0,0)}
atlas={name:Image.new("RGBA",(SIZE,SIZE),value) for name,value in ATLAS_SPECS.items()}
out_map={}
def resized(im,w,h,span):
    im=im.resize((round(w/span),h),Image.Resampling.LANCZOS)
    if im.width==w:return im
    dst=Image.new(im.mode,(w,h))
    dst.paste(im,(0,0));dst.paste(im,(im.width,0))
    return dst
def paste_pad(target,im,x,y,pad):
    w,h=im.size
    target.paste(im,(x,y))
    target.paste(im.crop((0,0,1,h)).resize((pad,h)),(x-pad,y))
    target.paste(im.crop((w-1,0,w,h)).resize((pad,h)),(x+w,y))
    target.paste(target.crop((x-pad,y,x+w+pad,y+1)).resize((w+2*pad,pad)),(x-pad,y-pad))
    target.paste(target.crop((x-pad,y+h-1,x+w+pad,y+h)).resize((w+2*pad,pad)),(x-pad,y+h))
pad=8
slot=0
used={}
big=[name for name in doc if ("canopy" in name or "embroidered resource-yard" in name) and doc[name]["mask"]]
assert len(big)==1
for name,d in sorted(doc.items()):
    signature=tuple((k,tuple(v) if isinstance(v,list) else v) for k,v in d.items())
    if signature in used:
        out_map[name]=used[signature]
        continue
    if name==big[0]:
        x,y,w,h=pad,pad,2048-pad*2,880-pad*2
    else:
        x,y=slot%8*256+pad,880+slot//8*256+pad
        w=h=256-pad*2
        slot+=1
    assert y+h+pad<=SIZE,(name,slot)
    v=d["base"]
    if v:
        with Image.open(v) as im:source=im.convert("RGBA")
        pix=resized(source,w,h,d["u_span"])
        if d["soot"]<1:
            channel=pix.getchannel("A")
            pix=ImageEnhance.Brightness(pix.convert("RGB")).enhance(d["soot"]).convert("RGBA")
            pix.putalpha(channel)
        if not d["alpha"]:pix.putalpha(255)
    else:
        def srgb(a):return round(255*(12.92*a if a<=.0031308 else 1.055*a**(1/2.4)-.055))
        pix=Image.new("RGBA",(w,h),(*[srgb(a) for a in d["color"][:3]],255))
    paste_pad(atlas["albedo"],pix,x,y,pad)
    if d["mask"]:
        with Image.open(d["mask"]) as im:r=resized(im.convert("RGB").getchannel("R"),w,h,d["u_span"])
        z=Image.new("L",(w,h),0)
        paste_pad(atlas["pattern"],Image.merge("RGBA",(r,z,z,z)),x,y,pad)
    rough=d["roughness"]
    paste_pad(atlas["roughness"],Image.new("RGBA",(w,h),(rough,rough,rough,255)),x,y,pad)
    # Subtle height-derived grain is a conventional tangent-space normal input.
    g=np.asarray(pix.convert("L").filter(ImageFilter.GaussianBlur(.75)),dtype=np.float32)
    dy,dx=np.gradient(g)
    normals=np.stack((128-dx*.38,128+dy*.38,np.full_like(g,255),np.full_like(g,255)),axis=-1)
    paste_pad(atlas["normal"],Image.fromarray(np.uint8(np.clip(normals,0,255))),x,y,pad)
    out_map[name]=used[signature]=[x,y,w,h,d["u_span"],SIZE]
for key,image in atlas.items():image.save(out/(key+".png"))
(out/"uv.json").write_text(json.dumps(out_map,indent=2))
r=atlas["pattern"].getchannel("R").histogram()
coverage=sum(r[128:])/SIZE**2
assert .15<=coverage<=.50,coverage
print(asset,"atlas coverage",coverage,"small tiles",slot)
