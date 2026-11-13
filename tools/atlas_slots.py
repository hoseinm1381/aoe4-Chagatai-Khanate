import bpy,sys,math,json
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1]); out=Path(sys.argv[-1])
data={}
for key in ('court','mint','qarshi','almaliq'):
 bpy.ops.wm.open_mainfile(filepath=str(root/f'{key}-030.blend'))
 states=bpy.context.scene['lifecycle_states'].split(', ')
 mats=set()
 for state in states:
  for o in bpy.data.collections[f'{key}_{state}'].objects:
   mats.update(o.data.materials[p.material_index].name for p in o.data.polygons)
 grid=math.ceil(math.sqrt(len(mats)))
 data[key]=dict(grid=grid,tiles={name:[i%grid,i//grid] for i,name in enumerate(sorted(mats))})
out.write_text(json.dumps(data,indent=2))
