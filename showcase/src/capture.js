// usage: node capture.js <worker> <workers> [frame list for preview]
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
(async () => {
  const [w, nw, list] = [Number(process.argv[2] || 0), Number(process.argv[3] || 1), process.argv[4]];
  const out = path.join(__dirname, list ? 'preview' : 'frames');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('PAGEERR', e.message); process.exit(1); });
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  await page.evaluate(() => window.ready);
  const frames = list ? list.split(',').map(Number) : [...Array(960).keys()].filter(n => n % nw === w);
  for (const n of frames) {
    await page.evaluate(n => window.renderFrame(n), n);
    await page.screenshot({ path: path.join(out, `f${String(n).padStart(4, '0')}.png`) });
  }
  await browser.close();
  console.log('done', w, frames.length);
})();
