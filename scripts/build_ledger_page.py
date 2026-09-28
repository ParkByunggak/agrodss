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
    ("⓪ <b>update.bat 마지막 한 번</b> — 화면은 아직 08224cc(13:46 스크린샷). 이번을 누르시면 그 뒤로는 화면이 <b>스스로</b> 따라갑니다(U-39 자동 갱신 · 600초마다) (2분)",
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
     "(미리 걷기 → 격자 → 문서 재생성 → 상태 검사)을 한다. <b>격자 파일을 PC 에서 손으로 고치지는 마십시오</b> — <code>data/grid/jjokpa_autumn.json</code> 은 추적 파일이라 "
     "다음 <code>update.bat</code> 이 그 수정을 <code>data\\_local_backup\\</code> 으로 치우고 되돌립니다(값은 남지만 화면에는 없습니다). 격자는 세션 커밋으로만 바뀝니다. "
     "모양만 참고: <code>{\"symptoms\": [\"비틀\"], \"causes\": [{\"name\": \"…\", \"check\": \"…\", \"recoverable\": false}], \"first_check\": \"…\"}</code>"),
    ("②b <b>D-20 임계</b> — 무강수 며칠이면 관수를 검토할지 (값 하나)",
     "<b>정할 것</b>: 예를 들어 <i>\"가을 쪽파는 비 안 온 지 7일이면 관수를 검토한다 — 출처: 농진청 쪽파 재배 지침(또는 내 경험 2026)\"</i>. "
     "<b>보낼 것</b>: 그 문장 한 줄(N 과 출처) — 세션이 <code>prewalk_grid --stage 3 4</code> → 격자 칸 3·4 <code>\"drought_rules\": {\"dry_days\": 7, \"source\": \"…\"}</code> → 문서 재생성 → "
     "상태 검사 하나를 한다. 격자 파일을 PC 에서 손으로 고치면 ② 와 같은 이유로 다음 <code>update.bat</code> 이 되돌립니다 — 값 한 줄을 주시는 것이 길입니다. "
     "<b>그 뒤 화면</b>: 채팅에 <i>어제 비가 왔다</i> 한 줄(비 온 날 기록) → <i>가뭄이 심한데 물 줘야 하나</i> → 「마지막 비·관수 2026-09-27 뒤 무강수 1일 — 임계 7일 미만: 아직 관수 판단 아님 · "
     "수분 요구 중간 · 결핍 민감 중간」. 비 기록이 없으면 「마지막으로 비 온 날이나 관수한 날을 알면 판단합니다」 로 묻는다"),
    ("③ WO-LLM-01 첫 숫자 (1분)",
     "<b>할 것</b>: 시작 → <i>cmd</i> → <code>cd /d D:\\agrodss</code> → <code>python -m scripts.measure_misclassified</code>. 표가 나오고 마지막 두 줄이 "
     "<i>재료 N건 (고침 a · 편집 b) — 문턱 30: 충족/미달</i> · <i>기대 종류는 발행자가 붙인다 …</i> 다. <b>보낼 것</b>: 그 두 줄만(위의 발화 원문 줄들은 붙이지 않아도 된다 — PII). "
     "30 미만 = 그 자체가 결과(지시서 §5-2). 30 이상 = 트리거를 정한 뒤 하네스. <b>.env 는 건드리지 않는다</b>"),
    ("④ 결정 둘 — 한 줄씩",
     "<b>D-17</b> 예: <i>\"파일명 시각은 쓴다 — 단 라벨에 '저장·전송 시각일 수 있음' 을 유지\"</i> 또는 <i>\"안 쓴다 — 찍은 때가 없으면 날짜를 묻는다\"</i>. "
     "<b>D-19</b> 예: <i>\"공개는 몰 상세페이지만 · 첫 수확 뒤 · 호스팅은 그때 정한다\"</i> — 셋(어느 화면 · 언제 · 호스팅)이 한 줄에 있으면 된다. 지금 화면(밭 자료)은 계속 루프백"),
    ("⑤ <b>D-21 — 단기·중기·장기 자리 반영됨 · 장기 값은 발행자가 넣는다</b> — 받으신 뒤 \"내일 날씨 어때\" 한 번 · 1개월 전망 한 주 등재 (10분)",
     "<b>지금 커밋</b>: 단기(오늘부터 3일) → 중기(D+3~D+10 · 권역) → 장기(등재분)를 한 인용에 이어 낸다. 못 받은 쪽은 그 이유를 그대로 — 지금 장기는 「장기: 없음 — 등재된 장기 전망 없음」. "
     "<b>장기 넣는 법</b>(파일 안 <code>_how_to</code> 와 같다): 날씨누리 → 기후예측 → 1개월 전망(목요일 발표). <code>D:\\agrodss\\data\\kma\\climate_outlook.json</code> 을 <b>복사해 이름을 <code>climate_outlook_local.json</code> 으로</b>(같은 폴더 · git 밖) 두고, "
     "그 파일의 <code>_example</code> 을 복사해 <code>entries: [ … ]</code> 안에 넣고 바꾼다 — 기간(<code>target_from</code>~<code>target_to</code>) · 지역(발표문 표기 그대로, 예: 충북) · 기온 높음/비슷/낮음 % · 강수 많음/비슷/적음 % · "
     "<code>source_title</code> · <code>source_url</code>(발표문 주소 · 필수). 주마다 항목 하나(4주면 넷). <b>원본 <code>climate_outlook.json</code> 에는 넣지 않는다</b> — <code>update.bat</code> 이 그 수정을 치우고 되돌려 값이 사라진다. "
     "<b>지키는 것</b>: 확률 셋의 합 100(±5) · URL 있음 — 어긋난 항목은 <code>/changes</code> 에 「못 읽음 — climate_outlook_local.json entries[i]: 이유」 로 남고 값은 안 나간다(조용히 고치지 않는다). 저장 뒤 <code>python -m pytest tests\\test_climate_outlook.py -q</code>. "
     "<b>그 뒤 화면</b>: 「장기(1개월 전망 · 등재 기준 · 발표 09-25) 10-05~10-11 충북 기온 높음 50% · 비슷 30% · 낮음 20% / 강수 …」 · <code>/judge</code> 에 표(출처 링크). "
     "<b>보낼 것</b>: 날씨 카드 한 줄(단기·중기가 붙었는지 · 못 받은 이유). 시스템은 이 파일 밖에서 장기 값을 얻지 않는다 — VELA 가 2026-08-05 에 오픈 API 가 없다고 잰 것을 인용했고, 이 세션은 그 원천들이 차단이라 다시 못 쟀습니다(PC 에서 apihub 「장기예보」 를 한 번 보시면 확정)"),
]
NEXT_SESSION = [
    ("세션 시작 시 훅 활성 확인(가드 창)", "스크래치패드에 heredoc 파일 쓰기 1회 시도 — 차단되면 훅 활성, 통과하면 그 세션은 규율로만 지킨다(U-22: 세션 루트가 다른 저장소면 가드가 잠든다)"),
    ("D-20 임계가 오면 — 세 줄", "<code>prewalk_grid --stage 3 4 --key drought_rules</code> 로 잔여를 잰다(상태 검사 하나뿐이어야 한다) → 격자 칸 3·4 → 문서 재생성 → 상태 검사 하나. D-18 규칙을 넓히실 때도 같은 세 줄"),
    ("WO-LLM-01 — 숫자가 오면", "30 미만: 표만 대장에 남기고 닫는다. 30 이상: 트리거 D 결정 뒤 하네스(플래그 · 호출부 · 검사 6 · 측정 스크립트 · 표) — 측정 실행은 발행자 PC(Ollama · GPU). 지시서의 전제 셋(트리거 빈 집합 · 말뭉치 104 · 오분류 이력은 원장 줄 순서) 정정본으로"),
    ("검토표 순서 — 다음은 ⑤b 장기 입력 폼", "발행자 승인(2026-09-28 \"제안 순서대로\") — ⓪ 자동 갱신은 U-39 로 섰다. 다음: ⑤b 장기 값 입력 폼(/me 형태 → 덮개에 저장 · 합≈100 · URL 필수를 저장 전에) → ①⑤a 자기 점검 화면 /selfcheck → ② 격자 값 한 명령 → ③ 오분류 상시 측정"),
    ("D-21 장기 값이 오면","발행자가 덮개 <code>climate_outlook_local.json</code> entries 에 넣은 뒤 상태 검사(<code>test_climate_outlook</code> 마지막 것)가 초록인지 · 채팅 카드에 「장기(…)」 가 붙는지 · /changes 에 못 읽음이 없는지 셋만 본다. 값은 세션이 넣지 않는다 · 씨앗은 발행자가 세션에 값을 주어 커밋할 때만"),
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
BEST = ("<b>⓪ 자동 갱신을 등재하셨고 U-39 로 섰습니다 — 화면 프로세스가 600초마다 저장소를 보고 뒤처졌으면 fast-forward 로만 따라가 기존 경로로 다시 뜹니다. 아무것도 버리지 않고(수정·갈라짐은 보류), 결과가 꼬리에 늘 보입니다. 이 코드를 받으시려면 update.bat 을 <u>마지막 한 번</u> 누르셔야 합니다 — 그 뒤로는 사람 손이 안 갑니다.</b> "
        "<b>어떻게 도는가</b>: 기동 30초 뒤 첫 시도, 그 뒤 600초마다 fetch. 원격과 같으면 「최신」. 뒤처졌는데 이 PC 에 원격에 없는 커밋이 있으면 「보류: 갈라짐」, 추적 파일에 손 수정이 있으면 「보류: 추적 파일 수정 N: 이름」 — "
        "update.bat 은 그 수정을 치우고 되돌리지만 자동은 <b>아무것도 버리지 않습니다</b>(사람이 누른 것과 기계가 하는 것의 차이). 덮개 <code>*_local</code> 은 추적이 아니라 걸리지 않습니다. 따라갈 수 있으면 <code>pull --ff-only</code> 로 「갱신 a → b」, HEAD 가 바뀐 것을 기존 감시가 보고 새 코드로 다시 뜹니다. fetch 가 안 되면 「실패: fetch …」(비공개로 바뀌면 자격 증명 프롬프트에 매달리지 않고 이렇게 보입니다). "
        "꼬리 · /changes · /running(배치용 ASCII) 세 곳에 마지막 시도가 남습니다 — 침묵이 가장 나쁜 실패라서. 검사·걷기는 <code>AGRODSS_AUTO_PULL_SEC=0</code> 으로 끕니다(env 와 setattr 둘 다 — 하나만 두면 검사 프로세스가 원격을 부릅니다). "
        "앞서 같은 오후: 날씨 인용 단기·중기·장기 자리, 덮개 정정, 격자 손 수정 안내 정정, 연결 실패 문면, 시각 표기 전수.",
        "<b>왜 이것이 먼저인가</b>: 검토표(핸드오버 §5 ⑧)에서 드리프트가 이 트랙 최다 사고라 ⓪ 를 첫 순서로 제안했고 승인하셨습니다 — 오늘 오후만 해도 커밋 30여 개가 08224cc 화면에 못 닿은 채였습니다. "
        "설계에서 고른 것: 병합·리베이스는 절대 안 합니다(ff-only). 손 수정을 치우는 것은 사람이 누른 update.bat 만 하고 기계는 보류합니다 — 되돌릴 수 없는 일을 기계가 하지 않는 것이 P-3 입니다. "
        "검사는 임시 git 저장소 셋(원격 · 이 PC · 세션)으로 다섯 경로를 실제로 돌렸고, 주입 9/9 — 그중 하나(0 인데 돎)는 첫 판에 검사가 <b>매달려</b> 적발이 아니었습니다(하네스가 죽였다). 검사가 스스로 멈추게 고친 뒤 적발. 관문 <b>1055 → 1062</b>(증분 +7 = 신규 7, 일치 · TZ=Asia/Seoul) · 걷기 ok. "
        "<b>다음</b>은 검토표 순서대로 ⑤b(장기 값 입력 폼) → ①⑤a(자기 점검 화면) → ② 한 명령 → ③. 장기 원천은 여전히 <b>VELA 의 2026-08-05 실측을 인용</b>한 것입니다(PC 에서 apihub 「장기예보」 를 한 번 보시면 확정). D-20 임계(칸 3·4)는 값 한 줄로 주십시오 — 세션이 커밋합니다.")
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
