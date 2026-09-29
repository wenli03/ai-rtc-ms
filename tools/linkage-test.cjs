// 数字人 ↔ 文字会话 同屏联动取证（Playwright / Chromium）
// 证据口径：MJPEG 画面是浏览器真实渲染的 LiveTalking 帧；
// 用口部 ROI 的帧间变化量做量化对比（静默期 vs 播报期），不依赖"帧是否不同"这种弱判据。
const PW = 'C:/Users/47298/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright-core';
const { chromium } = require(PW);
const fs = require('fs');
const path = require('path');

const BASE = process.env.AICS_BASE || 'https://<实例ID>-3210.container.x-gpu.com';
const OUT = 'C:/qoder-space/evidence-cloud';
const QUESTION = process.argv[2] || '你们的退款政策是什么？';
const SAMPLES = Number(process.argv[3] || 12);
const GAP = 700;

const sleep = ms => new Promise(r => setTimeout(r, ms));

// 在页面里把当前 <img> 帧画进 canvas，取口部区域(纵向 55%-80%、横向 30%-70%)的平均亮度与标准差
const ROI_FN = async () => {
  const img = document.getElementById('avatar');
  if (!img.naturalWidth) return null;
  const c = document.createElement('canvas');
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0);
  const x0 = Math.floor(c.width * 0.30), x1 = Math.floor(c.width * 0.70);
  const y0 = Math.floor(c.height * 0.55), y1 = Math.floor(c.height * 0.80);
  const d = g.getImageData(x0, y0, x1 - x0, y1 - y0).data;
  const px = [];
  for (let i = 0; i < d.length; i += 4) px.push((d[i] + d[i + 1] + d[i + 2]) / 3);
  let s = 0, ss = 0, n = 0;
  for (let k = 1; k < px.length; k += 37) { const v = px[k]; s += v; ss += v * v; n++; }
  const mean = s / n;
  let dark = 0;
  for (let k = 0; k < px.length; k++) if (px[k] < 60) dark++;
  return { mean, std: Math.sqrt(Math.max(0, ss / n - mean * mean)), darkRatio: +(dark / px.length).toFixed(4), count: n };
};

