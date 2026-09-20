#!/usr/bin/env python3
"""Local data and package invariants. Standard library only; no CAD approval."""
from pathlib import Path
import json,re,hashlib,math,xml.etree.ElementTree as E,csv
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def test(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
a=json.loads((ROOT/'data/assembly.json').read_text());p=json.loads((ROOT/'data/parameters.json').read_text());geometry=(ROOT/'data/geometry.bin').read_bytes()
test('Model and parameter basis match',a['parameters']==p)
refs=[c['id'] for c in a['components']];test('Component identifiers unique',len(refs)==len(set(refs)))
ids=[w['id'] for w in a['connections']];test('Wire identifiers unique',len(ids)==len(set(ids))==50)
endpoints=[]
for w in a['connections']:
 for term in ['from','to']:endpoints.append(w[term] in a['ports'])
 for term,point in [('from',w['sampled_mm'][0]),('to',w['sampled_mm'][-1])]:
  expected=a['ports'][w[term]]['point'];endpoints.append(math.dist(expected,point)<1e-5)
test('Every wire ends at its declared modeled port',all(endpoints))
expected=0;valid=True
for g in a['geometry']:
 valid=valid and g['offset']==expected and g['count']%3==0 and g['ref'] in refs
 expected+=g['count']*24
test('Binary geometry offsets and counts are complete',valid and expected==len(geometry),{'bytes':len(geometry)})
test('Triangle count matches binary metadata',sum(g['count']//3 for g in a['geometry'])==a['counts']['triangles'])
rows=list(csv.DictReader((ROOT/'data/connections.csv').open(encoding='utf-8-sig')))
test('Connection CSV and model IDs match',ids==[r['id'] for r in rows])
for k in ['deck','battery','drive','caster','handle','routing']:test('Parameter section '+k,k in p)
test('Explicit unresolved motor diameter conflict','102mm alternative is NOT cleared' in p['provenance']['drive.motor_body_diameter'])
missing=[]
for f in [ROOT/'index.html',ROOT/'wiring.html',ROOT/'README.md',ROOT/'README-KR.md']:
 text=f.read_text();links=re.findall(r'(?:href|src)="([^"]+)"',text)+re.findall(r'\]\(([^)]+)\)',text)
 for link in links:
  if '://' in link or link.startswith(('#','data:','mailto:')):continue
  link=link.split('#')[0].split('?')[0]
  if link and not(f.parent/link).exists():missing.append({'file':str(f.relative_to(ROOT)),'link':link})
test('HTML and README local links exist',not missing,missing)
test('Only local runtime script dependencies',all('://' not in link for f in [ROOT/'index.html',ROOT/'wiring.html'] for link in re.findall(r'<script src="([^"]+)"',f.read_text())))
report={'scope':'Static data, endpoint, binary layout, links and CSV consistency. No native browser/physical/electrical approval.','checks':checks,'passed':all(c['passed'] for c in checks)}
(ROOT/'docs/static-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for c in checks:print(('PASS' if c['passed'] else 'FAIL'),c['name'])
raise SystemExit(0 if report['passed'] else 1)
