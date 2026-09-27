// scripts/browser/walk.cjs — 발행자 경로를 실제 브라우저로 걷는다(읽기 전용 · 격리 서버는 walk.sh 가 띄운다).
// 화면 열 개의 상태·콘솔 오류·가로 넘침(1100 · 390) → 채팅: 보내기 → 넣기 → 편집 → 고쳐 달라는 말 → 사진 올리기.
const { chromium } = require("playwright");
const path = require("path");

const base = process.argv[2], sid = process.argv[3], W = process.argv[4];
const EXE = process.env.PLAYWRIGHT_CHROMIUM || "/opt/pw-browsers/chromium";
const say = (k, v) => console.log(`${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror ${page.url()} ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console ${page.url()} ${m.text()}`); });
  page.on("response", (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });

  const enc = encodeURIComponent(sid);
  const PAGES = ["/", `/c/${enc}`, `/diary/${enc}`, "/judge", "/me", "/improve", "/changes", "/media", "/events", `/mall/${enc}`];
  const overflow = async () => await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  let bad = 0;

  for (const w of [1100, 390]) {
    await page.setViewportSize({ width: w, height: 700 });
    for (const p of PAGES) {
      const r = await page.goto(base + p);
      const o = await overflow();
      const over = o.sw > o.iw ? o : null;
      if (r.status() !== 200 || over) bad++;
      say(`${w}px ${p}`, { status: r.status(), overflow: over });
    }
  }
  await page.setViewportSize({ width: 1100, height: 700 });

  await page.goto(`${base}/c/${enc}`);
  await page.fill("#text", "오늘 물 줬다");
  await Promise.all([page.waitForNavigation(), page.keyboard.press("Enter")]);       // 엔터 = 보내기
  const confirmBtn = page.locator('.draft button[type="submit"]').last();
  say("draft_confirm_button", await confirmBtn.textContent());
  await Promise.all([page.waitForNavigation(), confirmBtn.click()]);
  say("after_confirm", (await page.locator("p.ok").allTextContents()).join(" | "));
  const s = await page.evaluate(() => ({ gap: document.documentElement.scrollHeight - (window.scrollY + window.innerHeight), active: document.activeElement && document.activeElement.id }));
  say("after_confirm_position", s);                                                  // gap 0 · active text 여야 한다
  if (s.gap !== 0 || s.active !== "text") bad++;

  await page.locator('button[data-act="edit"]').last().click();
  say("edit", { value: await page.inputValue("#text"), active: await page.evaluate(() => document.activeElement.id) });
  await page.fill("#text", "");

  const ask = page.locator("details.ask").last();
  await ask.locator("summary").click();
  await ask.locator("textarea").fill("이 답이 이해가 안 됩니다");
  await Promise.all([page.waitForNavigation(), ask.locator('button[type="submit"]').click()]);
  say("ask_ack", (await page.locator("p.ok").allTextContents()).join(" | "));

  await page.setInputFiles("#file", path.join(W, "KakaoTalk_20260923_074025068_04.jpg"));
  say("files_shown", { hidden: await page.evaluate(() => document.getElementById("files").hidden), names: await page.textContent("#filenames") });
  await page.fill("#text", "");
  await Promise.all([page.waitForNavigation(), page.keyboard.press("Enter")]);
  say("photo_reply", (await page.locator(".msg.sys .bub").allTextContents()).pop());

  say("errors", errors);
  if (errors.length) bad++;
  say("result", bad ? `문제 ${bad}` : "ok");
  await browser.close();
  process.exit(bad ? 2 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
