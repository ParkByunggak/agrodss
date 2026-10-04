# -*- coding: utf-8 -*-
# FILE: scripts/build_ledger_page.py
# ROLE: [U-19 · D-13] docs/agrodss_backlog.md → 발행용 작업대장 페이지(HTML 조각 — 발행 도구가 doctype/head/body 를 씌운다).
#   읽기 전용 — 저장소에는 아무것도 쓰지 않는다. 출력은 인자로 준 파일 하나뿐.
#   [2026-09-27] 이 생성기가 세션 스크래치패드에만 있었다(U-35 · prewalk_grid 와 같은 형태 — 세션이 끝나면 사라진다). 저장소로 옮기며 옛 회차의
#   BEST 스물여덟 개를 잘라냈다(그 서술은 핸드오버 표와 대장 로그가 대신한다). 회차마다 다시 쓰는 것 셋: BEST(발행자 형식 — 할 것 하나 · 한 것 · 막힌 것, check_best 가 강제) · NEXT_PUBLISHER · NEXT_SESSION.
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
    ("⓪ˢ <b>종구 생산 — 둘</b>: ① 용도에 「종구 생산」 — 새 코드를 받은 뒤 채팅에 아무 말이나 한 줄 보내면 「밭 정보 → 종구 생산」 카드가 섭니다(10-04 일지의 「종구생산을 위한 목적이다」 를 읽은 것) → '일지에 넣기' · 지금 바로는 맨 아래 사용자 탭 → 설정 → 필지 구역의 용도 칸(새 코드 뒤엔 왼쪽 메뉴 「밭 정보 · 설정」 → 「밭 정보」)(1분 · 10/14 전에) ② 수확 · 수확 후 두 칸의 종구 기준 값(D-24)",
     "<b>①을 하시면 즉시</b>: 수확 시기 답이 「종구 재배의 수확 때는 재배 달력에 아직 없습니다 — 잎 수확 기준으로는 말하지 않습니다」 로 바뀌고, 10/14 부터 나갈 「수확 지연 — 잎 노화·도복」 경보와 수확 칸 할 일이 안 나갑니다(그 이유가 메모에 적힙니다). 과습 등 수확 전 칸은 그대로입니다. 씨앗(저장소 파일)은 바꾸지 않았습니다 — 이 밭의 값은 그 화면 몫입니다. "
     "<b>②는 값</b>: 두 칸(수확 · 수확 후)마다 창(심은 날 뒤 며칠~며칠) · 위험(이름 · 회복 가능 여부 · 무엇을 보는지 · 출처) · 할 일(이름 · 며칠째) · 출처 한 줄씩 — 예: <i>종구 비대·수확 70~100일 · 위험 인경 부패(회복 불가 · 비·배수) · 할 일 수확 95일째 · 출처 농사로 쪽파 종구 생산(또는 이장 경험 2026)</i>. 세션이 한 명령(<code>apply_grid_value --stage 5 --key by_use</code>)으로 넣고 검증기가 합친 달력을 같은 관문으로 돕니다. 값이 없어도 ①만으로 틀린 경보는 멎습니다. <b>밭 확인 두 줄</b> 중 고랑 물 빠짐이 더 급하다는 말씀 — 종구는 잎이 상해도 건지지만 인경이 썩으면 전부 잃는다 — 그 한 줄이 과습 경보의 근거(배수)와 바로 잇닿습니다"),
    ("⓪ʷ <b>WO-ASK-01 — 결정 ① 「가」 반영됨(2026-10-03) · 다음 물음 하나: 배수가 「나쁨」 이면 과습 경보를 올릴까요</b> (1분 · 지식이라 세션이 정하지 않습니다)",
     "<b>지금 화면</b>: 밭 정보(/me)의 배수 칸이 「판정이 읽는 값」 으로 바뀌었고, 위험 경보의 과습 줄 근거에 「배수 N(밭 정보 — 속성이 주, 관측이 보조)」 가 붙습니다. 배수를 안 적으면 「배수 등급 없음 — 밭 정보에 적으면 …」 메모가 뜹니다. "
     "<b>안 한 것</b>: 등급(주의/경보)은 그대로입니다 — 「배수 나쁨 + 비 예보 N mm 면 경보」 같은 규칙은 임계라 발행자 몫입니다. <b>보낼 것</b>: 「나쁨이면 주의 그대로」 또는 「나쁨 + 7일 강수 ≥ N mm 면 경보 — 출처 …」 한 줄. 없어도 돌아갑니다(근거에 싣기만 한다). "
     "요구 문장은 이제 한 자리에서 나옵니다(누가 · 무엇 · 어디서 · 왜 지금 — 명령줄·환경변수는 농가 문장에 못 들어옵니다). 묻기 기록도 섰습니다(채팅 「오늘」 의 「물은 것」 줄). "
     "<b>반복 상한 3 · 유효기간 — 반영됨(2026-10-03 · 추론 표시 그대로)</b>: 같은 물음은 세 번까지 붙고, 그 뒤엔 건너뛰며 결정 화면 머리에 「더 묻지 않는 것 N건 — 모르겠다와 같은 신호」 로 올라옵니다(말씀하신 자리). 필지 속성 답은 무기한(고칠 때까지) · 검정값 유효기간은 재배 달력에 그 키가 생기면 읽습니다. §9 답 묶기도 섰습니다(답 → 밭 정보 초안 → 넣기). <b>값 하나 더 — 배수 선택지의 기준 문면(§7)</b>: 지금은 「좋음 · 보통 · 나쁨」 이 화면에도 질문에도 그대로입니다(말씀대로 §7 이 아직 안 들어간 것). 세 줄(예: <i>나쁨 — 비 온 다음 날에도 고랑에 물이 남는다</i>)을 주시면 저장값은 그대로 두고 표시에 붙입니다. <b>10-03 일지에 적으신 「고랑 물 빠짐이 잘 되고 있다」 는 새 코드(10-04)가 읽습니다</b> — 다음 채팅 말 뒤에 「밭 정보 → 배수 좋음」 카드가 서고 넣기 한 번이면 과습 근거가 그 값을 읽습니다(10-04 전에는 어느 칸으로도 안 묶여 배수를 또 물었습니다 — 발행자 진단 그대로). 기준 문면은 이제 급하지 않습니다 — 오면 표시에 붙입니다. "
     "<b>추론값 표(§10) — 재배 달력 문서 끝의 「추론값 — 누가 고칠 수 있는가」 24행</b>: 세션이 농가 9 · 기준 자료 15 로 갈랐습니다. 틀린 행만 「이름 — 농가/정본」 으로 주시면 됩니다(전부 맞으면 보낼 것 없음). <b>D-23 은 결정 화면에</b>(배수 나쁨 → 경보 조건 · 말씀하신 「전자」 가 제안값 · 추론 표시) — 맞다 한 번이면 규칙 한 줄이 들어갑니다"),
    ("⓪⁼ <b>저장소 비공개 전환</b> — 2026-10-02 20:59 UTC 재측정: <b>여전히 공개</b>(visibility=public) (1분)",
     "<b>할 것</b>: GitHub 저장소 → Settings → 맨 아래 Danger Zone → Change visibility → Private. 9/20 에 하셨다고 하셨는데 9/21 · 10/02 두 번 다 공개로 잽니다 — 저장이 안 됐거나 되돌려진 것. "
     "지번·좌표·검정값은 추적 파일에 없고(U-18 2단계) 이력 두 커밋에만 남아 있어, 비공개가 되면 앞으로의 접근은 막힙니다(이미 나간 것은 되돌릴 수 없습니다 — 이력 정리(force-push)는 파괴적이라 발행자 결정). "
     "<b>보낼 것</b>: 「비공개로 바꿨다」 한 줄 — 세션이 다시 재서 U-18 을 닫습니다"),
    ("⓪⁻ <b>밭에서 본 것 두 줄 — 10-03 일지에 들어왔습니다</b>(「고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않음」 — 발행자 전언 10-03) · 남은 것 하나 (1분)",
     "<b>세션이 잰 것</b>: 그 문장은 「본 것」 으로 읽힙니다(맞다). 배수 값은 10-04 새 코드가 그 줄에서 읽어 「밭 정보 → 좋음」 카드로 올립니다(넣기 한 번) · 황화 쪽은 증상 말이라 원인 후보가 그대로 나갑니다 — 「더 진행되지 않음」 같은 추이는 아직 못 읽습니다(등재 후보 — 발행자 판단). "
     "<b>할 것</b>: 증상 있는 포기를 뽑아 봤으면 그 한 줄(<i>인경 밑이 물렁하고 구더기가 있다 / 단단하다</i>) — 감별 넷 중 어느 쪽인지가 그 줄로 갈린다. <b>보낼 것</b>: 없다 — 일지에 확인한 것만 원장이 안다"),
    ("⓪⁺ <b>결정 — 한 화면에서 답하기</b>: 메뉴 「결정」(<code>/me/decisions</code>) — 새 커밋이 선 뒤 (5분)",
     "<b>할 것</b>: 화면의 12줄에 맞다 / 다르다(→ 무엇) / 모르겠다 중 하나를 찍고 저장. 맨 위 D-2(판정을 소비자에게 보일 것인가)부터 — 다섯 항목이 그 답에 매달린다. "
     "제안값 옆의 <b>권고</b>는 작업 기록에 권고로 적혀 있던 값이고 <b>추론</b>은 세션이 미룬 값이라 맞다를 눌러도 그 표시가 남는다. 모르는 것은 <b>모르겠다</b>가 맞는 답이다(처음 지으신 밭의 수확 시기처럼) — 쌓이면 그 항목은 발행자 몫이 아니라 아직 어디에도 없는 값이었다는 신호라 세션이 갈래를 고친다. "
     "<b>화면에 보일 것</b>: 「답 N/12」 와 맨 아래 「세션에 보낼 것」 글(답한 것만 한 줄씩). <b>보낼 것</b>: 그 글을 그대로 — 답은 이 PC 에만 있어 세션은 그 글로만 안다. 세션이 작업 기록의 상태 열을 커밋으로 고친다(화면은 항목을 닫지 않는다)"),
    ("⓪ <b>update.bat 은 끝났습니다</b> — 06:18 스크린샷 「실행 중 9903974 · 자동 갱신 대기」. 이제 꼬리만 봅니다 (0분)",
     "<b>할 것</b>: 없다. 화면이 600초마다 저장소를 보고 뒤처지면 스스로 따라간다. <b>화면에 보일 것</b>: 오늘 커밋이 올라간 뒤 10분 안에 꼬리가 「자동 갱신 HH:MM 갱신 9903974 → …」 로 바뀌고 새 커밋으로 다시 뜬다. "
     "「보류: …」 나 「실패: …」 가 보이면 <b>보낼 것</b>: 그 문장 그대로(보류는 아무것도 안 버린 상태 — 추적 파일에 손 수정이 있으면 그 이름이 적혀 있다). 아무 말도 없이 옛 해시가 계속이면 그것도 보낸다"),
    ("① 확인 셋 — <b>이제 화면이 스스로 돕니다</b>: 메뉴 「자기 점검 — 화면이 스스로 확인」(<code>/selfcheck</code>) (1분)",
     "<b>할 것</b>: 새 커밋이 선 뒤 왼쪽 메뉴의 「자기 점검」 을 연다. 화면이 ㉡ 증상 두 문장(<i>잎 끝이 누렇게 되는데 왜 그런가요</i> · <i>잎이 노래지는데 어떻게 해야 하나</i>)을 같은 길로 돌려 "
     "「이렇게 보입니다 · 원인 후보 …」 와 '본 것' 카드인지, ㉢ 판단 화면에 「증상 → 원인 좁히기」 카드가 있는지, ⑤a <i>내일 날씨 어때</i> 가 「찾아본 것입니다」 인지 대조하고 걸린 시간을 적는다. "
     "일지에는 아무것도 넣지 않는다. <b>화면에 보일 것</b>: 「전부 맞다 (5/5)」 — 좌표·키가 있는 PC 라면 날씨 줄까지 맞다. "
     "<b>보낼 것</b>: 「다른 것 N」 이 보이면 그 줄(실제: …)을 그대로. ㉠ <b>엔터</b>만 사람 몫이다(브라우저 안의 동작이라 화면이 못 본다): 채팅에 <i>오늘 물 줬다</i> 치고 Enter → 보내지면 됐다"),
    ("② <b>D-18 반영됨</b> — ㉡이 그 확인이다",
     "쓰신 감별 넷이 격자 칸 3 에 그대로 들어갔다. <b>규칙을 넓히실 때(예: '잎이 비틀린다' 를 더하고 싶다)</b>: 값과 출처를 세션에 한 줄로 주시면 세션이 세 줄"
     "(미리 걷기 → 격자 → 문서 재생성 → 상태 검사)을 한다. <b>격자 파일을 PC 에서 손으로 고치지는 마십시오</b> — <code>data/grid/jjokpa_autumn.json</code> 은 추적 파일이라 "
     "다음 <code>update.bat</code> 이 그 수정을 <code>data\\_local_backup\\</code> 으로 치우고 되돌립니다(값은 남지만 화면에는 없습니다). 격자는 세션 커밋으로만 바뀝니다. "
     "모양만 참고: <code>{\"symptoms\": [\"비틀\"], \"causes\": [{\"name\": \"…\", \"check\": \"…\", \"recoverable\": false}], \"first_check\": \"…\"}</code>"),
    ("②b <b>D-20 임계 — 반영됨(2026-09-30 · 7일 · 발행자 측 추론 · 표준 아님) · D-22 수확 칸 — 맞다(2026-10-03) 반영됨</b> — 재배 달력 수확 칸에 「가뭄 판단 없음(N/A) · 출처: 발행자 결정 D-22 … 추론」 으로 적었습니다. 10-15 부터 가뭄 물음의 답은 「수확 칸에는 가뭄 · 관수 판단을 두지 않습니다」 입니다(비운 것과 다르게 — 출처가 답까지 갑니다). 결정 화면의 D-22 카드는 「결정됨」 으로 남습니다(지우기는 세션 커밋으로). 농진청 정본이 오면 같은 한 명령으로 바꾼다 · 아래는 값을 바꿀 때의 예",
     "<b>정할 것</b>: 예를 들어 <i>\"가을 쪽파는 비 안 온 지 7일이면 관수를 검토한다 — 출처: 농진청 쪽파 재배 지침(또는 내 경험 2026)\"</i>. "
     "<b>보낼 것</b>: 그 문장 한 줄(N 과 출처) — 세션이 한 명령(<code>apply_grid_value --stage 3 4 --key drought_rules</code>: 미리 걷기 → 격자 칸 3·4 <code>\"drought_rules\": {\"dry_days\": 7, \"source\": \"…\"}</code> → 문서 재생성 → 검사)을 돌리고 "
     "남은 상태 검사 하나를 고쳐 커밋한다. 격자 파일을 PC 에서 손으로 고치면 ② 와 같은 이유로 다음 <code>update.bat</code> 이 되돌립니다 — 값 한 줄을 주시는 것이 길입니다. "
     "<b>그 뒤 화면</b>(2026-09-29 갱신 — 말씀하신 대로 기상청 지난 일강수를 씁니다): <i>가뭄이 심한데 물 줘야 하나</i> → 「마지막 비·관수 2026-09-25(기상청 관측 지점 131) 뒤 무강수 4일 — 임계 7일 미만: 아직 관수 판단 아님 · "
     "수분 요구 중간 · 결핍 민감 중간」 — 비 온 날은 좌표에서 가장 가까운 관측 지점의 일강수(0.1mm 이상 = 기상청 강수일 정의)로 세고, 채팅의 <i>어제 비가 왔다</i> 나 관수 기록이 더 최근이면 그쪽입니다. "
     "임계 날수 내내 비가 없었으면 묻지 않고 「무강수 N일 이상 — 관수 검토」 로 냅니다(관측은 임계가 선 뒤에만 · 임계 날수만 부릅니다). 관측 키(KMA_API_HUB_KEY)나 좌표가 없을 때만 「마지막으로 비 온 날이나 관수한 날을 알면 판단합니다」 로 묻습니다"),
    ("③ <b>WO-LLM-01 — 첫 숫자는 왔고(09-29 08:21 · 70 · 고침 4 · 미달), 이제 화면이 늘 셉니다</b>: 변경 로그(<code>/changes</code>) 「종류 고침」 줄 (0분)",
     "<b>할 것</b>: 없다. 스크립트를 다시 돌리실 필요가 없다 — 변경 로그를 열면 「종류 고침 재료 N건 (손으로 고친 종류 a · 편집 b) — 문턱 30: 미달/충족 · 농가 발화 T · 잰 때」 가 늘 보인다(건수만 · 문장은 안 보인다). "
     "고치신 넷(포장을 보니 → 예찰 · 물주었다 → 관수 · 스프링쿨러 가동 → 할 일 · 옛 '분류 안 됨')은 4c979fe 에서 규칙이 됐다. <b>보낼 것</b>: 그 줄이 「충족 — 발행자 결정 차례」 로 바뀌고 색이 달라지면 그 줄 한 번 — 그때 트리거 D(어떤 발화를 LLM 에 넘길지)를 정하시면 하네스를 세운다. 초안 종류를 손으로 고치신 것은 그대로 두시면 된다(일지가 그것을 기억한다)"),
    ("④ 결정 둘 — <b>이제 ⓪⁺ 결정 화면에서</b>(D-17 · D-19 둘 다 그 열두 줄에 있다 · 아래는 한 줄로 주실 때의 예)",
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
    ("D-20 농진청 정본 임계가 오면 — 같은 한 명령(지금은 7일 · 추론 표시)","<code>python -m scripts.apply_grid_value jjokpa_autumn --stage 3 4 --key drought_rules --value-file v.json</code> — 미리 걷기(잔여가 상태 검사 하나를 넘으면 안 넣는다) → 격자 → 문서 재생성 → 검사 → 남은 것 보고. 남은 상태 검사 하나의 기대를 새 상태로 고쳐 격자·문서·검사를 한 커밋으로. D-18 규칙을 넓히실 때도 같은 명령(<code>--stage 3 --key symptom_rules</code>)"),
    ("WO-LLM-01 — 닫힘(09-29 08:21 · 70 · 고침 4 · 미달)", "하네스는 세우지 않는다. 손으로 고친 넷은 규칙이 됐다(test_sprinkler_plan). 다음 재료는 원장이 자라야 나온다 — 검토표 ③(오분류 상시 측정 · /changes)이 그 자리. 30 을 넘는 날이 오면 그때 트리거 D 결정 뒤 하네스"),
    ("종구 생산 — 자리와 문은 섰다(2026-10-03) · 값이 오면", "D-24 값(두 칸 · 창 · 위험 · 할 일 · 출처)이 한 줄씩 오면 <code>python -m scripts.apply_grid_value jjokpa_autumn --stage 5 --key by_use --value-file v.json</code>(v.json = {\"종구\": {\"source\": …, \"window\": …, \"risks\": […], \"tasks\": […]}}) · 칸 6 도 같은 명령 → 미리 걷기 → 격자 → 문서 → 검사. 넣은 뒤 셋만 본다: 수확 시기 답이 종구 창으로 · 위험 경보 메모의 `use_gap_stages` 가 빈다 · 계획표에 종구 할 일이 선다. 용도 값(밭 정보 「종구 생산」)은 발행자 PC 덮개 몫 — 씨앗을 바꾸려면 잎 수확 전제 검사 21파일 전수가 한 묶음(발행자 확인 뒤)"),
    ("WO-ASK-01 — 1 · 2 · 3 · 3′ · 4 · §9 · 5(§10 §12) 끝(2026-10-03) · 남은 §14", "6 §5-2 정본 채우기는 --probe 뒤(발행자 PC). §10 표(docs/grid_jjokpa_autumn.md) 에서 뒤집힌 행은 <code>apply_grid_value</code> 로 그 값의 fixable_by 만 고친다(값은 그대로). 「농가 확인」 으로 승격할 때는 출처에 날짜 · 확신 한 단계. 배수 선택지 기준 문면(§7)이 오면 등록부 어휘 <b>표시</b>에 붙인다(저장값 좋음·보통·나쁨은 그대로 — 화면 · 질문 둘 다 같은 자리에서). <b>D-23 맞다가 오면</b> <code>judge/risk_alert.py</code> 등급 규칙 한 줄(배수 나쁨 + 예보 신호 → 경보 · 신호 임계는 지금 값 그대로 · 표시가 답까지) + 양방향 검사(나쁨+신호 경보 · 나쁨만 주의 · 좋음+신호 경보 그대로) · 대장 D-23 완료 · DECIDED 에 넣고 측정에서 뺀다(D-22 와 같은 길). 유효기간 키가 격자에 생기면 질문 생성이 읽는다. 새 요구 문장은 <code>need()</code> 로만 · 원장은 send 에만"),
    ("결정 화면의 「세션에 보낼 것」 글이 오면","한 줄이 한 답(<code>id 맞다</code> · <code>id 다르다 — 무엇</code> · <code>id 모르겠다</code>). 맞다/다르다는 작업 기록 상태 열을 그 답으로 고쳐 커밋(D-2 가 서면 D-3 · D-7 · D-19 · M-11 행도 함께) · 다르다의 「무엇」 은 근거 열에 발행자 말로 · <b>모르겠다</b>는 측정(<code>measure_publisher_bottleneck</code> JUDGMENTS)의 그 행을 P1 → P4 로 고치고 보고서를 같은 기준일로 다시 생성(갈래의 사후 교정 — 발행자 ①). 화면 항목(<code>ingest/decisions.py</code> ITEMS)에서 답이 선 것은 빼지 않는다 — 답한 카드로 남고 지우기는 발행자 몫"),
    ("WO-PB-01 뒤 — 표 회신 · --probe", "① 표(<code>docs/wo_pb01_publisher_bottleneck.md</code> §1)에서 뒤집힌 행은 스크립트 JUDGMENTS 를 고치고 같은 기준일로 다시 생성(문서는 손으로 안 고친다 — 동기 검사) ② PC <code>--probe</code> 표가 오면 REACH_SNAPSHOT 을 그 측정·시점으로 바꿔 다시 생성(도달한 원천은 다음이 형태 확인 §4 — 단위 불일치면 P4) — 병행이지 선행이 아니다(H2 는 안 바뀐다) ③ 10-18 이후 <code>--today</code> 로 다시 생성하면 30일 축이 뜻을 갖는다"),
    ("검토표 — 다섯 다 섰다(2026-09-29)","발행자 승인 순서(2026-09-28 \"제안 순서대로\") 그대로: ⓪ 자동 갱신(U-39) · ⑤b 입력 폼(/me/outlook) · ①⑤a 자기 점검(/selfcheck) · ② 한 명령(<code>apply_grid_value</code>) · ③ 상시 측정(/changes 「종류 고침」 줄). 자율 큐는 비었다 — 남은 것은 발행자 몫(값과 결정)과 실사용 관찰뿐. 다음 회차는 낡음 대조부터"),
    ("D-21 장기 값이 오면","발행자가 덮개 <code>climate_outlook_local.json</code> entries 에 넣은 뒤 상태 검사(<code>test_climate_outlook</code> 마지막 것)가 초록인지 · 채팅 카드에 「장기(…)」 가 붙는지 · /changes 에 못 읽음이 없는지 셋만 본다. 값은 세션이 넣지 않는다 · 씨앗은 발행자가 세션에 값을 주어 커밋할 때만"),
    ("U-20 — NCPMS 임계 정본이 오면","필지 축 가운데 토성 · 미기상은 소비자 0(배수는 10-03 부터 과습 근거가 읽는다 — 등급 규칙은 D-23). 정본 없이는 대리값이 경보로 나가므로 예찰 보정은 지금은 안 한다"),
    ("낡음 대조", "대장 상태 열 · 이 페이지의 두 목록 · 핸드오버 §5 — 회차마다 다시 쓴다(시점 축). 실사용 관찰은 관찰 시점과 함께"),
]

