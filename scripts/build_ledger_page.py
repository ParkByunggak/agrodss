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
    # [발행자 2026-09-28 "각 단계별로 발행자가 할 일을 구체적으로 사례를 들어"] 항목마다 **손으로 할 것 → 화면에 보일 것(예) → 세션에 보낼 것** 순으로.
    ("⓪ <b>받으셨다</b> — 2026-09-28 13:46 스크린샷 꼬리 「실행 중 08224cc」. 다음 묶음(D-21 단기 · 중기 · 폼 공백 — 전부 커밋됨)을 받으실 때 같은 순서로 한 번 더 (2분)",
     "<b>할 것</b>: 탐색기에서 <code>D:\\agrodss\\scripts\\update.bat</code> 더블클릭 → 검은 창이 <i>pulling</i> → <i>waiting for the old screen to stop</i> → "
     "<b><code>measured: the screen is running 55c36ed</code></b>(또는 그 뒤 해시)로 끝난다. 이번은 TEMP 사본으로 도는 첫 실행이라 지난번의 <code>'/f'은(는) …</code> · <code>'he' …</code> 줄이 "
     "<b>없어야</b> 한다. 그 다음 열려 있던 <i>watch</i> 검은 창을 닫고 <code>scripts\\install_autostart.bat</code> 한 번 더 더블클릭. "
     "<b>확인</b>: 브라우저 <code>http://127.0.0.1:8765</code> 맨 아래 꼬리가 「실행 중 55c36ed」(00f7987 이 아니면 됐다). "
     "<b>보낼 것</b>: 창의 마지막 두 줄. 오류 줄이 보이면 그 줄 그대로"),
    ("① 확인 셋 (3분)",
     "㉠ <b>엔터</b>: 채팅 입력칸에 <i>오늘 물 줬다</i> 치고 Enter → 보내지고 답이 온다(예: 「한 일로 적었습니다 … '일지에 넣기'」). Shift+Enter 는 줄만 바뀐다. "
     "㉡ <b>증상 물음</b> 두 문장(다른 말로): <i>잎 끝이 누렇게 되는데 왜 그런가요</i> · <i>잎이 노래지는데 어떻게 해야 하나</i> → 둘 다 "
     "「이렇게 보입니다 · 원인 후보: 과습 · 뿌리 상함 · 고자리파리 유충 · 양분 부족 · 노균병 · 잎마름 — 먼저 … 인경 밑을 본다」 + 아래에 '본 것' 초안 카드(계획표는 안 나온다). "
     "㉢ <b>/judge</b>: 배지가 「이렇게 보입니다」 · 「증상 → 원인 좁히기」 카드가 있다 — ㉡의 초안을 '일지에 넣기' 하면 그 카드에 후보 표(가르는 확인 · 회복)가 선다. "
     "<b>보낼 것</b>: 셋 중 다르게 나온 것만(같으면 「셋 다 맞다」 한 줄)"),
    ("② <b>D-18 반영됨</b> — ㉡이 그 확인이다",
     "쓰신 감별 넷이 격자 칸 3 에 그대로 들어갔다. <b>규칙을 넓히실 때(예: '잎이 비틀린다' 를 더하고 싶다)</b>: 값과 출처를 세션에 한 줄로 주시면 세션이 세 줄"
     "(미리 걷기 → 격자 → 문서 재생성 → 상태 검사)을 한다. 직접 하시면: <code>data/grid/jjokpa_autumn.json</code> 칸 3 의 <code>symptom_rules</code> 목록에 "
     "<code>{\"symptoms\": [\"비틀\"], \"causes\": [{\"name\": \"…\", \"check\": \"…\", \"recoverable\": false}], \"first_check\": \"…\"}</code> 를 더하고 → "
     "<code>python scripts\\build_grid_doc.py</code> → 형식이 틀리면 <code>python -m pytest tests\\test_grid.py -q</code> 가 어느 규칙의 무엇이 틀렸는지 말한다"),
    ("②b <b>D-20 임계</b> — 무강수 며칠이면 관수를 검토할지 (값 하나)",
     "<b>정할 것</b>: 예를 들어 <i>\"가을 쪽파는 비 안 온 지 7일이면 관수를 검토한다 — 출처: 농진청 쪽파 재배 지침(또는 내 경험 2026)\"</i>. "
     "<b>보낼 것</b>: 그 문장 한 줄(N 과 출처) — 세션이 <code>prewalk_grid --stage 3 4</code> → 격자 칸 3·4 <code>\"drought_rules\": {\"dry_days\": 7, \"source\": \"…\"}</code> → 문서 재생성 → "
     "상태 검사 하나를 한다. <b>직접 하시면</b> 같은 파일 칸 3 과 칸 4 의 <code>\"decisions\": […]</code> 줄 아래에 그 한 줄을 넣는다(앞 줄 끝 쉼표 주의). "
     "<b>그 뒤 화면</b>: 채팅에 <i>어제 비가 왔다</i> 한 줄(비 온 날 기록) → <i>가뭄이 심한데 물 줘야 하나</i> → 「마지막 비·관수 2026-09-27 뒤 무강수 1일 — 임계 7일 미만: 아직 관수 판단 아님 · "
     "수분 요구 중간 · 결핍 민감 중간」. 비 기록이 없으면 「마지막으로 비 온 날이나 관수한 날을 알면 판단합니다」 로 묻는다"),
    ("③ WO-LLM-01 첫 숫자 (1분)",
     "<b>할 것</b>: 시작 → <i>cmd</i> → <code>cd /d D:\\agrodss</code> → <code>python -m scripts.measure_misclassified</code>. 표가 나오고 마지막 두 줄이 "
     "<i>재료 N건 (고침 a · 편집 b) — 문턱 30: 충족/미달</i> · <i>기대 종류는 발행자가 붙인다 …</i> 다. <b>보낼 것</b>: 그 두 줄만(위의 발화 원문 줄들은 붙이지 않아도 된다 — PII). "
     "30 미만 = 그 자체가 결과(지시서 §5-2). 30 이상 = 트리거를 정한 뒤 하네스. <b>.env 는 건드리지 않는다</b>"),
    ("④ 결정 둘 — 한 줄씩",
     "<b>D-17</b> 예: <i>\"파일명 시각은 쓴다 — 단 라벨에 '저장·전송 시각일 수 있음' 을 유지\"</i> 또는 <i>\"안 쓴다 — 찍은 때가 없으면 날짜를 묻는다\"</i>. "
     "<b>D-19</b> 예: <i>\"공개는 몰 상세페이지만 · 첫 수확 뒤 · 호스팅은 그때 정한다\"</i> — 셋(어느 화면 · 언제 · 호스팅)이 한 줄에 있으면 된다. 지금 화면(밭 자료)은 계속 루프백"),
    ("⑤ <b>D-21 — 단기·중기 반영됨 · 장기는 결정 하나</b> — 받으신 뒤 \"내일 날씨 어때\" 한 번 · 장기 ⓐ/ⓑ 한 줄",
     "<b>지금 커밋</b>: 단기(오늘부터 3일 — 최저·최고 · 비 올 확률 · 강수량) 뒤에 중기(D+3~D+10 · 권역 — 최저·최고 · 비 올 확률(오전·오후 최대) · 날씨)를 이어 붙여 원천·발표 시각과 함께 그대로 낸다 → "
     "「찾아본 것입니다 · 09-29 11~22℃ 비 60% 5.0mm · …(기상청 단기예보 · 발표 …) · 중기(괴산) 10-01 7~17℃ 비 70% · …(기상청 중기예보 · 발표 …)」. 못 받은 쪽은 그 이유를 그대로. "
     "<b>확인</b>: <code>/judge</code> 꼬리 \"예보 사용 · 중기: 중기예보 사용\" · 「날씨 인용(단기·중기 예보)」 카드에 표 둘. <b>보낼 것</b>: 그 카드 한 줄(또는 못 받은 이유). "
     "<b>장기(1개월 전망)</b>: VELA 가 2026-08-05 에 apihub · data.go.kr · 기상자료개방포털 셋을 재서 <b>오픈 API 가 없다</b>고 적어 두었고(관리자 수동 등재 정본으로 둠), 이 세션은 그 셋이 차단이라 다시 못 쟀습니다. "
     "<b>정하실 것 한 줄</b>: ⓐ <i>\"장기는 VELA 처럼 수동 정본 — 내가 날씨누리 1개월 전망 수치를 출처와 함께 넣는다\"</i>(세션이 자리를 세운다 · 값은 발행자 몫) 또는 ⓑ <i>\"장기는 안 낸다\"</i>. "
     "apihub 「장기예보」 항목을 PC 에서 한 번 보시면 VELA 의 그 실측이 지금도 맞는지 확정됩니다"),
]
NEXT_SESSION = [
    ("세션 시작 시 훅 활성 확인(가드 창)", "스크래치패드에 heredoc 파일 쓰기 1회 시도 — 차단되면 훅 활성, 통과하면 그 세션은 규율로만 지킨다(U-22: 세션 루트가 다른 저장소면 가드가 잠든다)"),
    ("D-20 임계가 오면 — 세 줄", "<code>prewalk_grid --stage 3 4 --key drought_rules</code> 로 잔여를 잰다(상태 검사 하나뿐이어야 한다) → 격자 칸 3·4 → 문서 재생성 → 상태 검사 하나. D-18 규칙을 넓히실 때도 같은 세 줄"),
    ("WO-LLM-01 — 숫자가 오면", "30 미만: 표만 대장에 남기고 닫는다. 30 이상: 트리거 D 결정 뒤 하네스(플래그 · 호출부 · 검사 6 · 측정 스크립트 · 표) — 측정 실행은 발행자 PC(Ollama · GPU). 지시서의 전제 셋(트리거 빈 집합 · 말뭉치 104 · 오분류 이력은 원장 줄 순서) 정정본으로"),
    ("D-21 장기 — ⓐ 면 자리 넷", "<code>data/kma/climate_outlook.json</code>(VELA 형태 · 출처 URL 필수 · 확률 합≈100) · 스키마 kind · 인용 result <code>long</code>(비면 \"등재된 장기 전망 없음\") · 검사. 값은 넣지 않는다"),
    ("U-20 — NCPMS 임계 정본이 오면","필지 축(배수 · 토성 · 미기상) 소비자 0 인 자리에 첫 소비자(과습 · 예찰 보정). 정본 없이는 대리값이 경보로 나가므로 지금은 안 한다"),
    ("낡음 대조", "대장 상태 열 · 이 페이지의 두 목록 · 핸드오버 §5 — 회차마다 다시 쓴다(시점 축). 실사용 관찰은 관찰 시점과 함께"),
]

