const {chromium,expect}=require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs=require('node:fs');const assert=require('node:assert/strict');
const root=require('node:path').resolve(__dirname,'../../../..');
const base=process.env.MOMENTUM_BASE_URL || 'http://127.0.0.1:3001';
const baseline=JSON.parse(fs.readFileSync(`${root}/web/data/momentum.json`,'utf8'));
const out=__dirname;fs.mkdirSync(out,{recursive:true});
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});
 for(const width of [320,390,1440])for(const theme of ['light','dark']){
  const p=await b.newPage({viewport:{width,height:1000},colorScheme:theme});
  await p.addInitScript(t=>localStorage.setItem('desk.theme',t),theme);
  await p.goto(`${base}/momentum`,{waitUntil:'networkidle'});
  await expect(p.getByRole('heading',{name:'Market references',exact:true})).toBeVisible();
  for(const name of ['Monthly model basket','Daily ranking and entry boundary','Recent moves and price anchors','This cycle · execution reference','Rank history'])await expect(p.getByRole('heading',{name,exact:true})).toBeVisible();
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${width}/${theme} overflow`);
  assert.equal(await p.locator('details').getAttribute('open'),null);
  const basketY=await p.getByRole('heading',{name:'Monthly model basket',exact:true}).evaluate(e=>e.getBoundingClientRect().top+scrollY);
  assert(basketY<800,`basket not near first screen: ${basketY}`);
  await p.locator('details > summary').click();await expect(p.getByText('Stock price evidence',{exact:true})).toBeVisible();
  await expect(p.getByText('Market reference evidence',{exact:true})).toBeVisible();
  await p.locator('details > summary').click();
  await p.evaluate(()=>window.scrollTo(0,0));
  await expect.poll(()=>p.evaluate(()=>scrollY)).toBe(0);
  await p.screenshot({path:`${out}/${width}-${theme}.png`,fullPage:true});
  console.log(`PASS layout ${width}/${theme}: bounded width, early basket, details toggle, all references`);
  await p.close();
 }
 const p=await b.newPage({viewport:{width:1440,height:1000}});await p.clock.install({time:new Date(Math.max(Date.now(),Date.parse(baseline.generated_at_utc)+10000))});
 let mode='new',calls=0;
 const newer=structuredClone(baseline);newer.generated_at_utc=new Date(Date.parse(baseline.generated_at_utc)+1000).toISOString();newer.price_evidence.primary_source.name='Verified refresh fixture';
 const recovery=structuredClone(newer);recovery.generated_at_utc=new Date(Date.parse(newer.generated_at_utc)+1000).toISOString();recovery.price_evidence.primary_source.name='Recovered refresh fixture';
 await p.route('**/api/momentum',async route=>{
  calls++;
  if(mode==='error')return route.fulfill({status:503,json:{data:null,error:'Fixture unavailable'}});
  if(mode==='invalid'){const bad=structuredClone(newer);bad.context.stocks[0].close='not a price';return route.fulfill({json:{data:bad,error:null}});}
  const data=mode==='old'?baseline:mode==='recover'?recovery:newer;return route.fulfill({json:{data,error:null}});
 });
 await p.goto(`${base}/momentum`,{waitUntil:'networkidle'});
 const button=()=>p.getByRole('button',{name:'Refresh snapshot',exact:true});
 await button().click();await expect(button()).toBeEnabled();await expect.poll(()=>p.locator('details').textContent()).toContain('Verified refresh fixture');
 console.log('PASS new snapshot replaces server props');
 mode='error';await button().click();await expect(p.getByRole('status')).toContainText('Could not load a newer snapshot');await expect.poll(()=>p.locator('details').textContent()).toContain('Verified refresh fixture');
 console.log('PASS failed refresh keeps verified snapshot and reports failure');
 mode='invalid';await button().click();await expect(button()).toBeEnabled();await expect(p.getByRole('status')).toContainText('Could not load a newer snapshot');await expect.poll(()=>p.locator('details').textContent()).toContain('Verified refresh fixture');
 console.log('PASS malformed snapshot rejected');
 mode='old';await button().click();await expect(button()).toBeEnabled();await expect.poll(()=>p.locator('details').textContent()).toContain('Verified refresh fixture');
 console.log('PASS older snapshot cannot overwrite newer data');
 mode='recover';const before=calls;await p.clock.fastForward(61000);await expect.poll(()=>calls).toBeGreaterThan(before);await expect.poll(()=>p.locator('details').textContent()).toContain('Recovered refresh fixture');await expect(p.getByRole('status')).not.toContainText('Could not');
 console.log('PASS 60-second polling recovers without a page reload');
 mode='error';await p.clock.fastForward(5*86400000);await expect(p.getByRole('heading',{name:'Monthly model basket',exact:true}).locator('xpath=ancestor::section')).toContainText('fresh, complete price panel');await expect(p.getByText('33⅓%',{exact:true})).toHaveCount(0);
 console.log('PASS stale snapshot hides weights even when refresh fails');
 await p.close();await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
