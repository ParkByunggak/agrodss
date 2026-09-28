# -*- coding: utf-8 -*-
# FILE: scripts/build_ledger_page.py
# ROLE: [U-19 · D-13] docs/agrodss_backlog.md → 발행용 작업대장 페이지(HTML 조각 — 발행 도구가 doctype/head/body 를 씌운다).
#   읽기 전용 — 저장소에는 아무것도 쓰지 않는다. 출력은 인자로 준 파일 하나뿐.
#   [2026-09-27] 이 생성기가 세션 스크래치패드에만 있었다(U-35 · prewalk_grid 와 같은 형태 — 세션이 끝나면 사라진다). 저장소로 옮기며 옛 회차의
#   BEST 스물여덟 개를 잘라냈다(그 서술은 핸드오버 표와 대장 로그가 대신한다). 회차마다 다시 쓰는 것 셋: BEST(머리·이유) · NEXT_PUBLISHER · NEXT_SESSION.
#   쓰는 법   python scripts/build_ledger_page.py <출력.html>   → 폭 넷 넘침은 node scripts/browser/static_overflow.cjs <출력.html>
#   래칫     머리에 커밋 해시는 하나까지(U-19) · 페이지에 모델 식별자 0 · 지번 주소 패턴 0(PII) — 쓰기 전에 단언한다
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from frontend import render  # noqa: E402

text = (ROOT / "docs" / "agrodss_backlog.md").read_text(encoding="utf-8")
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                      encoding="utf-8", errors="replace").stdout.strip()
counts = render.ledger_counts(text)
ids = re.findall(r"^\| ([DIMUR]-\d+) \|", text, re.M)
body = render.md_to_html(text)
# 첫 h1 은 페이지 헤더가 대신한다
body = re.sub(r"^<h1>.*?</h1>\s*", "", body, count=1, flags=re.S)