def li(items):
    # [발행자 붙임 2026-09-28] 머리(k)를 escape 해서 <span style=…>·<code> 가 글자 그대로 화면에 나갔다 — 머리도 본문도 여기서 쓴 HTML 이지 사용자 글이 아니다.
    # 그리고 <ol> 번호 위에 ⓪①② 표지를 또 달아 "1. ⓪" 로 두 번 셌다 → 표지만 남기고 목록 번호는 뗀다(<ul>)
    return "".join(f"<li><b>{k}</b><span>{v}</span></li>" for k, v in items)

pills = "".join(f'<span class="st st-{s}">{s} <strong>{n}</strong></span>' for s, n in counts.items() if n or s != "폐기")

# [U-19 · 발행자 2026-09-20] "최선의 다음 한 수"는 누적 보고가 아니라 **지금의 한 수 하나**다 — 회차마다 머리·이유를 다시 쓴다. 앞 회차 서술은
# 핸드오버 몫. 머리에 커밋 해시가 둘 이상이면 생성기가 거부한다(형식 래칫 — 낡은 주장 자체는 못 잡는다).
# [§0 보고 규칙 2026-09-21 — 발행자] 이번 회차에 **바뀐 것**부터. 앞 회차 서술은 아래 대장 표의 그 행이 대신한다.
BEST = ("<b>지시하신 순서의 둘째까지 섰습니다 — 날씨 물음이 단기 3일에 이어 권역 중기(D+3~D+10)까지 그대로 냅니다. 셋째(장기 1개월 전망)는 원천을 확인했고, 오픈 API 가 없어 발행자 결정 한 줄(ⓐ 수동 정본 자리 / ⓑ 안 낸다)이 남았습니다.</b> "
        "<b>중기</b>는 VELA 의 중기예보 클라이언트(발표 06·18시 −30분 · 육상 <code>getMidLandFcst</code> + 기온 <code>getMidTa</code> · 권역표 14)를 D-9 로 인용해 표준 라이브러리로 다시 썼습니다. 중기는 격자가 아니라 <b>권역</b> 단위라 "
        "좌표에서 최근접 관측 지점 이름으로 권역을 찾습니다(괴산 → 육상 11C10000 · 기온은 충주 코드 11C10401 을 빌린다는 VELA 검증 기록 그대로) — 표에 없으면 <b>\"권역 미해소\"</b> 를 이유로 내고 수도권 등으로 대체하지 않습니다. "
        "값은 오전·오후 원문 그대로 싣고 비 올 확률은 둘 중 큰 값 · 강수량 열은 없습니다(중기에 없는 값을 지어내지 않습니다). 단기 창(오늘부터 3일)과 겹치는 중기 날은 5km 격자 단기가 이깁니다. "
        "레코드 종류를 단기와 <b>따로</b> 둔 이유: 판단 넷이 단기 줄을 날짜별로 읽고 있어, 같은 종류에 섞으면 해상도가 다른 권역 값이 그 판단에 들어갑니다. 새 종류는 스키마 정본을 지나 경계 관문을 통과합니다. "
        "<b>관문의 입력을 둘 다</b> 배선했습니다 — 중기 줄(게이트 뒤)과 못 받은 이유. 한쪽만 없으면 사실 인용에 그쪽 이유가 남고, 둘 다 없으면 판단 불가에 이유가 둘 다 실립니다. /judge 에는 표 둘(열이 다릅니다), 꼬리에 \"중기: …\".",
        "<b>장기 — 확인 결과</b>: VELA 정본(<code>held_inventory.json</code> · <code>climate_outlook.json</code>)이 <i>\"1·3개월 전망은 오픈 API 부재 — 2026-08-05 apihub · data.go.kr · 기상자료개방포털 3곳 실측\"</i> 이라 적고, "
        "관리자가 날씨누리 발표문 수치를 출처 URL 과 함께 <b>수동 등재</b>하는 정본(확률 3분위 합≈100 검증)으로 둡니다. 이 컨테이너는 그 세 곳이 차단이라 <b>오늘 다시 재지 못했습니다</b> — 인용이지 측정이 아니고, 그래서 시점(2026-08-05)을 함께 적습니다. "
        "지식을 지어내지 않는 규칙상 장기를 낼 길은 ⓐ 뿐이고, 그것도 값은 발행자 몫입니다. <b>왜 자리를 먼저 묻는가</b>: ⓐ 는 파일 · 종류 · 인용 갈래 · 검사 넷을 세우는 일이라 결정 뒤 한 회차면 되고, 비어 있으면 \"등재된 장기 전망 없음\" 이 정직한 답입니다. "
        "검사 9(중기 원천 7 · 인용 +2) · 주입 11/11(게이트 미배선 · 이유 미배선 · 창 겹침 · 확률 최소값 · 서울 대체 · −30분 · 표 제거 · 3층 입력 아님 · 권역 없이 호출 · 단기 없으면 불가 · partial 누락 — 전부 적발) · 걷기 ok · "
        "관문 <b>1019 → 1028</b>(증분 +9 = 신규 9, 일치 · TZ=Asia/Seoul). 발행자 PC 는 08224cc — 이번 세 커밋 뒤 <code>update.bat</code> 을 한 번 돌리시면 날씨 물음이 표 둘로 나옵니다. D-20 임계(칸 3·4)는 그대로 발행자 몫입니다.")
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
.next ul {{ margin:0; padding-left:0; list-style:none; display:grid; gap:8px; }}
.next li {{ padding:6px 8px; border-left:3px solid var(--line, #ddd); }}
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
  <section><h2>발행자 몫 — 지금</h2><ul>{li(NEXT_PUBLISHER)}</ul></section>
  <section><h2>세션 몫 — 지시하면 이 순서로</h2><ul>{li(NEXT_SESSION)}</ul></section>
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
