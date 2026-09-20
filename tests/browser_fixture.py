#!/usr/bin/env python3
"""Browser DOM/input/CPU-render tests with local fixture data.
Does not claim native HTTP navigation or browser WebGL success.
Use CHROMIUM_PATH to choose an installed browser. No browser policies are bypassed.
"""
from pathlib import Path
import base64,json,re,os,time,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
checks=[];errors=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
    print(('PASS ' if ok else 'FAIL ')+name,flush=True)
def fixture(page,name):
    html=(ROOT/name).read_text()
    scripts=re.findall(r'<script src="([^"]+)"></script>',html)
    html=re.sub(r'<script src="[^"]+"></script>','',html)
    for css in re.findall(r'<link rel="stylesheet" href="([^"]+)">',html):
        html=html.replace(f'<link rel="stylesheet" href="{css}">','<style>'+(ROOT/css).read_text()+'</style>')
    page.set_content(html,wait_until='domcontentloaded')
    page.evaluate('(m)=>window.fixtureModel=m',json.loads((ROOT/'data/assembly.json').read_text()))
    if name=='index.html':
        blob=(ROOT/'data/geometry.bin').read_bytes();page.evaluate('(n)=>window.fixtureBytes=new Uint8Array(n)',len(blob))
        for offset in range(0,len(blob),4*1024*1024):
            chunk=base64.b64encode(blob[offset:offset+4*1024*1024]).decode()
            page.evaluate('({s,offset})=>{const b=atob(s);for(let i=0;i<b.length;i++)fixtureBytes[offset+i]=b.charCodeAt(i)}',{'s':chunk,'offset':offset})
    page.evaluate("()=>{window.fetch=async url=>String(url).endsWith('assembly.json')?new Response(JSON.stringify(fixtureModel),{status:200,headers:{'Content-Type':'application/json'}}):new Response(window.fixtureBytes||new Uint8Array(),{status:200});}")
    for s in scripts:page.add_script_tag(content=(ROOT/s).read_text())