NEXT_PUBLISHER = [
    # [시점 축 2026-09-27] 이 목록은 회차마다 **다시 쓴다** — 스크래치패드 판은 9/20~21 항목(9/8 예찰 · D-12 촬영 · 검토지)을 일주일 넘게 싣고 있었다.
    # 낡은 지시는 없는 지시보다 나쁘다(발행자가 이미 한 일을 다시 하거나, 안 해도 되는 일을 한다).
    ("⓪ <span style=\"color:#8C2B2B\">화면이 아직 00f7987</span> — <code>scripts\\update.bat</code> 더블클릭 (2분)", "2026-09-27 저녁 묶음 일곱(D-18 자리·뒷문·앞문·미리 걷기·도구 둘·WO-LLM-01 측정기)이 발행자 PC 에 아직 안 섰다. 이번 실행은 <b>TEMP 사본</b>으로 도는 첫 번째라 <code>'/f'</code>·<code>'he'</code> 줄이 없어야 한다. 끝 두 줄(<code>measured: the screen is running …</code>)을 세션에 붙인다. 받은 뒤 watch 창을 닫고 <code>install_autostart.bat</code> 한 번 더"),
    ("① 확인 셋 (3분)", "㉠ 입력칸에 한 줄 적고 <b>엔터</b> → 보내진다 · 줄바꿈은 Shift+Enter ㉡ 증상 물음(다른 문장으로 두 번 더 — 3/3 독립 재현) → 「아직 모릅니다 — 기준이 없습니다 …」 + '본 것' 초안, 계획표 없음 ㉢ <code>/judge</code> 배지가 「이렇게 보입니다」 · 「증상 → 원인 좁히기」 카드에 격자 id · 키 · 고칠 파일"),
    ("② <b>D-18 반영됨</b>(2026-09-28) — 받으신 뒤 증상 물음 한 번", "쓰신 감별 넷이 격자 칸 3 에 그대로 들어갔다. 증상 물음(예: 잎 끝이 노랗다) → 「이렇게 보입니다 · 원인 후보: 과습 · 뿌리 상함 · 고자리파리 유충 · 양분 부족 · 노균병 · 잎마름 — 먼저 증상 있는 포기를 몇 개 뽑아 인경 밑을 본다」 · <code>/judge</code> 「증상 → 원인 좁히기」 카드에 후보마다 가르는 확인. 규칙을 넓히실 때는 같은 파일(<code>data/grid/jjokpa_autumn.json</code> 칸 3 <code>symptom_rules</code>) → <code>python scripts/build_grid_doc.py</code> → 상태 검사 하나. 형식이 틀리면 검증기가 어느 규칙의 무엇이 틀렸는지 말한다"),
    ("②b <b>D-20 임계</b> — 무강수 며칠이면 관수를 검토할지(칸 3·4)", "<code>data/grid/jjokpa_autumn.json</code> 칸 3·4 에 <code>\"drought_rules\": {\"dry_days\": N, \"source\": \"…\"}</code>. N 은 발행자·농진청 정본(세션이 정하지 않는다). 순서는 D-18 과 같다: <code>python -m scripts.prewalk_grid jjokpa_autumn --stage 3 --key drought_rules --value-file rules.json</code> → 격자 → 문서 재생성 → 상태 검사 하나. 임계가 서도 마지막 비 온 날이 원장에 없으면 \"비 온 날을 알면 판단합니다\" 로 묻는다 — 채팅에 \"어제 비가 왔다\" 한 줄이면 된다"),
    ("③ WO-LLM-01 첫 숫자 — <code>python -m scripts.measure_misclassified</code> (1분)", "발행자 PC 의 채팅 원장에서 오분류 재료(종류 고침 + 편집 쌍)를 센다 — 마지막 두 줄을 붙인다. 30 미만이면 그 자체가 결과(§5-2). 30 이상이면 트리거('결과 없음' 은 빈 집합 → '기본값으로 떨어진 발화')를 D 항목으로 정한 뒤 하네스. <b>.env 는 건드리지 않는다</b>(발행자 2026-09-27 · LLM 키 제외는 D-9 결정)"),
    ("④ 결정 둘 — D-17 · D-19", "D-17 찍은 때 사다리의 '파일 이름' 칸을 둘 것인가(카카오톡 파일명은 받은 시각) · D-19 검색엔진 노출 — 어느 화면 · 언제 · 호스팅(지금 화면은 D-6 루프백 · 밭 자료라 노출 대상 아님)"),
]
NEXT_SESSION = [
    ("세션 시작 시 훅 활성 확인(가드 창)", "스크래치패드에 heredoc 파일 쓰기 1회 시도 — 차단되면 훅 활성, 통과하면 그 세션은 규율로만 지킨다(U-22: 세션 루트가 다른 저장소면 가드가 잠든다)"),
    ("D-18 이 오면 — 세 줄", "격자 칸 3 규칙 → 문서 재생성 → 상태 검사 하나. 먼저 <code>scripts/prewalk_grid.py</code> 로 잔여를 잰다(잔여가 상태 검사 하나뿐이어야 한다 · 아니면 처방이 먼저)"),
    ("WO-LLM-01 — 숫자가 오면", "30 미만: 표만 대장에 남기고 닫는다. 30 이상: 트리거 D 결정 뒤 하네스(플래그 · 호출부 · 검사 6 · 측정 스크립트 · 표) — 측정 실행은 발행자 PC(Ollama · GPU). 지시서의 전제 셋(트리거 빈 집합 · 말뭉치 104 · 오분류 이력은 원장 줄 순서) 정정본으로"),
    ("U-20 — NCPMS 임계 정본이 오면", "필지 축(배수 · 토성 · 미기상) 소비자 0 인 자리에 첫 소비자(과습 · 예찰 보정). 정본 없이는 대리값이 경보로 나가므로 지금은 안 한다"),
    ("낡음 대조", "대장 상태 열 · 이 페이지의 두 목록 · 핸드오버 §5 — 회차마다 다시 쓴다(시점 축). 실사용 관찰은 관찰 시점과 함께"),
]

def li(items):
    return "".join(f"<li><b>{html.escape(k)}</b><span>{v}</span></li>" for k, v in items)

pills = "".join(f'<span class="st st-{s}">{s} <strong>{n}</strong></span>' for s, n in counts.items() if n or s != "폐기")