async function sampleSeries(page, tag, count) {
  const rows = [];
  let prevMean = null, prevDark = null;
  let sumAbsDiff = 0, darkSwing = 0, diffs = 0;
  for (let i = 0; i < count; i++) {
    const roi = await page.evaluate(ROI_FN);
    const bytes = await page.evaluate(async () => {
      const r = await fetch('/avatar.jpg?_=' + Date.now(), { cache: 'no-store' });
      return (await r.arrayBuffer()).byteLength;
    });
    if (roi) {
      if (prevMean !== null) { sumAbsDiff += Math.abs(roi.mean - prevMean); darkSwing += Math.abs(roi.darkRatio - prevDark); diffs++; }
      prevMean = roi.mean; prevDark = roi.darkRatio;
    }
    rows.push({ i: i + 1, ts: Date.now(), mean: roi ? +roi.mean.toFixed(2) : null,
                std: roi ? +roi.std.toFixed(2) : null, darkRatio: roi ? roi.darkRatio : null, jpgBytes: bytes });
    console.log(`[${tag} #${i + 1}] ROI mean=${roi ? roi.mean.toFixed(2) : 'n/a'} std=${roi ? roi.std.toFixed(2) : 'n/a'} dark=${roi ? roi.darkRatio : 'n/a'} jpg=${bytes}B`);
    if (i < count - 1) await sleep(GAP);
  }
  const means = rows.filter(r => r.mean !== null).map(r => r.mean);
  const darks = rows.filter(r => r.darkRatio !== null).map(r => r.darkRatio);
  return {
    samples: rows.length,
    roi_mean_avg: +(means.reduce((a, b) => a + b, 0) / means.length).toFixed(2),
    roi_std_avg: +(rows.reduce((a, r) => a + (r.std || 0), 0) / rows.length).toFixed(2),
    roi_mean_range: +(Math.max(...means) - Math.min(...means)).toFixed(2),
    dark_ratio_range: +(Math.max(...darks) - Math.min(...darks)).toFixed(4),
    mean_abs_frame_delta: diffs ? +(sumAbsDiff / diffs).toFixed(3) : 0,
    mean_abs_dark_delta: diffs ? +(darkSwing / diffs).toFixed(5) : 0,
    rows,
  };
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('pageerror', e => consoleErrors.push(String(e).slice(0, 200)));

  await page.goto(BASE + '/?name=customer', { waitUntil: 'load', timeout: 60000 });
  await sleep(4000);

  const nat = await page.evaluate(() => {
    const i = document.getElementById('avatar');
    return { w: i.naturalWidth, h: i.naturalHeight, complete: i.complete, src: i.getAttribute('src') };
  });
  console.log('浏览器内数字人画面:', nat);

  await page.screenshot({ path: path.join(OUT, '12_linkage_00_page_before_join.png'), fullPage: true });

  console.log(`\n=== 阶段1：静默基线（${SAMPLES} 帧 / ${GAP}ms）===`);
  const idle = await sampleSeries(page, 'idle', SAMPLES);
  await page.locator('#avatar').screenshot({ path: path.join(OUT, '12_linkage_01_avatar_idle.png') });

  console.log('\n=== 阶段2：以客户身份入会 ===');
  await page.click('#join');
  await page.waitForFunction(
    () => document.getElementById('status').textContent.includes('已连接'),
    null, { timeout: 90000 }
  );
  console.log('status:', (await page.textContent('#status')).trim());

  console.log('\n=== 阶段3：发送提问，等待 AI 回答并驱动数字人 ===');
  const t0 = Date.now();
  await page.fill('#inp', QUESTION);
  await page.click('#send');
  await page.waitForFunction(() => /AI 答:/.test(document.getElementById('log').innerText), null, { timeout: 180000 });
  const answerWait = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`AI 首帧回答耗时 ${answerWait}s`);

  console.log(`\n=== 阶段4：播报期取帧（${SAMPLES} 帧 / ${GAP}ms）===`);
  const speak = await sampleSeries(page, 'speak', SAMPLES);
  await page.locator('#avatar').screenshot({ path: path.join(OUT, '12_linkage_02_avatar_speaking.png') });
  await page.screenshot({ path: path.join(OUT, '12_linkage_03_same_screen.png'), fullPage: true });

  await sleep(8000);
  await page.screenshot({ path: path.join(OUT, '12_linkage_04_same_screen_after.png'), fullPage: true });

  console.log(`\n=== 阶段5：播报结束后复测静默（${SAMPLES} 帧）===`);
  const post = await sampleSeries(page, 'post', SAMPLES);

  const transcript = await page.evaluate(() => document.getElementById('log').innerText);
  const members = await page.evaluate(() => document.getElementById('plist').innerText);

  const summary = {
    问题: QUESTION,
    AI首帧回答耗时s: +answerWait,
    画面来源: 'LiveTalking(GPU) → aiortc 环回观看者 avatar_bridge.py → latest.jpg → web/server.js MJPEG → 浏览器 <img>',
    浏览器内画面分辨率: nat,
    静默期: idle,
    播报期: speak,
    播报后静默期: post,
    房间成员: members,
    页面报错: consoleErrors,
  };
  fs.writeFileSync(path.join(OUT, '12_linkage_summary.json'), JSON.stringify(summary, null, 2));
  const line = s => `口部ROI mean_avg=${s.roi_mean_avg} std_avg=${s.roi_std_avg} mean_range=${s.roi_mean_range} dark_range=${s.dark_ratio_range} 帧间平均亮度变化=${s.mean_abs_frame_delta} 帧间暗区占比变化=${s.mean_abs_dark_delta}`;
  fs.writeFileSync(path.join(OUT, '12_linkage_transcript.txt'),
    `提问: ${QUESTION}\nAI 首帧回答耗时: ${answerWait}s\n房间成员:\n${members}\n\n转写:\n${transcript}\n\n` +
    `静默期   ${line(idle)}\n播报期   ${line(speak)}\n播报后   ${line(post)}\n`);

  console.log('\n=== 房间成员 ===\n' + members);
  console.log('\n=== 转写 ===\n' + transcript);
  const strip = s => JSON.stringify({ ...s, rows: undefined });
  console.log('\n静默期:', strip(idle));
  console.log('播报期:', strip(speak));
  console.log('播报后:', strip(post));
  console.log('页面报错:', consoleErrors.length ? consoleErrors : '无');
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
