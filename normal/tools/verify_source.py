"""Portable project/identity/dependency checks and execution of Lua source validation."""
import csv
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'chagatai_khanate'
GUID = '9fb54312599d47218eef70ad08c75e33'


def verify():
    manifest=ET.parse(PROJECT/'chagatai_khanate.aoe4mod').getroot()
    fields={n.tag.split('}')[-1]:n.text for n in manifest}
    assert uuid.UUID(fields['ID']).hex==GUID and fields['Type']=='Extension'
    assert fields['DataGenericPath']=='assets'
    attributes=ET.parse(PROJECT/'assets/attrib/chagatai_khanate.xml').getroot()
    assert attributes.get('guid')==GUID
    locpath=PROJECT/'assets'/fields['LocDBPath'].replace('\\','/')
    assert (PROJECT/'assets/attrib'/attributes.get('locdb_path').replace('\\','/')).resolve()==locpath.resolve()
    with locpath.with_name(locpath.stem+'_en.csv').open(encoding='utf-8-sig',newline='') as h:
        rows=list(csv.reader(h))
    assert all(len(r)==len(rows[0]) for r in rows)
    locids=[int(r[0]) for r in rows[1:]]; assert len(locids)==len(set(locids))
    instances=PROJECT/'assets/attrib/instances'; identities=[]
    files=list(instances.rglob('*.xml'))
    # EXFAT directory lookups become quadratic with the Court overlay closure.
    # Enumerate once, then validate reference membership entirely in memory.
    instance_keys={f.relative_to(instances).as_posix()[:-4].lower() for f in files}
    digest=hashlib.sha256()
    for file in sorted(files):
        raw=file.read_bytes();data=ET.fromstring(raw)
        digest.update(file.relative_to(PROJECT).as_posix().encode('utf-8')+b'\0'+hashlib.sha256(raw).digest())
        identities.append(int(data.find("uniqueid[@name='pbgid']").get('value')))
        parent=data.find("instance_reference[@name='parent_pbg']")
        for branch in data.findall('variant'):
            label=str(file)+': '+branch.get('name','')
            if parent is not None and parent.get('value'):
                assert branch.find("instance_reference[@name='parent_pbg']") is not None, 'Variant missing its own parent: '+label
            branch_id=branch.find("uniqueid[@name='pbgid']")
            assert branch_id is not None and int(branch_id.get('value'))==identities[-1], 'Variant identity missing/mismatched: '+label
        for node in data.iter():
            if node.tag=='template_reference' and node.get('value','').replace('\\','/')=='ui_command_card_info':
                assert all(int(n.get('value'))>=0 for n in node.iter('int')
                           if n.get('name') in ('ui_position_row','ui_position_column')), 'Negative Xbox grid coordinate: '+str(file)
            if node.tag=='locstring' and node.get('mod')==GUID:
                assert int(node.get('value')) in locids, 'Missing locale row'
            if node.tag=='instance_reference' and node.get('mod')==GUID:
                assert node.get('value').replace('\\','/').lower() in instance_keys, 'Missing local reference in '+str(file)+': '+node.get('value')
    assert len(identities)==len(set(identities)), 'Duplicate project PBG IDs'
    assert {1073741823,1073741824}<=set(identities), 'Editor-generated Horse identities changed'
    entry=PROJECT/'assets/scar/winconditions/chagatai_khanate.rdo'
    rdo=ET.parse(entry).getroot()
    scar=rdo.find(".//DataProperty[@Name='m_scarWinConditionFile']").get('Value')
    assert (PROJECT/'assets/scar'/(scar.replace('\\','/')+'.scar')).exists()
    tuning=rdo.find(".//DataProperty[@Name='m_tuningModGUID']").get('Value')
    assert tuning==GUID
    # Resolve project imports from the actual registered entry, not arbitrary
    # files elsewhere in the workspace or sibling packs.
    seen=set()
    def walk(file):
        if file in seen: return
        seen.add(file)
        for imported in re.findall(r'import\("([^"]+)"\)',file.read_text(encoding='utf-8-sig')):
            if imported.startswith('chagatai/'):
                dependency=PROJECT/'assets/scar'/imported
                assert dependency.exists(), 'Missing project import: '+imported
                walk(dependency)
    walk(PROJECT/'assets/scar/winconditions/chagatai_khanate.scar')
    assert len(seen)==17, 'Unexpected loader dependency set'
    assert not any('/court/' in key for key in instance_keys), 'Retired damage overlays must stay outside assets'
    assert not (PROJECT/'assets/scar/chagatai/damage_catalog.scar').exists(), 'Retired overlay catalog must stay outside assets'
    extra=[PROJECT/'chagatai_khanate.aoe4mod',PROJECT/'assets/mod.rdo',PROJECT/'assets/attrib/chagatai_khanate.xml']
    for folder in ('scar','locdb'):
        extra.extend(p for p in (PROJECT/'assets'/folder).rglob('*') if p.suffix in ('.scar','.rdo','.csv','.locdb'))
    for path in sorted(extra):digest.update(path.relative_to(PROJECT).as_posix().encode('utf-8')+b'\0'+hashlib.sha256(path.read_bytes()).digest())
    print(f'Project source verified: {len(identities)} instances; {len(seen)} loaded project SCAR files.')
    return {'instances':len(identities),'loaded_project_scar_files':len(seen),'source_sha256':digest.hexdigest(),'native_validated':False}


if __name__ == "__main__":
    verify()
