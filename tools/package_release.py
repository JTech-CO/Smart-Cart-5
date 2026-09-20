#!/usr/bin/env python3
"""Create and validate a self-contained release ZIP. Standard library only."""
from pathlib import Path
import argparse,hashlib,json,zipfile,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT.parent/'Smart-Cart-5-Prototype.zip');args=ap.parse_args();out=args.output.resolve()
    if ROOT in out.parents:raise SystemExit('Write the archive outside the release root.')
    for cache in ROOT.rglob('__pycache__'):shutil.rmtree(cache)
    subprocess.run([sys.executable,str(ROOT/'tests/static_regression.py')],check=True)
    for name in ['static-qa.json','browser-fixture-qa.json','routing-review.json']:
        report=json.loads((ROOT/'docs'/name).read_text())
        if not report.get('passed'):raise SystemExit('Release gate failed: '+name)
    fc=json.loads((ROOT/'docs/cad-container-qa.json').read_text());step=json.loads((ROOT/'docs/step-qa.json').read_text())
    if not(fc['all_brep_roundtrips_valid'] and fc['forward_only_app_payload_order'] and step['valid']):raise SystemExit('CAD gate failed')
    gl=json.loads((ROOT/'docs/offscreen-render.json').read_text())
    if not(gl['program_link'] and all(v['GL_error']==0 for v in gl['views'])):raise SystemExit('Render gate failed')
    manifest=ROOT/'SHA256SUMS.txt'
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p!=manifest and '__pycache__' not in p.parts)
    forbidden=[p for p in files if p.suffix.lower() in {'.ttf','.otf','.woff','.woff2'}]
    if forbidden:raise SystemExit('Font files must not be packaged.')
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
    manifest.write_text(''.join(h+'  '+n+'\n' for n,h in hashes.items()))
    files.append(manifest);out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,str(Path(ROOT.name)/p.relative_to(ROOT)))
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for name,h in hashes.items():assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==h,name
    result={'file':out.name,'bytes':out.stat().st_size,'sha256':digest(out),'file_count':len(files),'zip_crc_pass':True,'all_manifest_hashes_pass':True,'no_font_files':True,'root':ROOT.name,'native_app_and_physical_limits':'See docs/QA-KR.md; a ZIP release is not an energization approval.'}
    out.with_suffix('.validation.json').write_text(json.dumps(result,indent=2)+'\n');out.with_suffix('.sha256').write_text(result['sha256']+'  '+out.name+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