def li(items):
    # [발행자 붙임 2026-09-28] 머리(k)를 escape 해서 <span style=…>·<code> 가 글자 그대로 화면에 나갔다 — 머리도 본문도 여기서 쓴 HTML 이지 사용자 글이 아니다.
    # 그리고 <ol> 번호 위에 ⓪①② 표지를 또 달아 "1. ⓪" 로 두 번 셌다 → 표지만 남기고 목록 번호는 뗀다(<ul>)
    return "".join(f"<li><b>{k}</b><span>{v}</span></li>" for k, v in items)

pills = "".join(f'<span class="st st-{s}">{s} <strong>{n}</strong></span>' for s, n in counts.items() if n or s != "폐기")

# [U-19 · 발행자 2026-09-20] "최선의 다음 한 수"는 누적 보고가 아니라 **지금의 한 수 하나**다. 앞 회차 서술은 핸드오버 몫.
# [발행자 2026-10-03 "회차 보고는 이 형식으로. 이유와 앞 회차는 핸드오버에."] 머리·이유 두 덩이가 회차마다 앞에 붙어 아홉 회차가 한 덩어리였다 —
#   "'최선의 다음 한 수'라는 이름이 이미 그 뜻이었습니다 — 하나를 고르는 것 … 보고 자체가 '요구는 있는데 찾을 자리가 없는' 상태". 그래서 형식을 **코드가 강제**한다:
#   발행자가 할 것 — 하나(무엇을 · 어디서 · 왜 지금 · 안 하면) · 세션이 한 것 — 세 줄 안(관문 · 주입) · 막힌 것 — 한 줄. 열 줄 안쪽. 이유 문단 없음 · 앞 회차 없음.
#   BEST 는 회차마다 **덮어쓴다**(붙이지 않는다). 아래 check_best 가 줄 수 · 하나 · 누적 어휘를 본다 — 어기면 생성기가 멈춘다.
BEST = {
    "date": "10-04",
    "do": {"what": "용도를 「종구 생산」 으로 — 새 코드를 받은 뒤 채팅에 아무 말이나 한 줄 보내면 「밭 정보 → 종구 생산」 카드가 섭니다(일지의 그 말을 읽었습니다) → '일지에 넣기'",
           "where": "채팅(update.bat 뒤) · 또는 왼쪽 메뉴 「밭 정보 · 설정」 → 「밭 정보」 → 용도 칸(새 코드 뒤 — 지금 화면에선 맨 아래 사용자 탭을 누르면 나오는 설정 → 필지 구역)",
           "why_now": "10/14 부터 나갈 잎 수확 기준 경보(수확 지연 · 서리 잎 손상)가 이것으로 안 나갑니다 — 종구 재배의 수확 기준은 재배 달력에 아직 없다고 답합니다",
           "if_not": "10일 뒤부터 매일 틀린 「수확 지연 — 회복 불가」 경보가 나갑니다"},
    "did": ["진단대로 한 곳에 세웠습니다 — 묻기 전에 속성 → 일지(관찰) 순으로 읽고, 값을 읽을 수 있으면 묻지 않고 「밭 정보」 카드로 올립니다(일지의 「물 빠짐이 잘 되고 있다」 → 배수 좋음 · 「종구생산을 위한 목적이다」 → 용도 종구 생산 · 넣기는 사람)",
            "채팅으로 말한 용도는 처음부터 밭 정보 카드가 됩니다 · 종류를 고른 뒤에는 「종류를 고르셨습니다 — 처음 제안은 지웠습니다」 가 뜹니다 · 「왜 되묻는가」 는 고쳐 달라는 말로 들어갑니다",
            "「밭 정보 메뉴를 찾지 못함」 → 화면 이름을 한 목록으로(왼쪽 메뉴 「밭 정보 · 설정」 · 구역 「밭 정보」 · 없는 이름은 요구 문장·보고에 못 들어옵니다) · 「이 메뉴가 작목마다」 → 채팅 목록의 각 작목(쪽파 · 대파) 아래 그 작목으로 좁힌 판단 · 일지 · 한 일 · 영상 · 고쳐 달라는 말 · 몰 한 줄 · 대파(재배 달력 없음)의 판단은 「누가 · 어디서(발행자 — 달력 만들기)」 를 함께 말하고 「재배 달력가」 같은 조사 어긋남이 멎었습니다"],
    "gate": "1277 → 1327 · 주입 10/10 · 8/8 · 7/7 · 7/7 · 7/7 + 걷기 2",
    "blocked": "종구 두 칸 값(D-24) · §10 표 24행 중 뒤집을 행 · 대파 재배 달력(세션에 「작목 · 작기 달력」 요청 한 줄이면 자리를 만듭니다 — 값은 지식) — 셋 다 발행자 몫. 배수 기준 문면(§7)은 급하지 않습니다.",
}
BEST_MAX_LINES = 10
BEST_CUMULATIVE_WORDS = ("앞 회차", "어제", "그 회차", "전 회차")      # 누적 보고의 표지 — 어디에도 못 들어온다. 앞 회차는 핸드오버 §1 표 몫


