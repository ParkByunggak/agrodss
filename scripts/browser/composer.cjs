// scripts/browser/composer.cjs — 채팅 입력칸 계약을 실제로 누른다(U-33): 엔터 = 보내기 · Shift+Enter = 줄바꿈 ·
// 보낸 뒤/다시 시도 뒤 맨 아래 + 커서 입력칸. 쓰는 법  bash scripts/browser/walk.sh composer.cjs
const { chromium } = require("playwright");
const base = process.argv[2], sid = process.argv[3];
const EXE = process.env.PLAYWRIGHT_CHROMIUM || "/opt/pw-browsers/chromium";
const say = (k, v) => console.log(`${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 1100, height: 600 } });
  await page.goto(`${base}/c/${encodeURIComponent(sid)}`);
  const count = async () => await page.locator(".msg.me").count();
  const where = async () => await page.evaluate(() => ({
    gap: document.documentElement.scrollHeight - (window.scrollY + window.innerHeight), active: document.activeElement && document.activeElement.id }));
  let bad = 0;

  const n0 = await count();
  for (let i = 0; i < 12; i++) { await page.fill("#text", `오늘 물 줬다 ${i}`); await Promise.all([page.waitForNavigation(), page.keyboard.press("Enter")]); }
  const n1 = await count();
  say("enter_sent", `${n0} -> ${n1}`); if (n1 !== n0 + 12) bad++;
  let s = await where(); say("after_send", s); if (s.gap !== 0 || s.active !== "text") bad++;

  await page.fill("#text", "첫 줄"); await page.keyboard.press("Shift+Enter"); await page.keyboard.type("둘째 줄");
  const v = await page.inputValue("#text");
  say("shift_enter", { newline: v.includes("\n"), sent: (await count()) !== n1 }); if (!v.includes("\n") || (await count()) !== n1) bad++;
  await page.fill("#text", "");

  await page.evaluate(() => window.scrollTo(0, 0));
  await Promise.all([page.waitForNavigation(), page.locator('button[data-act="retry"]').first().click()]);
  s = await where(); say("after_retry", s); if (s.gap !== 0 || s.active !== "text" || (await count()) !== n1 + 1) bad++;

  say("result", bad ? `문제 ${bad}` : "ok");
  await browser.close();
  process.exit(bad ? 2 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
