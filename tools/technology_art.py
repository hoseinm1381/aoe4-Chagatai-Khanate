"""Draw Chagatai technology emblems in the gold command-card palette."""
from PIL import Image, ImageDraw

from landmark_icons import DARK as RELIEF_SHADOW, PALE, Tile

DARK = "#53351d"
GOLD = "#b98548"
LIGHT = "#e2b575"
IVORY = "#ffe5ae"
PALE_GOLD = "#edc98e"
BRONZE = "#ae7b40"
DARK_BRONZE = "#976234"
SCALE = 4


class Emblem:
    def __init__(self):
        self.image = Image.new("RGBA", (96 * SCALE, 96 * SCALE))
        self.draw = ImageDraw.Draw(self.image)

    def polygon(self, points, color, edge=DARK):
        coords = [(round(x * SCALE), round(y * SCALE)) for x, y in points]
        self.draw.polygon(coords, fill=color, outline=edge, width=2 * SCALE)

    def line(self, points, color, width=2):
        self.draw.line([(round(x * SCALE), round(y * SCALE)) for x, y in points],
                       fill=color, width=round(width * SCALE), joint="curve")

    def oval(self, bounds, color, edge=DARK):
        self.draw.ellipse(tuple(round(v * SCALE) for v in bounds), fill=color, outline=edge, width=2*SCALE)

    def arc(self, bounds, start, end, color, width=2):
        self.draw.arc(tuple(round(v * SCALE) for v in bounds), start, end, fill=color, width=round(width*SCALE))

    def spear(self, x, y, dx, dy, length, width):
        tip = (x, y)
        left = (x + dx * length - dy * width, y + dy * length + dx * width)
        right = (x + dx * length + dy * width, y + dy * length - dx * width)
        center = (x + dx * (length + 5), y + dy * (length + 5))
        self.line([center, (x + dx * (length + 28), y + dy * (length + 28))], DARK, 7)
        self.line([center, (x + dx * (length + 28), y + dy * (length + 28))], GOLD, 3)
        self.polygon([tip, left, center, right], PALE_GOLD)
        self.polygon([tip, center, right], "#9b6a3a", None)
        self.line([tip, center], "#ffe4b4")

    def horse(self, x, y, scale):
        """Engrave a steppe horse profile with a cheek plane and working bridle."""
        relief=Tile()
        def points(xy):
            return [(x+u*scale,y+v*scale) for u,v in xy]
        def face(xy, tone, edge=None):
            relief.face(points(xy),tone,edge,width=.95*scale)
        def line(xy, fill, width):
            relief.line(points(xy),fill,width*scale)
        def dot(u,v,rx,ry,fill,edge=None):
            relief.ellipse((x+(u-rx)*scale,y+(v-ry)*scale,x+(u+rx)*scale,y+(v+ry)*scale),
                           fill,edge,width=.9*scale)
        # Upright ears, a sloping bridge, a rounded muzzle and a weighted neck.
        face([(3,57),(9,46),(14,32),(17,25),(17,19),(14,12),(16,8),(21,10),(25,15),
              (28,10),(31,3),(33,5),(35,15),(39,19),(43,24),(46,29),(52,34),
              (58,38),(61,44),(59,49),(54,51),(49,48),(44,43),(39,39),(35,38),
              (32,46),(33,56),(29,61),(13,62)],"wall",RELIEF_SHADOW)
        # The crest and mane carry the dark relief, with three heavy locks.
        face([(3,57),(9,46),(13,33),(18,24),(19,16),(24,15),(31,17),(29,24),
              (23,30),(25,31),(19,40),(19,43),(15,52),(15,60),(9,62)],"side",RELIEF_SHADOW)
        line([(7,57),(12,46),(15,34),(20,25),(22,18)],"#d2a063",1.65)
        line([(12,56),(16,43),(21,34),(25,24)],"#e4b97e",1.15)
        line([(15,60),(20,47),(23,41)],"#9a6133",1.1)
        # Separate the lit bridge, jaw, and broad plane of the cheek.
        face([(30,17),(36,16),(40,21),(44,27),(48,31),(53,35),(58,39),(60,44),
              (55,44),(49,39),(44,35),(38,29),(32,26)],"crown")
        face([(33,26),(41,27),(48,36),(52,44),(48,46),(42,42),(36,38),(31,34)],"sun")
        face([(31,36),(37,38),(34,47),(34,55),(29,59),(23,60),(25,52),(27,44)],"roof")
        face([(51,43),(59,41),(61,44),(59,49),(54,50),(49,47)],"side")
        line([(17,11),(21,15),(22,19)],"#f6d398",1.4)
        line([(32,6),(31,13),(33,16)],PALE,1.35)
        line([(31,20),(36,18),(42,23),(47,30),(54,36)],PALE,1.35)
        line([(30,20),(29,25),(26,29)],"#5a3b20",2.3)
        face([(36,25),(40,24),(43,26),(40,28),(37,27)],"shadow")
        dot(39.5,25.65,1.05,.64,PALE)
        dot(56.7,43.5,2,1.15,"#4b2d18")
        line([(51,47),(57,48),(59,47)],"#efc58b",1.1)
        # Browband, cheek strap, noseband and a small bright bit ring.
        line([(32,19),(36,23),(44,24)],"#5d3b20",2.65)
        line([(33,20),(37,23),(42,23)],"#e8bf83",1.05)
        line([(35,22),(37,30),(43,36),(50,43)],"#604020",2.8)
        line([(36,25),(38,30),(44,36),(50,42)],"#e5b57a",1.05)
        line([(51,35),(48,39),(47,44)],"#704723",2.5)
        line([(52,36),(49,40),(48,44)],"#f0cb91",1.05)
        dot(49,44,2.55,2.45,"#ba864b","#f5d598")
        dot(49,44,1,1,"#6c4324")
        self.image.alpha_composite(relief.im)

    def stable(self, x, y, width, height, gate):
        roof = y + height * .31
        self.polygon([(x+3, roof), (x+width-3, roof), (x+width-3,y+height),(x+3,y+height)], GOLD)
        self.polygon([(x,roof+2),(x+width/2,y),(x+width,roof+2)], LIGHT)
        self.line([(x+4,roof+1),(x+width/2,y+3),(x+width-4,roof+1)], IVORY, 2)
        for dx in (6, width-10):
            self.polygon([(x+dx,roof+4),(x+dx+4,roof+4),(x+dx+4,y+height-2),(x+dx,y+height-2)], LIGHT)
        if gate:
            a,b=x+width*.34,x+width*.66
            self.polygon([(a,y+height),(a,roof+9),((a+b)/2,roof+4),(b,roof+9),(b,y+height)], DARK)
            self.line([(a,y+height-3),(a,roof+10),((a+b)/2,roof+5),(b,roof+10)], LIGHT)

    def wheat(self, x, y, dx):
        self.line([(x+dx*11,y-44),(x,y)], GOLD, 3)
        for k in range(5):
            x0,y0=x+dx*k*2, y-13-k*6
            self.polygon([(x0,y0),(x0-7,y0-5),(x0-7,y0-10),(x0,y0-5),(x0+6,y0-12),
                          (x0+6,y0-6)], LIGHT)

    def shoe(self):
        for start, end in ((326,360),(0,214)):
            self.arc((15,23,81,85), start, end, DARK, 16)
            self.arc((17,24,79,83), start, end, GOLD, 12)
            self.arc((24,29,72,77), start, end, IVORY, 2)
        for x,y in ((22,46),(24,62),(38,75),(57,75),(71,62),(74,46)):
            self.oval((x-2,y-2,x+2,y+2), DARK)

    def heart(self, x, y, size):
        self.oval((x,y,x+size*.58,y+size*.61), DARK_BRONZE)
        self.oval((x+size*.42,y,x+size,y+size*.61), DARK_BRONZE)
        self.polygon([(x+size*.05,y+size*.33),(x+size*.5,y+size*.18),(x+size*.95,y+size*.33),
                      (x+size*.5,y+size)], DARK_BRONZE)
        self.arc((x+3,y+3,x+size*.50,y+size*.55),185,266,IVORY,2)

    def finish(self):
        return self.image.resize((96, 96), Image.Resampling.LANCZOS)