# [U-19 · 발행자 2026-09-20] "최선의 다음 한 수"는 누적 보고가 아니라 **지금의 한 수 하나**다 — 회차마다 머리·이유를 다시 쓴다. 앞 회차 서술은
# 핸드오버 몫. 머리에 커밋 해시가 둘 이상이면 생성기가 거부한다(형식 래칫 — 낡은 주장 자체는 못 잡는다).
# [§0 보고 규칙 2026-09-21 — 발행자] 이번 회차에 **바뀐 것**부터. 앞 회차 서술은 아래 대장 표의 그 행이 대신한다.
BEST = ("<b>D-20 을 등재하셨고, D-18 과 같은 형태로 가뭄 · 관수 판단의 자리를 지식 없이 세웠습니다. 남은 것은 임계 하나 — 격자 칸에 「무강수 며칠」 을 적으시면 답이 열립니다.</b> "
        "<i>\"가을 가뭄이 심하다\"</i> 를 읽는 판단이 없던 자리에 <b>가뭄 · 관수 판단</b>이 섰습니다. 오늘 칸(심은 날 뒤 날수)의 수분 요구·결핍 민감도를 읽는 <b>첫 소비자</b>입니다. "
        "임계가 있으면 마지막으로 비 온 날(채팅 관찰의 비 어휘) 또는 관수한 날 뒤 지난 날수를 세어 임계 이상이면 「관수 검토」, 미만이면 「아직 아님」 을 내고, 비·관수 기록이 하나도 없으면 "
        "「마지막으로 비 온 날이나 관수한 날을 알면 판단합니다」 로 묻습니다. 임계가 없는 지금은 이렇게 답합니다: <b>「[아직 모릅니다 — 기준이 없습니다] 가뭄을 판단할 기준(무강수 며칠)이 "
        "아직 없습니다 — 지금 칸은 수분 요구 중간 · 결핍 민감 중간. 기준이 서면 관수 검토 여부를 냅니다」</b>. \"가뭄이 심한데 물 줘야 하나\" 같은 물음도 이 판단으로 갑니다. "
        "<b>넣으실 것은 하나</b>: <code>data/grid/jjokpa_autumn.json</code> 칸 3·4 에 <code>\"drought_rules\": {\"dry_days\": N, \"source\": \"…\"}</code>. N 은 발행자·농진청 정본입니다 — 제가 정하면 "
        "대리값이 경보로 나갑니다. 순서는 D-18 과 같습니다(미리 걷기 → 격자 → 문서 재생성 → 상태 검사 하나). 관수량·방법은 이 결정 밖(별도 지식)입니다.",
        "<b>왜 자리를 먼저 세우는가</b>: 임계가 오는 날 격자 한 줄로 끝나게 하려는 것이고(D-18 이 실제로 그렇게 끝났습니다), 그 전까지는 시스템이 가뭄 발화에 \"기준이 없다\" 고 정직하게 말합니다. "
        "봉투가 13 → 14 가 되면서 앞 회차가 정본 표현식 옆에 남겨 둔 리터럴 <code>== 13</code> 넷이 붉었습니다 — 안 재고 쓴 것의 마지막 흔적을 지웠습니다. 한 글자 탐침 검사의 \"얼마나 자주 물 줘야 하나\" 는 "
        "이제 이 판단으로 가는 것이 맞아 기대를 바꿨습니다(잡으려던 '얼' → 서리는 여전히 안 갑니다). 검사 12 · 주입 9/9 · 걷기 ok · 관문 <b>995 → 1007</b>(증분 +12 = 신규 12, 일치). "
        "발행자 PC 는 여전히 00f7987 — <code>update.bat</code> 이 첫 순서입니다.")
assert len(set(re.findall(r"\b[0-9a-f]{7}\b", BEST[0]))) <= 1, "U-19: 머리에 회차(커밋)가 둘 이상 — 지금의 한 수 하나만 적는다"

