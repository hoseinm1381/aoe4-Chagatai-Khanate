"""Draw the approved gold landmark silhouettes for the AoE IV command card."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

S = 4
PALE = "#ffe3aa"
GILT = "#d4a15d"
DARK = "#52341b"
STYLE = {
    "crown": ("#c18a43", "#ffe8b3"),
    "roof": ("#98602d", "#f9d99e"),
    "sun": ("#b78041", "#efd094"),
    "wall": ("#916132", "#e0b67a"),
    "side": ("#644220", "#c48d50"),
    "step": ("#9a622f", "#efc889"),
    "shadow": ("#392515", "#77512b"),
}


class Tile:
    def __init__(self):
        self.im = Image.new("RGBA", (96*S, 96*S))
        self.draw = ImageDraw.Draw(self.im)
        self.textures = {}

    def coords(self, xy):
        return [(round(x*S), round(y*S)) for x,y in xy]

    def face(self, xy, tone, edge=None, width=.85):
        points = self.coords(xy)
        mask = Image.new("L", self.im.size)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        key = (tone, min(y for _, y in points), max(y for _, y in points))
        if key not in self.textures:
            low, high = STYLE[tone]
            top, end = key[1:]
            ramp = Image.linear_gradient("L").resize((1,max(1,end-top+1)))
            light = Image.new("L", (1,96*S))
            light.paste(ramp, (0,top))
            light = ImageOps.invert(light)
            self.textures[key] = ImageOps.colorize(light,low,high).resize(self.im.size)
        self.im.paste(self.textures[key], mask=mask)
        if edge:
            self.draw.line(points+[points[0]],fill=edge,width=max(1,round(width*S)),joint="curve")

    def line(self, xy, color, width=1.4):
        self.draw.line(self.coords(xy), fill=color, width=round(width*S), joint="curve")

    def ellipse(self, xy, fill, edge=None, width=1):
        self.draw.ellipse([round(v*S) for v in xy],fill=fill,outline=edge,width=round(width*S))

    def rect(self, x0,y0,x1,y1,tone,edge=None):
        self.face([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],tone,edge)

    def step(self, left, right, y):
        self.face([(left,y),(right,y),(right+5,y+3),(left-4,y+3)],"sun")
        self.rect(left-4,y+3,right+5,y+7,"step",DARK)
        self.line([(left-2,y+3),(right+3,y+3)],PALE,1)

    def pillar(self, x, top, end, width=6):
        self.rect(x,top,x+width,end,"wall",DARK)
        self.line([(x+.9,top+1),(x+.9,end-1)],PALE,1)
        self.rect(x-1,top,x+width+1,top+2.5,"crown")

    def arch(self, x, base, half, rise):
        bottom = base
        spring = bottom-rise*.58
        peak = bottom-rise
        self.face([(x-half,bottom),(x-half,spring),(x-half*.64,peak+rise*.17),
                   (x,peak),(x+half*.64,peak+rise*.17),(x+half,spring),(x+half,bottom)],"shadow")
        self.line([(x-half,bottom),(x-half,spring),(x-half*.64,peak+rise*.17),
                   (x,peak),(x+half*.64,peak+rise*.17),(x+half,spring)],"#f3d095",1.5)

    def dome(self, x, base, half, rise):
        crown = base-rise
        self.rect(x-half*.82,base-1,x+half*.82,base+5,"wall")
        self.face([(x-half,base),(x-half*.86,base-rise*.34),(x-half*.61,base-rise*.71),
                   (x-half*.27,base-rise*.94),(x,crown),(x+half*.27,base-rise*.94),
                   (x+half*.61,base-rise*.71),(x+half*.86,base-rise*.34),(x+half,base)],"roof",DARK)
        self.face([(x,crown),(x+half*.27,base-rise*.94),(x+half*.61,base-rise*.71),
                   (x+half*.86,base-rise*.34),(x+half,base),(x+half*.19,base)],"side")
        self.line([(x-half*.82,base-rise*.34),(x-half*.57,base-rise*.70),
                   (x-half*.24,base-rise*.93),(x,crown)],PALE,1.35)
        self.line([(x-half,base),(x+half,base)],GILT,1.35)
        if half>=18:
            for sign, color in ((-1,"#f2ce90"),(1,"#b47c40")):
                self.line([(x, crown+.7),(x+sign*half*.18,base-rise*.77),
                           (x+sign*half*.39,base-rise*.39),
                           (x+sign*half*.53,base-.8)],color,1.35)
        self.line([(x,crown-4),(x,crown)],PALE,1.1)
        self.ellipse((x-1.1,crown-4.8,x+1.1,crown-2.7),PALE)

    def finish(self, frame=True):
        if frame:
            self.draw.rectangle((3*S,3*S,93*S,93*S),outline="#99703e",width=2*S)
            self.draw.rectangle((3*S,3*S,92*S,92*S),outline="#eac88d",width=S)
        return self.im.resize((96,96), Image.Resampling.LANCZOS)


def ordu(t):
    t.line([(80,22),(80,74)],DARK,3.7)
    t.line([(79.5,22),(79.5,74)],PALE,1.2)
    t.face([(80,23),(89,26),(86,31),(80,30)],"crown")
    t.line([(81,29),(86,30)],"#9b6637",1)
    t.ellipse((11,65,79,82),"#986331",DARK)
    t.face([(18,51),(74,51),(74,69),(70,75),(21,75),(17,68)],"wall",DARK)
    t.face([(62,51),(74,51),(74,69),(70,75),(60,75)],"side")
    t.dome(45,54,33,21)
    t.line([(18,58),(72,58)],PALE,1.4)
    t.line([(21,70),(70,70)],"#e2b67b",1.5)
    for x in (21,55,64):
        t.line([(x,61),(x+8,69)],"#75481f",1.25)
        t.line([(x+8,61),(x,69)],"#e2b477",1.1)
    t.arch(43,76,8,16)
    t.face([(32,61),(51,61),(55,66),(29,66)],"crown",DARK)
    t.line([(36,62),(34,65)],"#9c6738",1.4)
    t.line([(46,62),(48,65)],"#9c6738",1.4)
    t.step(35,50,76)


def almaliq(t):
    t.step(12,82,75)
    t.face([(19,32),(34,25),(77,25),(77,73),(18,73)],"wall",DARK)
    t.face([(77,25),(85,31),(85,68),(77,73)],"side",DARK)
    t.face([(25,29),(35,21),(79,21),(85,27),(77,32),(25,32)],"crown",DARK)
    t.rect(31,22,75,26,"shadow")
    t.line([(41,23),(41,26)],PALE,1.7)
    t.line([(55,23),(55,26)],PALE,1.7)
    t.line([(66,23),(66,26)],PALE,1.7)
    t.pillar(34,34,74,5)
    t.pillar(65,34,74,5)
    t.arch(52,74,12,32)
    t.line([(39,52),(43,43),(52,37),(61,43),(65,52)],PALE,1.7)
    t.line([(43,68),(43,56),(47,49),(52,46),(57,49),(61,56),(61,68)],"#bb884e",1)
    for y in (39,47,55,65):
        t.line([(71,y),(77,y)],"#d6a975",1)
        t.line([(77,y),(83,y-2)],"#785026",1)
    t.face([(9,59),(30,54),(38,62),(10,66)],"crown",DARK)
    for x,y in ((14,58),(22,56),(29,55)):
        t.line([(x,y),(x+3,y+6)],"#a7753c",1.8)
    t.pillar(11,65,74,4)
    t.pillar(29,62,74,4)


def qarshi(t):
    t.step(13,81,76)
    t.rect(14,47,82,76,"wall",DARK)
    t.face([(67,47),(82,47),(82,76),(70,76)],"side")
    t.dome(26,47,12,14)
    t.dome(70,47,12,14)
    t.dome(48,44,18,22)
    t.rect(32,49,64,76,"sun",DARK)
    t.rect(30,45,66,51,"crown",DARK)
    t.line([(33,47.5),(63,47.5)],"#a67241",1.25)
    t.pillar(33,51,76,5)
    t.pillar(58,51,76,5)
    t.arch(48,76,9,21)
    t.line([(42,74),(42,63),(48,58),(54,63),(54,74)],"#bb884d",1)
    t.line([(16,72),(31,72)],PALE,1)
    t.line([(65,72),(80,72)],GILT,1)
    for x in (23,73):
        t.arch(x,70,4,11)


def court(t):
    t.step(14,79,73)
    t.step(34,61,80)
    t.rect(21,44,75,73,"shadow",DARK)
    for x in (18,34,56,73):
        t.pillar(x,45,74,6)
    t.face([(10,46),(24,36),(32,21),(66,21),(72,33),(87,46)],"roof",DARK)
    t.face([(64,21),(72,32),(87,46),(71,44),(63,37)],"side",DARK)
    t.face([(15,42),(27,34),(34,22),(63,22),(70,41)],"sun")
    t.line([(12,45),(26,37),(33,22),(64,22)],PALE,1.45)
    t.line([(21,39),(35,38),(67,38),(76,42)],"#a8733d",1.25)
    t.line([(27,33),(40,31),(66,31)],"#edc78e",1.05)
    t.rect(11,45,85,50,"crown",DARK)
    for x in (24,34,44,54,64,74):
        t.ellipse((x-1,47,x+1,48.7),"#946130")
    t.line([(22,65),(35,65)],GILT,2.5)
    t.line([(62,65),(75,65)],GILT,2.5)
    for x in (26,31,65,70):
        t.line([(x,65),(x,73)],"#d0a163",1.25)


def ili(t):
    t.step(12,61,72)
    t.rect(14,43,60,72,"wall",DARK)
    t.face([(60,43),(72,49),(72,67),(60,72)],"side",DARK)
    t.face([(8,47),(32,28),(51,29),(68,44),(73,49),(60,49),(43,38),(17,51)],"crown",DARK)
    t.face([(32,28),(51,29),(73,49),(60,49)],"side")
    t.line([(9,46),(32,29),(59,48)],PALE,1.5)
    t.line([(20,46),(32,35),(47,45)],"#8c5b2f",1.35)
    t.line([(40,32),(61,47)],"#d1a269",1.1)
    t.line([(49,33),(66,47)],"#7e5228",1.1)
    t.line([(17,52),(58,52)],PALE,1.3)
    t.arch(29,72,7,19)
    t.arch(48,72,6,16)
    t.line([(53,72),(72,78),(88,69)],DARK,6)
    t.line([(53,70),(72,75),(88,67)],GILT,3.2)
    t.line([(54,76),(72,81),(87,73)],"#bc8951",2)
    for x,y in [(53,64),(72,68),(88,59)]:
        t.pillar(x-1,y,y+13,3.5)


def mint(t):
    t.step(12,77,76)
    t.rect(19,45,74,76,"wall",DARK)
    t.face([(63,44),(74,44),(74,76),(64,76)],"side")
    t.face([(19,45),(31,35),(39,23),(65,23),(81,43),(75,47),(18,47)],"roof",DARK)
    t.face([(62,23),(81,43),(72,45),(63,35)],"side")
    t.line([(22,41),(33,34),(40,24),(63,24)],PALE,1.55)
    t.line([(32,37),(69,37),(76,42)],"#b98249",1.3)
    t.face([(10,59),(31,42),(51,42),(65,58),(56,63),(12,63)],"crown",DARK)
    t.face([(50,42),(65,58),(56,63),(49,57)],"side")
    t.line([(15,58),(32,45),(50,45)],PALE,1.35)
    t.line([(22,56),(36,54),(52,55)],"#ac763c",1.15)
    t.pillar(16,62,76,5)
    t.arch(37,76,9,15)
    t.line([(49,64),(55,64),(55,71),(49,71),(49,64)],"#7d502a",1.1)
    t.line([(52,64),(52,71)],GILT,1)
    t.ellipse((66,62,88,84),"#ae793d",DARK,1.6)
    t.ellipse((68,64,86,81),"#dfb275","#ffe0a5",1.15)
    t.line([(77,67),(77,78)],"#81552c",1.6)
    t.line([(73,71),(77,68),(81,71)],PALE,1.4)


LANDMARKS = {
    "ordu": ordu,
    "almaliq": almaliq,
    "qarshi": qarshi,
    "court": court,
    "ili": ili,
    "mint": mint,
}


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    for name, draw in LANDMARKS.items():
        icon = Tile()
        draw(icon)
        icon.finish().save(output / (name + ".png"))


if __name__ == "__main__":
    render(Path(__file__).resolve().parents[1] / "source/tuning/assets/ui/icons/chagatai/landmarks")
