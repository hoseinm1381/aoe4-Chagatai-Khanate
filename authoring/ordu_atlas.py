"""Create the Ordu's native material textures from its retained palette."""
import math
from pathlib import Path
import random
import sys
from PIL import Image

COLORS = [(100,66,43),(170,146,109),(151,117,82),(81,48,28),
          (88,62,45),(77,82,79),(135,101,73),(144,121,80)]
TEAM = {2,6}
WORK = Path(sys.argv[1])
WORK.mkdir(parents=True,exist_ok=True)
rng = random.Random(7115)
images = {name:Image.new("RGBA",(512,256)) for name in
          ("albedo","normal","roughness","metalness","pattern")}
pixels = {name:image.load() for name,image in images.items()}
for y in range(256):
    for x in range(512):
        tile = ((255-y)//128)*4+x//128
        grain = (math.sin(y*.94+x*.13)+math.sin(x*.59-y*.17))*2.4
        noise = rng.gauss(0,4.0)+grain
        if tile in (1,2,6):
            noise += (x%3-1)*2+(y%3-1)*2
            if x%47 in (0,1) and y%6 < 4:
                noise += 12
        elif tile in (3,4):
            noise += 7*math.sin(x*.43+math.sin(y*.082))
        rgb = tuple(max(0,min(255,round(c+noise))) for c in COLORS[tile])
        pixels["albedo"][x,y]=(*rgb,255)
        pixels["normal"][x,y]=(round(128+grain),round(128-noise*.45),254,255)
        pixels["roughness"][x,y]=(207 if tile==5 else 229,)*3+(255,)
        pixels["metalness"][x,y]=(147 if tile==5 else 0,)*3+(255,)
        pixels["pattern"][x,y]=(240 if tile in TEAM else 0,0,0,0)
for name,image in images.items():
    image.save(WORK/(name+".png"))
