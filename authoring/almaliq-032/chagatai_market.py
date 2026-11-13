"""Paint full-strength owner cloth onto the market's actual atlas tiles."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from PIL import Image
from lifecycle_repair import stage,prior,repos
sys.path.insert(0,str(prior))
from chagatai_cloth import levels,encode_bc3,encode_srgb_bc1,rr
atlas=json.loads((prior/'chagatai/atlas-slots.json').read_text())['almaliq']
prefix='art/scenario/chagatai/almaliq_healthy/almaliq_healthy_'
art=prior/'chagatai/baseline'
out=stage/'chagatai'
out.mkdir(exist_ok=True)
members={k:prefix+k+'.rrtex' for k in ('albedo','pattern')}
def get(key):
    dds=out/(key+'.dds')
    rr.decode_rrtex(art/members[key],dds,validate_stream=True)
    return np.array(Image.open(dds).convert('RGBA'))
albedo,pattern=get('albedo'),get('pattern')
dim=albedo.shape[0]
grid=atlas['grid']
selected=('030 market / roof / dyed felt','Saffron market smoke-dark wool',
          '030 market / roof / dyed felt / scorched','030 market / roof / dyed felt / charred')
for material in selected:
    x,y=atlas['tiles'][material]
    step=dim//grid
    ys,xs=slice(dim-(y+1)*step,dim-y*step),slice(x*step,(x+1)*step)
    texels=albedo[ys,xs,:3]
    light=texels @ np.array([.2126,.7152,.0722])
    lo,hi=np.percentile(light,[5,95])
    luminance=np.clip((light-lo)/max(8,hi-lo),0,1)*35+108
    if material.endswith(('scorched','charred')): luminance*=.78
    texels[:]=np.rint(luminance[:,:,None]).astype(np.uint8)
    pattern[ys,xs,0]=255
for key,pixels in [('albedo',albedo),('pattern',pattern)]:
    path=out/key
    im=Image.fromarray(pixels)
    im.save(path.with_suffix('.png'))
    template=((repos/'aoe4-korea/inputs/native/art/kr036/architecture/gyeongbok_palace.rrtex') if key=='albedo' else (art/members[key])).read_bytes()
    data=encode_srgb_bc1(template,members[key],im) if key=='albedo' else encode_bc3(template,members[key].removesuffix('.rrtex'),list(levels(im)))
    path.with_suffix('.rrtex').write_bytes(data)
print('Almaliq dye painted on market canopy and pennant cloth tiles',selected)

