const { chromium } = require('@playwright/test');
const path = require("node:path");
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:3037/allocation', {waitUntil: 'networkidle'});
  await page.getByRole('tab', {name: 'Current snapshot', exact: true}).click();
  await page.getByRole('heading', {name: 'Current momentum ranking', exact: true}).waitFor();
  const region = page.getByRole('region', {name: 'Current momentum ranking'});
  const rows = region.getByRole('row');
  assert.equal(await rows.count(), 9);
  for (const [i,ticker] of ['TSM','V','UNH','NVDA','COST','MSFT','AVGO','ORCL'].entries()) {
    assert((await rows.nth(i+1).innerText()).includes(ticker));
  }
  assert.equal(await region.getByText('33⅓%', {exact:true}).count(), 3);
  assert((await page.getByRole('tabpanel').innerText()).includes('Month-end preview'));
  await page.screenshot({path: path.join(__dirname, 'current-snapshot-desktop.png'), fullPage: true});
  await page.setViewportSize({width: 390,height:844});
  await page.waitForFunction(() => document.querySelector('aside').getBoundingClientRect().right <= 1);
  await page.screenshot({path: path.join(__dirname, 'current-snapshot-mobile.png'), fullPage:true, animations:'disabled'});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.getByRole('tab', {name:'Historical research',exact:true}).click();
  await page.getByText('Last historical selection',{exact:true}).waitFor();
  // A later browser clock must suppress current weights while history remains usable.
  await page.clock.install({time:new Date('2026-11-03T04:00:00Z')});
  await page.reload({waitUntil:'networkidle'});
  await page.getByRole('tab',{name:'Current snapshot',exact:true}).click();
  await page.getByRole('heading',{name:'Current ranking unavailable',exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:'Current momentum ranking'}).count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS real-page desktop/mobile ranking, all 8 rows, top3 weights, history switch, stale suppression; no page errors.');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
