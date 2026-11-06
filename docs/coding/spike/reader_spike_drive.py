import json,sys,re
from playwright.sync_api import sync_playwright
T={"plain":"target words","emoji":"TARGET-EMOJI","nfd":"TARGET-NFD","crlf":"TARGET-CRLF","markdown":"TARGET-MD"}
SEL="""(target)=>{const root=document.querySelector('#didi-reader');
 const nodes=[...root.childNodes].filter(n=>n.nodeType===1);
 for(const el of nodes){const t=el.firstChild;if(!t)continue;const i=t.data.indexOf(target);if(i>=0){
  const r=document.createRange();r.setStart(t,i);r.setEnd(t,i+target.length);const s=getSelection();s.removeAllRanges();s.addRange(r);
  root.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));return true}}return false}"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); ext=[]
    pg.on('request',lambda r: ext.append(r.url) if 'localhost' not in r.url and not r.url.startswith(('data:','blob:')) else None)
    pg.goto('http://localhost:8598',timeout=60000); pg.wait_for_selector('#didi-reader',timeout=60000)
    for name,target in T.items():
        pg.locator('[data-testid="stSelectbox"]').click(); pg.get_by_role('option',name=name,exact=True).click(); pg.wait_for_timeout(1500)
        print(name,'selected',pg.evaluate(SEL,target)); pg.wait_for_timeout(2000)
        code=pg.locator('[data-testid="stCode"]').first.inner_text() if pg.locator('[data-testid="stCode"]').count() else ''
        d=json.loads(code) if code else {}
        print('  ',d.get('start'),d.get('end'),'py==target',d.get('py')==target,'browser==target',d.get('browser')==target)
        pg.wait_for_timeout(1500)
        print('   highlighted spans:',pg.evaluate("[...document.querySelectorAll('#didi-reader .hl')].map(e=>e.textContent)"),' full text intact len', pg.evaluate("Array.from(document.querySelector('#didi-reader').textContent).length"))
    # selection across a highlight boundary on emoji doc (spans now split)
    pg.locator('[data-testid="stSelectbox"]').click(); pg.get_by_role('option',name='emoji',exact=True).click(); pg.wait_for_timeout(2000)
    print('spans before',pg.evaluate("[...document.querySelectorAll('#didi-reader span')].map(e=>[e.dataset.start,e.className,e.textContent])"))
    pg.evaluate("""()=>{const root=document.querySelector('#didi-reader');const sp=[...root.querySelectorAll('span')];
      const a=sp[0].firstChild,z=sp[sp.length-1].firstChild;const i=a.data.indexOf('then');const j=z.data.indexOf('Next')+4;
      const r=document.createRange();r.setStart(a,i);r.setEnd(z,j);const s=getSelection();s.removeAllRanges();s.addRange(r);
      root.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));}""")
    pg.wait_for_timeout(2500)
    d=json.loads(pg.locator('[data-testid="stCode"]').first.inner_text()); print('across spans',d['start'],d['end'],repr(d['py']),'match',d['py']==d['browser'])
    # real mouse drag on plain doc
    pg.locator('[data-testid="stSelectbox"]').click(); pg.get_by_role('option',name='plain',exact=True).click(); pg.wait_for_timeout(2000)
    box=pg.locator('#didi-reader').bounding_box(); pg.mouse.move(box['x']+2,box['y']+8); pg.mouse.down(); pg.mouse.move(box['x']+140,box['y']+8,steps=8); pg.mouse.up(); pg.wait_for_timeout(2500)
    d=json.loads(pg.locator('[data-testid="stCode"]').first.inner_text()); print('mouse drag',d['start'],d['end'],repr(d['py']),'match',d['py']==d['browser'])
    print('text survives rerun:',pg.evaluate("document.querySelector('#didi-reader').textContent.startsWith('Plain text')"))
    print('external requests',ext[:5])
    b.close()
