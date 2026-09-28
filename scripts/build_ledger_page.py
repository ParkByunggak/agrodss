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
    ("⓪ <b>update.bat 은 끝났습니다</b> — 06:18 스크린샷 「실행 중 9903974 · 자동 갱신 대기」. 이제 꼬리만 봅니다 (0분)",
     "<b>할 것</b>: 없다. 화면이 600초마다 저장소를 보고 뒤처지면 스스로 따라간다. <b>화면에 보일 것</b>: 오늘 커밋이 올라간 뒤 10분 안에 꼬리가 「자동 갱신 HH:MM 갱신 9903974 → …」 로 바뀌고 새 커밋으로 다시 뜬다. "
     "「보류: …」 나 「실패: …」 가 보이면 <b>보낼 것</b>: 그 문장 그대로(보류는 아무것도 안 버린 상태 — 추적 파일에 손 수정이 있으면 그 이름이 적혀 있다). 아무 말도 없이 옛 해시가 계속이면 그것도 보낸다"),
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
    ("③ <b>WO-LLM-01 첫 숫자 — 왔습니다(09-29 08:21)</b>: 70 발화 · 고침 4 → 문턱 30 미달, 그 자체가 결과. 넷은 규칙으로 닫았습니다 (0분)",
     "<b>할 것</b>: 없다. LLM 보조 판별기는 세우지 않는다(지시서 §5-2). 고치신 넷(포장을 보니 → 예찰 · 물주었다 → 관수 · 스프링쿨러 가동 → 할 일 · 옛 '분류 안 됨')은 이 회차 커밋에서 규칙이 됐다 — "
     "<b>화면에 보일 것</b>: 같은 문장을 다시 치면 고치신 종류로 바로 나온다. <b>보낼 것</b>: 앞으로도 초안 종류를 손으로 고치신 것은 그대로 두시면 된다(원장이 그것을 기억한다) — 다음 측정은 검토표 ③(상시 측정)이 화면에서 한다"),
    ("④ 결정 둘 — 한 줄씩",
     "<b>D-17</b> 예: <i>\"파일명 시각은 쓴다 — 단 라벨에 '저장·전송 시각일 수 있음' 을 유지\"</i> 또는 <i>\"안 쓴다 — 찍은 때가 없으면 날짜를 묻는다\"</i>. "
     "<b>D-19</b> 예: <i>\"공개는 몰 상세페이지만 · 첫 수확 뒤 · 호스팅은 그때 정한다\"</i> — 셋(어느 화면 · 언제 · 호스팅)이 한 줄에 있으면 된다. 지금 화면(밭 자료)은 계속 루프백"),
    ("⑤ <b>D-21 — 단기·중기는 화면에서 확인됐습니다(09-29 아침 · 발표 05시·06시 · 중기 괴산)</b> · 남은 것은 1개월 전망 한 주 등재 (5분)",
     "<b>어느 지점인가(물으셨던 것)</b>: 단기는 등록부 필지 좌표를 기상청 5km 격자로 바꾼 칸(이 회차부터 줄에 「필지 자리 5km 예보 구역」 · /judge 에 칸 번호) · 중기는 「괴산 권역 · 기온은 충주 기준」(괴산은 기온 코드를 충주에서 빌린다 — VELA 검증 기록). "
     "같은 뜻의 물음 다섯이 둘로 갈린 것(\"오늘 날씨 어떄\" · \"오늘 날씨는\" 이 본 것)도 이 회차에 고쳤다 — 날씨 낱말로 끝나면 물음이다. "
     "<b>지금 커밋</b>: 단기(오늘부터 3일) → 중기(D+3~D+10 · 권역) → 장기(등재분)를 한 인용에 이어 낸다. 못 받은 쪽은 그 이유를 그대로 — 지금 장기는 「장기: 없음 — 등재된 장기 전망 없음」. "
     "<b>장기 넣는 법(폼)</b>: 화면 왼쪽 <b>설정</b>(<code>/me</code>) → 「장기 전망 등재 →」. 날씨누리 → 기후예측 → 1개월 전망(목요일 발표)을 옆에 띄우고 주(週)마다 하나씩 — 전망 종류 · 발표일 · 대상 시작/끝 · 지역(발표문 표기 그대로, 예: 충북) · "
     "기온 높음/비슷/낮음 % · 강수 많음/비슷/적음 % · 출처 제목 · 출처 주소(발표문 URL) → 「등재」. 합이 100±5 가 아니거나 URL 이 없거나 날짜 꼴이 틀리면 <b>저장하지 않고 이유</b>를 말합니다(친 값은 남습니다). 두 번 눌러도 한 번만 남고, 잘못 넣은 것은 「이 항목 지우기」. "
     "저장은 git 밖 덮개 <code>climate_outlook_local.json</code> 에만 — <code>update.bat</code> 도 자동 갱신도 건드리지 않습니다(파일로 넣어도 됩니다 · 같은 열). "
     "<b>그 뒤 화면</b>: 「장기(1개월 전망 · 등재 기준 · 발표 09-25) 10-05~10-11 충북 기온 높음 50% · 비슷 30% · 낮음 20% / 강수 …」 · <code>/judge</code> 에 표(출처 링크). "
     "<b>보낼 것</b>: 날씨 카드 한 줄(단기·중기가 붙었는지 · 못 받은 이유). 시스템은 이 파일 밖에서 장기 값을 얻지 않는다 — VELA 가 2026-08-05 에 오픈 API 가 없다고 잰 것을 인용했고, 이 세션은 그 원천들이 차단이라 다시 못 쟀습니다(PC 에서 apihub 「장기예보」 를 한 번 보시면 확정)"),
]
NEXT_SESSION = [
    ("세션 시작 시 훅 활성 확인(가드 창)", "스크래치패드에 heredoc 파일 쓰기 1회 시도 — 차단되면 훅 활성, 통과하면 그 세션은 규율로만 지킨다(U-22: 세션 루트가 다른 저장소면 가드가 잠든다)"),
    ("D-20 임계가 오면 — 세 줄", "<code>prewalk_grid --stage 3 4 --key drought_rules</code> 로 잔여를 잰다(상태 검사 하나뿐이어야 한다) → 격자 칸 3·4 → 문서 재생성 → 상태 검사 하나. D-18 규칙을 넓히실 때도 같은 세 줄"),
    ("WO-LLM-01 — 닫힘(09-29 08:21 · 70 · 고침 4 · 미달)", "하네스는 세우지 않는다. 손으로 고친 넷은 규칙이 됐다(test_sprinkler_plan). 다음 재료는 원장이 자라야 나온다 — 검토표 ③(오분류 상시 측정 · /changes)이 그 자리. 30 을 넘는 날이 오면 그때 트리거 D 결정 뒤 하네스"),
    ("검토표 순서 — 다음은 ①⑤a 자기 점검 화면", "발행자 승인(2026-09-28 \"제안 순서대로\") — ⓪ 자동 갱신(U-39) · ⑤b 입력 폼(/me/outlook) 섰다. 다음: ①⑤a <code>/selfcheck</code>(읽기 전용 — 증상 두 문장의 분류·라우팅 · /judge 카드 존재 · 날씨 카드 한 줄) → ② 격자 값 한 명령 → ③ 오분류 상시 측정"),
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
BEST = ("<b>오늘 아침 화면에서 보신 넷을 한 회차에 고쳤습니다 — 라이브는 9903974 로 확인됐고(06:18 꼬리 · 자동 갱신 대기), 이 커밋은 화면이 스스로 받습니다.</b> "
        "<b>① 「오전에 스프링쿨러 가동 1시간한다」</b>가 '본 것' 으로 적혀 손으로 '할 일' 로 바꾸셨습니다. 장치 이름에 돌리는 말(가동·돌·틀)이 붙으면 관수로 읽고(장치 이름 홀로는 여전히 아닙니다 — \"스프링쿨러가 고장났다\" 는 본 것), "
        "문장 끝 \"…한다\" 는 작업 말이 있을 때만 할 일(\"잎이 마른다\" 는 본 것), \"오전에\" 처럼 때만 말하면 오늘입니다. 고치신 뒤 같은 형태를 세니 구멍이 하나 더 — \"내일 파종\" · \"모레 방제\" 가 <b>내일 날짜의 한 일</b>로 들어가고 있었습니다(계획 대 실제가 안 한 일을 한 것으로 셉니다). 오늘보다 뒤면 할 일입니다. "
        "손으로 고른 할 일은 작업 말(관수·예찰)로 남고 카드가 「고르신 종류」 라고 말합니다 — 위 답변은 보낸 때의 기록이라 고쳐 쓰지 않습니다. "
        "<b>② WO-LLM-01 첫 숫자</b>(08:21): 70 발화 · 고침 4 · 편집 0 → 문턱 30 미달, 그 자체가 결과입니다. 넷 다 낱말·규칙 구멍이라 여기서 닫았습니다(\"아침에 포장을 보니\" → 예찰 · \"오늘 물주었다\" → 관수 · 스프링쿨러 가동 · 옛 '분류 안 됨' 은 이미 없음). LLM 판별기는 세우지 않습니다. "
        "<b>③ 같은 뜻의 날씨 물음 다섯이 둘로 갈린 것</b>: \"오늘 날씨 어떄\"(오타) · \"오늘 날씨는\"(조사 끝)이 물음표·의문사가 없어 본 것으로 갔습니다. 날씨 낱말로 끝나거나 어때 오타면 물음입니다(\"오늘 날씨가 좋다\" 는 그대로 본 것). "
        "<b>④ 「이 날씨는 어느 지점을 말하는가」</b>: 단기는 등록부 필지 좌표를 기상청 5km 격자로 바꾼 칸입니다 — 이제 줄에 「필지 자리 5km 예보 구역」, /judge 에 칸 번호가 붙습니다. 중기는 「괴산 권역 · 기온은 충주 기준」 — 괴산은 기온 코드를 충주에서 빌린다는 VELA 검증 기록 그대로, 빌린 것을 숨기지 않습니다. 필지가 하나라 지금 예보는 그 필지의 것입니다. "
        "말뭉치 104 → 118(옛 104 의 종류 변화 0 · 측정) · 검사 20 · 주입 12/12 · 걷기 ok · 관문 <b>1068 → 1088</b>(증분 +20 = 신규 20, 일치 · TZ=Asia/Seoul).",
        "<b>왜 이것이 먼저인가</b>: 실사용에서 보신 것이 재료이고(다리 B), 넷 다 지금 안 고치면 다음 문장에서 또 손으로 고치셔야 하는 것이었습니다. 검토표 다음 순서(①⑤a 자기 점검 화면)는 그 뒤입니다. "
        "설계에서 고른 것: 장치 이름 홀로를 관수로 넓히지 않았습니다(09-21 규율 — \"급수 시설이 없다\" 가 관수 사건이 됩니다). \"…한다\" 도 작업 말 없이는 안 넓혔습니다(관찰 문장 대부분이 그 꼴). '격자' 라는 말은 화면 낱말 표가 재배 달력으로 바꾸므로 예보 자리는 '예보 구역' 이라 썼습니다 — 같은 낱말이 두 뜻으로 쓰이던 자리입니다. "
        "<b>다음</b>은 검토표 순서대로 ①⑤a(자기 점검 화면 /selfcheck) → ② 격자 값 한 명령 → ③ 오분류 상시 측정. 발행자 몫으로 남은 것: D-20 임계 한 줄 · D-17/D-19 · 1개월 전망 한 주 등재(/me/outlook) · §5 ⑦ 메모 등재 여부.")
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
