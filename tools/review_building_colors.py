"""Render and measure four gameplay-like offline views of each building mask."""
from argparse import ArgumentParser
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw

BASE=[(100,66,43),(170,146,109),(56,122,196),(81,48,28),
      (88,62,45),(77,82,79),(53,110,186),(144,121,80)]
BACKGROUND=(43,54,55)

def one(data,angle,red=False):
    c,s=math.cos(angle),math.sin(angle)
    p=[(x*c-y*s,(x*s+y*c)*.63-z*.78,(x*s+y*c)*.78+z*.63) for x,y,z in data["verts"]]
    bounds=[(min(q[i] for q in p),max(q[i] for q in p)) for i in (0,1)]
    scale=185/max(high-low for low,high in bounds)
    center_x,center_y=((low+high)/2 for low,high in bounds)
    img=Image.new("RGB",(250,218),BACKGROUND)
    m=Image.new("L",img.size,0)
    draw,mask=ImageDraw.Draw(img),ImageDraw.Draw(m)
    for i in sorted(range(len(data["faces"])),key=lambda k:sum(p[n][2] for n in data["faces"][k])):
        f=data["faces"][i]
        tile=data["tiles"][i]
        a,b,c=[p[n] for n in f]
        u=[b[k]-a[k] for k in range(3)]
        v=[c[k]-a[k] for k in range(3)]
        normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        length=math.sqrt(sum(x*x for x in normal))
        if length<1e-8:continue
        tinted=tile in (2,6)
        color=(189,53,50) if red and tinted else BASE[tile]
        shade=.76+.28*sum(a*b for a,b in zip(normal,(-.18,.25,.90)))/length
        coords=[(125+scale*(p[n][0]-center_x),105+scale*(p[n][1]-center_y)) for n in f]
        draw.polygon(coords,fill=tuple(max(0,min(255,round(x*shade+11))) for x in color))
        mask.polygon(coords,fill=2 if tinted else 1)
    hist=m.histogram()
    return img,round(hist[2]/(hist[2]+hist[1]),3)

def review(geometry,output):
    models=json.loads(geometry.read_bytes())
    board=Image.new("RGB",(1000,690),BACKGROUND)
    draw=ImageDraw.Draw(board)
    results={}
    for i,(name,data) in enumerate(models.items()):
        views=[one(data,angle,i%2==0) for angle in (.59,2.16,3.73,5.30)]
        x=i%4*250
        y=i//4*230
        board.paste(views[0][0],(x,y))
        draw.text((x+14,y+209),name.replace("_"," ").title(),fill="#e8ddc6")
        results[name]=[value for _,value in views]
    (output/"building-visible-masks.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    board.save(output/"building-review.png")
    print(results)

if __name__=="__main__":
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("geometry",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    review(args.geometry,args.output)
