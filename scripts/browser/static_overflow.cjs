// scripts/browser/static_overflow.cjs — 읽기 전용. **정적 HTML 파일 하나**(예: build_ledger_page.py 의 출력)를 폭 넷(390 · 768 · 1024 · 1400)에서
// 열어 화면 밖으로 나가는 요소를 찍는다. 서버를 띄우는 overflow.cjs 의 정적 파일 판 — 대장 페이지는 서버 화면이 아니라 이것으로 잰다.
// 쓰는 법  NODE_PATH=$(npm root -g) node scripts/browser/static_overflow.cjs <파일.html>      (Chromium 경로는 PLAYWRIGHT_CHROMIUM 로 바꿀 수 있다)
// [2026-09-27] 이 스크립트가 세션 스크래치패드에만 있었다(U-35 형태) — 저장소로.
const { chromium } = require("playwright");
const file = process.argv[2];
if (!file) { console.error("쓰는 법: node scripts/browser/static_overflow.cjs <파일.html>"); process.exit(2); }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || "/opt/pw-browsers/chromium" });
  const page = await browser.newPage();
  for (const w of [390, 768, 1024, 1400]) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto("file://" + file);
    const r = await page.evaluate(() => {
      const iw = window.innerWidth, out = [];
      for (const el of document.querySelectorAll("body *")) {
        const b = el.getBoundingClientRect();
        if (b.right > iw + 1 && b.width > 0 && el.children.length < 40) {
          const t = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (typeof el.className === "string" && el.className ? "." + el.className.split(" ").join(".") : "");
          out.push({ t, right: Math.round(b.right), w: Math.round(b.width) });
        }
      }
      return { sw: document.documentElement.scrollWidth, iw, top: out.sort((a, b) => b.right - a.right).slice(0, 6) };
    });
    console.log(`${w}px`, r.sw > r.iw ? JSON.stringify(r) : "ok");
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