def technology_icon(name):
    e = Emblem()
    if name == "jida_spearheads":
        e.spear(69, 19, -.52, .85, 29, 9)
        e.spear(40, 25, -.36, .93, 22, 7)
        e.spear(84, 43, -.67, .74, 21, 6)
    elif name == "yam_logistics":
        e.horse(21, 20, .94)
        e.line([(11,64),(52,64),(77,64)], DARK, 11)
        e.line([(11,63),(79,63)], IVORY, 5)
        e.polygon([(68,51),(88,63),(68,75),(72,63)], GOLD)
        e.line([(8,72),(32,72)], GOLD, 3)
    elif name == "compassionate_care":
        e.polygon([(15,54),(81,54),(73,70),(62,81),(34,81),(22,70)], GOLD)
        e.oval((15,47,81,62), LIGHT)
        e.line([(26,56),(68,56)], BRONZE, 3)
        e.line([(53,55),(70,26)], DARK, 10)
        e.line([(53,54),(69,27)], IVORY, 5)
        e.polygon([(36,51),(22,37),(24,26),(38,35),(43,47)], BRONZE)
        e.line([(25,30),(42,48)], LIGHT)
    elif name == "lamellar_reinforcement":
        e.polygon([(32,23),(45,27),(51,27),(65,23),(79,41),(69,53),(66,83),(30,83),(27,53),(17,41)], DARK)
        for row in range(4):
            y=36+row*11
            for col in range(5):
                x=27+col*9+(row%2)*2
                e.polygon([(x,y),(x+9,y-2),(x+9,y+7),(x+4,y+11),(x,y+8)], GOLD if col%2 else LIGHT)
                e.line([(x+2,y+2),(x+7,y)], IVORY)
        e.arc((35,22,62,42), 20, 160, BRONZE, 4)
    elif name == "production_1":
        e.stable(14, 23, 68, 59, True)
        e.line([(10,83),(86,83)], DARK, 4)
    elif name == "production_2":
        e.stable(12, 25, 58, 57, True)
        e.horse(45, 29, .72)
    elif name == "production_3":
        e.stable(8, 32, 44, 45, False)
        e.stable(42, 25, 43, 52, True)
        e.line([(64,28),(64,15)], DARK, 4)
        e.polygon([(64,15),(88,19),(80,25),(64,23)], DARK_BRONZE)
        e.line([(7,81),(88,81)], LIGHT, 3)
    elif name == "horse_hp_1":
        e.shoe()
    elif name == "horse_hp_2":
        e.horse(11, 22, .87)
        e.heart(65, 53, 21)
    elif name == "horse_hp_3":
        e.polygon([(17,39),(35,35),(48,23),(61,35),(79,39),(76,61),(64,77),(48,86),
                   (32,77),(20,61)], GOLD)
        e.polygon([(23,43),(38,40),(48,31),(58,40),(73,43),(69,62),(58,75),(48,80),
                   (38,75),(27,62)], BRONZE)
        e.horse(26, 32, .62)
    elif name == "livestock_1":
        for i,dx in ((28,-1),(39,-1),(49,0),(59,1),(69,1)):
            e.wheat(i, 75, dx)
        e.polygon([(28,60),(69,60),(64,68),(34,68)], DARK_BRONZE)
        e.line([(33,62),(66,62)], IVORY)
    elif name == "livestock_2":
        e.polygon([(13,51),(83,51),(75,75),(21,75)], GOLD)
        e.polygon([(11,48),(21,40),(76,40),(85,48),(77,61),(19,61)], DARK)
        for x,y in ((26,49),(39,46),(55,50),(69,45)):
            e.polygon([(x-7,y),(x-2,y-6),(x+6,y-4),(x+6,y+4),(x-4,y+5)], IVORY)
        e.line([(12,50),(20,58),(76,58),(84,50)], LIGHT, 4)
        e.line([(24,71),(73,71)], IVORY, 2)
    elif name == "livestock_3":
        e.oval((15,34,66,72), LIGHT)
        for x,y in ((22,42),(33,36),(43,42),(52,37),(29,51),(42,55),(55,52),(38,63)):
            e.oval((x-8,y-7,x+9,y+8), IVORY, GOLD)
        e.line([(24,66),(22,82)], DARK, 6)
        e.line([(51,66),(53,82)], DARK, 6)
        e.polygon([(58,37),(73,36),(83,49),(76,62),(62,57),(55,46)], GOLD)
        e.arc((61,24,85,48), 217, 356, DARK, 5)
        e.arc((62,24,85,47), 217, 354, LIGHT, 3)
        e.oval((71,43,76,48), DARK)
    else:
        raise ValueError(name)
    return e.finish()
