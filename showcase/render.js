#!/usr/bin/env node
// video.html を Playwright のヘッドレス Chromium で全フレーム PNG 書き出しする。
//   node render.js --content content.json --out out/frames [--workers 6] [--frames 0,120,400]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const content = path.resolve(arg('content', 'content.json'));
const outDir = path.resolve(arg('out', 'out/frames'));
const workers = +arg('workers', 6);
const only = arg('frames', null);
const MIME = { '.html': 'text/html', '.json': 'application/json', '.woff2': 'font/woff2' };

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const server = http.createServer((req, res) => {
    const u = decodeURIComponent(req.url.split('?')[0]);
    const file = u === '/content.json' ? content : path.join(__dirname, path.normalize(u));
    if (!file.startsWith(__dirname) && file !== content) { res.writeHead(403); return res.end(); }
    fs.readFile(file, (e, buf) => {
      if (e) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
      res.end(buf);
    });
  }).listen(0, '127.0.0.1');
  await new Promise(r => server.on('listening', r));
  const url = `http://127.0.0.1:${server.address().port}/video.html`;

  const browser = await chromium.launch();
  const pages = [];
  for (let w = 0; w < workers; w++) {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    page.on('pageerror', e => { console.error('page error:', e.message); process.exit(1); });
    await page.goto(url);
    pages.push(page);
  }
  const total = await pages[0].evaluate(() => window.ready);
  await Promise.all(pages.slice(1).map(p => p.evaluate(() => window.ready)));
  const frames = only ? only.split(',').map(Number) : [...Array(total).keys()];
  let next = 0, done = 0;
  const t0 = Date.now();
  await Promise.all(pages.map(async page => {
    while (next < frames.length) {
      const n = frames[next++];
      const b64 = await page.evaluate(n => { renderFrame(n); return document.getElementById('c').toDataURL('image/png').slice(22); }, n);
      fs.writeFileSync(path.join(outDir, `f${String(n).padStart(5, '0')}.png`), Buffer.from(b64, 'base64'));
      if (++done % 100 === 0) console.log(`${done}/${frames.length} frames (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
  }));
  console.log(`done: ${done} frames -> ${outDir}`);
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
