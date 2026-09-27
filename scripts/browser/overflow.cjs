// scripts/browser/overflow.cjs — 화면 열 개를 여러 폭에서 열어 화면 밖으로 나가는 요소를 이름으로 찍는다(읽기 전용).
// 쓰는 법  WIDTHS=390,768,1024,1400 bash scripts/browser/walk.sh overflow.cjs
const { chromium } = require("playwright");
const base = process.argv[2], sid = process.argv[3];
const EXE = process.env.PLAYWRIGHT_CHROMIUM || "/opt/pw-browsers/chromium";
const say = (k, v) => console.log(`${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 390, height: 780 } });
  const bad = [];
  page.on("response", (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`); });
  const enc = encodeURIComponent(sid);
  const widths = (process.env.WIDTHS || "390").split(",").map(Number);
  let over = 0, total = 0;
  for (const w of widths) {
    await page.setViewportSize({ width: w, height: 780 });
    for (const p of ["/me", "/improve", "/media", "/events", `/c/${enc}`, "/judge", "/changes", "/", `/diary/${enc}`, `/mall/${enc}`]) {
      await page.goto(base + p);
      total++;
      const wide = await page.evaluate(() => {
        const iw = window.innerWidth, out = [];
        for (const el of document.querySelectorAll("body *")) {
          const r = el.getBoundingClientRect();
          if (r.right > iw + 1 && r.width > 0 && el.children.length < 40) {
            const t = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.split(" ").join(".") : "");
            out.push({ t, right: Math.round(r.right), w: Math.round(r.width) });
          }
        }
        return out.sort((a, b) => b.right - a.right).slice(0, 8);
      });
      if (wide.length) { over++; say(`${w}px ${p}`, wide); } else say(`${w}px ${p}`, "ok");
    }
  }
  say("http_4xx_5xx", bad);
  say("result", `${total - over}/${total} ok` + (bad.length ? ` · 4xx/5xx ${bad.length}` : ""));
  await browser.close();
  process.exit(over || bad.length ? 2 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