page = f"""<title>agrodss 작업대장</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --bg:#FAFAF7; --fg:#1F2A22; --muted:#6B7468; --line:#E1E4DE; --head:#F1F3EE; --panel:#FFFFFF;
  --accent:#2F6B3A; --accent-ink:#FFFFFF;
  --wait:#DCE6F5; --wait-fg:#2B4C8C; --run:#FBEFD0; --run-fg:#8A5A00; --done:#DDF0E2; --done-fg:#1F6B35;
  --hold:#ECECE9; --hold-fg:#5B5F5A; --drop:#F6DEDE; --drop-fg:#8C2B2B;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#151815; --fg:#E7EAE4; --muted:#9AA398; --line:#2C312C; --head:#1E231E; --panel:#1A1E1A;
  --accent:#7FC08E; --accent-ink:#0F1A12;
  --wait:#1F2A40; --wait-fg:#9DB7EA; --run:#3A2E12; --run-fg:#F0C060; --done:#16301C; --done-fg:#7FD095;
  --hold:#2A2C2A; --hold-fg:#B8BDB6; --drop:#3A1A1A; --drop-fg:#F09090; }} }}
:root[data-theme="dark"] {{
  --bg:#151815; --fg:#E7EAE4; --muted:#9AA398; --line:#2C312C; --head:#1E231E; --panel:#1A1E1A;
  --accent:#7FC08E; --accent-ink:#0F1A12;
  --wait:#1F2A40; --wait-fg:#9DB7EA; --run:#3A2E12; --run-fg:#F0C060; --done:#16301C; --done-fg:#7FD095;
  --hold:#2A2C2A; --hold-fg:#B8BDB6; --drop:#3A1A1A; --drop-fg:#F09090; }}
body {{ background:var(--bg); color:var(--fg); margin:0; padding-block:0 32px; padding-inline:16px;
  font-family:"IBM Plex Sans KR","Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif; font-size:14px; line-height:1.55; }}
.wrap {{ max-width:1180px; margin:0 auto; }}
header {{ position:sticky; top:env(safe-area-inset-top,0px); background:var(--bg); z-index:2; padding-block:14px 10px; border-bottom:1px solid var(--line); }}
header h1 {{ font-size:20px; margin:0; font-weight:600; letter-spacing:-.01em; }}
header .sub {{ color:var(--muted); font-size:12px; margin-top:2px; font-family:"IBM Plex Mono",ui-monospace,monospace; }}
.pills {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
.st {{ display:inline-block; padding:1px 9px; border-radius:10px; font-size:12px; white-space:nowrap; }}
.st strong {{ font-weight:600; }}
.st-대기 {{ background:var(--wait); color:var(--wait-fg); }} .st-진행 {{ background:var(--run); color:var(--run-fg); }}
.st-완료 {{ background:var(--done); color:var(--done-fg); }} .st-보류 {{ background:var(--hold); color:var(--hold-fg); }}
.st-폐기 {{ background:var(--drop); color:var(--drop-fg); }}
.best {{ margin:16px 0 0; padding:12px 14px; border-left:4px solid var(--accent); background:var(--panel); border-radius:0 8px 8px 0; }}
.best h2 {{ font-size:13px; margin:0 0 6px; text-transform:uppercase; letter-spacing:.06em; color:var(--accent); border:0; padding:0; }}
.best p {{ margin:4px 0; }}
.best .why {{ color:var(--muted); font-size:13px; }}
.next {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:18px 0 8px; }}
.next section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px 14px; }}
.next h2 {{ font-size:13px; margin:0 0 8px; text-transform:uppercase; letter-spacing:.06em; color:var(--accent); border:0; padding:0; }}
.next ol {{ margin:0; padding-left:20px; display:grid; gap:6px; }}
.next li b {{ display:block; font-weight:600; }}
.next li span {{ color:var(--fg); }}
h2 {{ font-size:16px; margin:28px 0 8px; padding-top:12px; border-top:1px solid var(--line); text-wrap:balance; }}
h3 {{ font-size:14px; margin:18px 0 6px; }}
code {{ font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:12.5px; background:var(--head); padding:1px 4px; border-radius:3px; }}
pre {{ background:var(--head); padding:10px; overflow-x:auto; border-radius:4px; }}
.tbl {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; margin:8px 0 12px; font-size:13px; }}
th,td {{ border:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }}
th {{ background:var(--head); }}
td:first-child {{ white-space:nowrap; font-family:"IBM Plex Mono",ui-monospace,monospace; font-weight:500; }}
.meta {{ color:var(--muted); font-size:12px; }}
@media (max-width:720px) {{ .next {{ grid-template-columns:1fr; }} }}
</style>
<div class="wrap">
<header>
  <h1>agrodss 작업대장</h1>
  <div class="sub">정본 docs/agrodss_backlog.md · main {html.escape(head)} · 항목 {len(ids)}</div>
  <div class="pills">{pills}</div>
</header>
<div class="best">
  <h2>최선의 다음 한 수 (D-13)</h2>
  <p>{BEST[0]}</p>
  <p class="why">이유: {BEST[1]}</p>
</div>
<div class="next">
  <section><h2>발행자 몫 — 지금</h2><ol>{li(NEXT_PUBLISHER)}</ol></section>
  <section><h2>세션 몫 — 지시하면 이 순서로</h2><ol>{li(NEXT_SESSION)}</ol></section>
</div>
<div class="tbl">
{body}
</div>
</div>
"""
# 저장소 산출물에 **모델 식별자**를 남기지 않는다. 도구·파일 이름(Claude Code · CLAUDE.md · .claude/settings.json · "Claude 형식")은 모델이 아니라 통과 —
# 대장에 열넷 있다(실측 2026-09-27). 모델 이름과 모델 id 접두만 본다
MODEL_WORDS = ("fable", "opus", "sonnet", "haiku", "claude-", "anthropic", "gpt-", "gemini")
# 지번(읍·면 + 리 + 번호) · '번지' · PNU 19자리 (I-5 §1-2 · U-18). 어미 '하면 3' · '자리 3곳' 같은 일반 문장에 걸리지 않게 두 토큰 형태만 본다
ADDRESS_RE = re.compile(r"[가-힣]{1,6}(?:읍|면)\s+[가-힣]{1,6}리\s+(?:산\s*)?\d+(?:-\d+)?|\d+번지|(?<!\d)\d{19}(?!\d)")


def check_page(text: str) -> list[str]:
    """쓰기 전 래칫 — 위반이면 사유 목록(비면 통과)."""
    low = text.lower()
    bad = [f"모델 식별자 {w!r}" for w in MODEL_WORDS if w in low]
    if ADDRESS_RE.search(text):
        bad.append("지번 주소 · PNU 패턴")
    return bad


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("쓰는 법: python scripts/build_ledger_page.py <출력.html>")
        sys.exit(2)
    problems = check_page(page)
    assert not problems, f"대장 페이지에 실으면 안 되는 것: {problems}"
    out = Path(sys.argv[1])
    out.write_text(page, encoding="utf-8")
    print("written", out, len(page))