def render_best(b: dict) -> str:
    """발행자 형식 그대로 — 열 줄 안쪽의 <pre>. 한 줄이 한 뜻."""
    d = b["do"]
    did = list(b["did"]) or ["(한 것이 비었다)"]
    did[-1] = f"{did[-1]} (관문 {b['gate']})"
    lines = [f"최선의 다음 한 수 ({b['date']} · {head})", "",
             f"발행자가 할 것 — 하나: {d['what']}.",
             f"  어디서: {d['where']} · 왜 지금: {d['why_now']}",
             f"  안 하면: {d['if_not']}", "",
             f"세션이 한 것 — {did[0]}"] + [f"  {x}" for x in did[1:]]
    if b.get("blocked"):
        lines += ["", f"막힌 것 — {b['blocked']}"]
    return "\n".join(lines)


def check_best(b: dict) -> list[str]:
    """형식 래칫 — 하나 · 세 줄 안 · 열 줄 안쪽(빈 줄 제외) · 누적 어휘 없음 · 해시 하나까지."""
    bad = []
    d = b.get("do") or {}
    for k in ("what", "where", "why_now", "if_not"):
        if not str(d.get(k, "")).strip():
            bad.append(f"할 것 — {k} 가 비었다(무엇을 · 어디서 · 왜 지금 · 안 하면 넷이 한 줄씩)")
    if not (1 <= len(b.get("did") or []) <= 3):
        bad.append("세션이 한 것은 1~3줄")
    body = render_best(b)
    n = len([ln for ln in body.splitlines() if ln.strip()])
    if n > BEST_MAX_LINES:
        bad.append(f"열 줄 안쪽이어야 한다 — {n}줄")
    for w in BEST_CUMULATIVE_WORDS:
        if w in body:
            bad.append(f"누적 표지 {w!r} — 앞 회차는 핸드오버에")
    if len(set(re.findall(r"\b[0-9a-f]{7}\b", body))) > 1:
        bad.append("U-19: 회차(커밋) 해시가 둘 이상")
    # [발행자 §2 둘째 측정 2026-10-04 "밭 정보 메뉴를 찾지 못함"] 「어디서」 에 「…」 로 감싼 이름은 화면 이름 계약(schema.labels)에 있어야 한다 — 없는 메뉴가 보고에 나가지 않게
    from schema import labels as _labels
    for q in _labels.unknown_quoted(str(d.get("where", ""))):
        bad.append(f"어디서의 「{q}」 는 화면에 없는 이름 — schema.labels 의 메뉴·구역 이름만")
    return bad


assert not check_best(BEST), check_best(BEST)


def check_retired(items) -> list[str]:
    """[발행자 §2 둘째 측정 2026-10-04] 발행자 몫·세션 몫 두 목록에 물러난 화면 이름(schema.labels.RETIRED)이 다시 들어오면 생성기가 멈춘다 — 보고가 없는 메뉴를 가리키지 않게."""
    from schema import labels as _labels
    bad = []
    for k, v in items:
        for r in _labels.retired_in(k + " " + v):
            bad.append(f"{k[:30]}…: 물러난 화면 이름 {r!r}")
    return bad


assert not check_retired(NEXT_PUBLISHER + NEXT_SESSION), check_retired(NEXT_PUBLISHER + NEXT_SESSION)

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
.best pre {{ margin:0; white-space:pre-wrap; font:inherit; line-height:1.5; }}
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
  <pre>{html.escape(render_best(BEST))}</pre>
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
