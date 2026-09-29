// scripts/browser/widths.cjs — 휴대폰 폭(기본 390px)에서 화면마다 **사이드바 · 본문 폭과 문서 넘침**을 잰다. 읽기 전용 측정 도구(격리 서버는 walk.sh 가 띄운다).
//
// [U-35 형태 2026-09-29] walk.cjs 의 넘침 검사는 문서 폭(scrollWidth)만 본다 — 글이 접히면 본문이 130px 뿐이어도 "넘침 없음" 이다. 그날 /selfcheck 를
// 걷다 441px 가 나와 요소별로 재니 패널 없는 셸 다섯 화면이 휴대폰에서 사이드바 260 + 본문 130 이었다(5ae81e2). 그 측정 스크립트가 스크래치패드에만
// 있어 여기 둔다. 판정: 문서가 뷰포트를 넘거나(sw > W) 본문이 뷰포트의 절반보다 좁으면(main < W/2) 문제.
//
// 쓰는 법   PAGES="/me,/selfcheck" WIDTH=390 bash scripts/browser/walk.sh widths.cjs      (PAGES 의 SID 는 첫 목록 id 로 바뀐다)
const { chromium } = require("playwright");
const base = process.argv[2], sid = process.argv[3];
const EXE = process.env.PLAYWRIGHT_CHROMIUM || "/opt/pw-browsers/chromium";
const W = parseInt(process.env.WIDTH || "390", 10);
const PAGES = (process.env.PAGES || "/,/c/SID,/diary/SID,/judge,/me,/me/outlook,/c/new,/improve,/changes,/media,/events,/selfcheck")
  .split(",").map((p) => p.replace("SID", encodeURIComponent(sid)));
const say = (k, v) => console.log(`${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: W, height: 700 } });
  let bad = 0;
  for (const p of PAGES) {
    const r = await page.goto(base + p);
    const m = await page.evaluate(() => {
      const w = (sel) => { const el = document.querySelector(sel); return el ? Math.round(el.getBoundingClientRect().width) : null; };
      return { sw: document.documentElement.scrollWidth, side: w("aside.side, nav, .side, .wrap > aside"), main: w("main.thread, main, .wrap > .main, .content") };
    });
    const over = m.sw > W;
    const narrow = m.main !== null && m.main < W / 2;
    if (r.status() !== 200 || over || narrow) bad++;
    say(`${W}px ${p}`, { status: r.status(), ...m, problem: over ? "문서가 넘친다" : narrow ? "본문이 절반보다 좁다" : null });
  }
  say("result", bad ? `문제 ${bad}` : "ok");
  await browser.close();
  process.exit(bad ? 2 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