def sync(page):
    page.evaluate('()=>{D5.renderer.invalid=false;D5.renderer.draw()}')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1,accept_downloads=True)
    page.on('pageerror',lambda e:errors.append(str(e)))
    fixture(page,'index.html');page.wait_for_function('window.D5 && D5.renderer.vp',timeout=30000);sync(page)
    backend=page.evaluate('D5.renderer.backend');reason=page.evaluate('D5.renderer.fallbackReason||null')
    check('Actual production scripts initialize',not page.locator('#loader').is_visible(),{'backend':backend,'reason':reason})
    check('Default view applied',page.evaluate("D5.currentView==='overall'&&D5.renderer.state.distance===2.16"))
    check('Triangle metadata and 50 connections loaded',page.evaluate('D5.model.counts.triangles===D5.model.geometry.reduce((s,g)=>s+g.count/3,0) && D5.model.connections.length===50'))
    page.screenshot(path=str(ROOT/'assets/previews/ui-overall.png'))
    for key in ['underside','drive','power','controls','front','top','overall']:
        page.locator(f'[data-view="{key}"]').click();sync(page)
        check('Preset '+key,page.evaluate('(k)=>D5.currentView===k',key))
        if key=='underside':
            check('Underside disables ground',page.evaluate('!D5.renderer.groundVisible() && D5.renderer.state.pitch<0'))
            page.screenshot(path=str(ROOT/'assets/previews/ui-underside.png'))
    # Actual pointer events cross the horizon; not only direct state changes.
    rect=page.locator('#scene').bounding_box();x=rect['x']+rect['width']*.65;y=rect['y']+rect['height']*.65
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y-180,steps=3);page.mouse.up();sync(page)
    check('Pointer orbit below horizon removes floor',page.evaluate('D5.renderer.state.pitch<0 && !D5.renderer.groundVisible()'))
    page.mouse.move(x,y-180);page.mouse.down();page.mouse.move(x,y+10,steps=3);page.mouse.up();sync(page)
    check('Pointer orbit above horizon restores floor',page.evaluate('D5.renderer.state.pitch>.035 && D5.renderer.groundVisible()'))
    page.locator('#scene').focus();before=page.evaluate('D5.renderer.state.yaw');page.keyboard.press('ArrowRight');sync(page)
    check('Keyboard rotation',abs(page.evaluate('D5.renderer.state.yaw')-before-.1)<1e-7)
    page.locator('#search').fill('PI4');check('Search filters component tree',page.locator('#tree .part').count()==1)
    page.locator('#tree .part').click();sync(page);check('Pi inspector and grade',page.locator('#inspect-id').inner_text()=='PI4' and page.locator('#inspector').is_visible())
    page.locator('#focus').click();sync(page);check('Selection focus changes distance',page.evaluate('D5.renderer.state.distance<.6'))
    page.locator('#close-inspector').click();page.locator('#search').fill('');page.locator('[data-view="overall"]').click();sync(page)
    for option in ['deck','covers','wires','floor','labels','accessories']:
        old=page.locator('#opt-'+option).is_checked();page.locator('#opt-'+option).set_checked(not old);sync(page)
        check('Layer toggle '+option,page.evaluate('(o)=>D5.renderer.state[o]',option)==(not old));page.locator('#opt-'+option).set_checked(old);sync(page)
    # Pick the rasterized visible deck pixel then use the application's actual mouse path.
    if backend=='Canvas CPU':
        pos=page.evaluate("""()=>{const r=D5.renderer,id=r.ids.get('CART-DECK');for(let i=0;i<r.picks.length;i++)if(r.picks[i]===id){const x=i%r.canvas.width,y=Math.floor(i/r.canvas.width);if(y>r.canvas.height*.30&&y<r.canvas.height*.70){const b=r.canvas.getBoundingClientRect();return[b.left+(x+.5)*b.width/r.canvas.width,b.top+(y+.5)*b.height/r.canvas.height]}}return null}""")
        if pos:page.mouse.click(*pos);sync(page)
        check('Pixel picking selects a visible mesh',bool(pos) and page.evaluate("D5.renderer.state.selection==='CART-DECK'"))
    page.locator('#close-inspector').click()
    # Native download machinery is exercised on a Blob; local HTTP remains separate.
    try:
        with page.expect_download(timeout=10000) as dl:page.locator('#snapshot').click()
        path=dl.value.path();raw=Path(path).read_bytes();check('PNG Blob downloaded with PNG signature',raw[:8]==b'\x89PNG\r\n\x1a\n',{'bytes':len(raw)})
    except Exception as e:check('PNG Blob downloaded with PNG signature',False,str(e))
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(600);sync(page)
    check('Mobile page has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.locator('#menu').click();check('Mobile component drawer opens',page.locator('#sidebar').is_visible());page.locator('#search').fill('SCMB-L');page.locator('#tree .part').click();check('Mobile part selection closes drawer',not page.locator('#sidebar').is_visible());page.locator('#close-inspector').click();page.evaluate("D5.setView('overall')");sync(page)
    check('Mobile overall frame includes wheel and handle limits',page.evaluate("[[-335,-339,100],[482,0,380],[-473,159,980]].every(p=>D5.renderer.project(p)!==null)"))
    page.screenshot(path=str(ROOT/'assets/previews/ui-mobile.png'))
    # The 2D page gets the identical connection source, independent of the renderer.
    wire=browser.new_page(viewport={'width':1600,'height':1100},accept_downloads=True);wire.on('pageerror',lambda e:errors.append(str(e)));fixture(wire,'wiring.html');wire.wait_for_function('window.D5Wiring',timeout=10000)
    check('Wiring table has 50 connections',wire.locator('#wire-rows tr').count()==50)
    check('Physical drawing contains 50 routed polylines',wire.locator('#routing .wire').count()==50)
    wire.locator('#kind').select_option('power');expected=wire.evaluate("D5Wiring.model.connections.filter(w=>w.kind==='power').length");check('Wiring category filter',wire.locator('#routing .wire').count()==expected)
    wire.locator('#projection').select_option('side');check('Side projection label', 'X-Z' in wire.locator('#routing').text_content())
    wire.locator('#kind').select_option('all');wire.evaluate("D5Wiring.detail('W01')");check('Wire inspector has endpoints', 'BAT1.P' in wire.locator('#wire-detail').inner_text())
    for tab in ['logical','table','physical']:
        # actual tab names are recovered from the shipped HTML below
        pass
    for i in range(wire.locator('[data-tab]').count()):
        tab=wire.locator('[data-tab]').nth(i);target=tab.get_attribute('data-tab');tab.click();check('Wiring tab '+target,wire.locator('#'+target).is_visible())
    wire.evaluate("D5Wiring.setTab('table')");wire.locator('#wire-search').fill('W01');check('Connection search',wire.locator('#wire-rows tr').count()==1)
    wire.locator('#wire-rows tr').click();check('Table row opens selected physical route',wire.locator('#physical').is_visible() and 'W01' in wire.locator('#wire-detail').inner_text())
    wire.locator('#projection').select_option('top');wire.screenshot(path=str(ROOT/'assets/previews/ui-wiring.png'))
    try:
        with wire.expect_download(timeout=10000) as dl:wire.locator('#svg-download').click()
        raw=Path(dl.value.path()).read_text();check('SVG Blob download', '<svg' in raw and 'polyline' in raw)
    except Exception as e:check('SVG Blob download',False,str(e))
    wire.set_viewport_size({'width':390,'height':844});wire.wait_for_timeout(200);check('Mobile wiring has no page overflow',wire.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check('No runtime page errors',not errors,errors)
    report={'scope':'Actual shipped HTML/CSS/JS with set_content and fixture-injected local JSON/mesh; pointer/keyboard, rendering, selection and Blob downloads. Not a native HTTP/file navigation test.', 'browser':browser.version,'renderer':backend,'browser_webgl2_test':backend=='WebGL 2','native_http_navigation_test':False,'native_cad_gui_test':False,'checks':checks,'passed':all(c['passed'] for c in checks),'errors':errors}
    (ROOT/'docs/browser-fixture-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');browser.close()
if not all(c['passed'] for c in checks):raise SystemExit(1)
