# 코드 평가 — 정합성 · 논리성 · 합리성 (2026-09-19, HEAD 522e7b7)

**무엇을 지키려는가**: 지금 있는 코드가 문서(계약)와 서로(호출)와 맞는가(정합), 틀린 출력을 내는 경로가 있는가(논리),
결함이 조용히 지나가는 자리가 있는가(합리). 등급은 파일 단위, 발견은 심각도순. 근거는 파일:줄이고 **전부 이 세션에서
읽기 전용 실행으로 재확인한 것만** 실었다(리뷰어 인용 줄 번호가 파일 길이를 넘는 경우가 있어 앵커를 다시 잡았다).

측정 시점 2026-09-19 오후 · 대상 소스 45파일 7,246줄 · 검사 35파일 3,687줄 · 관문 421 passed.
방법: 영역 4(스키마·판정 핵 / 결정 / 반입 / 화면·몰·스크립트)를 각각 전수 정독 + 가설은 읽기 전용 실행으로 검증,
횡단 측정 4(소비자 0 · except 삼킴 · 판정 임계 리터럴 · 검사 규율)는 도구로 셌다. 리뷰어 발견 95건 중 상 6 · 중 대표를
재실행으로 확인했고, 확인 못 한 것은 "미확인"으로 표기했다.

## 0. 총평

**정합 중간 · 논리 중간 · 합리 높음.** 층 구조·봉투 8종·경계 게이트·되먹임 보수 원칙 같은 **뼈대는 문서와 코드가 맞고**
검사가 그것을 지킨다(M-5 관문 · 421). 결함은 뼈대가 아니라 **관절**에 있다 — 게이트가 필드를 안 보고, 되먹임이 예측이
없는 날에도 빗나감을 적고, 결정기 둘이 같은 작업을 다르게 판정하고, 대리값 하나(재배환경=노지)가 정본 저장소로 들어간다.
**상 6건**은 전부 *"조용히 틀린 값이 정본이나 봉투로 흐른다"* 형태이고 그중 하나(PSIS 파→쪽파 대체 인용)는 법규 축이다.

한 줄 판정: **첫 수확 전에 상 6건을 닫으면 쪽파 한 작기를 믿고 돌릴 수 있다.** 중 이하는 두 번째 작목·두 번째 필지가
생길 때 갈라지는 것들이라 등재 뒤 회수 순서로 간다.

## 1. 횡단 측정 (도구 — 2026-09-19)

### 1-1. 소비자 0 (G1 계열 — 정본이 있는데 안 흐른다)

도구 첫 판 37건 → 대부분 자기 파일 안 참조(라우터가 부르는 페이지 함수 — 도구 오측정). 자기 파일에서도 참조 0 인 **진짜 고아 4건**:

| 위치 | 무엇 | 판정 |
|---|---|---|
| `schema/records.py:255` `public_fields()` | kind 별 `pii` 선언에서 공개 필드를 뺀다 | **중 · 정합** — 스키마가 PII 를 kind 별로 선언하는데 소비자가 문서 생성기뿐. 실제 PII 제거는 `ingest/parcels.py:31`(전역 `PII_FIELDS`)과 `ingest/media.py:412`(`gps` 손코딩) **두 벌**. 오늘은 셋이 같으나 kind 에 PII 필드를 더 선언하면 화면은 모른다 |
| `ingest/kma.py:171` `fetch_normals()` | 평년값(`reference.climate_normal`) 수집 | **중 · 정합** — 스키마·kind·수집기가 있는데 부르는 곳이 없다. "안 하기로 한 것"인지 "빠뜨린 것"인지 문서가 없다(검사 규율: 미배선 결정은 검사로 고정) |
| `judge/run.py:49` `all_harvest()` | 수확기만 도는 옛 진입점 | **중 · 정합** — 사문이면서 **게이트 우회 경로**(필지 병합·`boundary.gate`·`apply_caps` 없이 판정). 게이트 위치 래칫은 `all_judgments` 만 본다 |
| `frontend/render.py:32` `render_doc()` | 파일→HTML | **하 · 합리** — 사문 |

### 1-2. except 삼킴 (fail-open)

14곳, **전부 예외 형을 특정**, bare `except:` 0. 둘만 기록:

| 위치 | 무엇 | 판정 |
|---|---|---|
| `ingest/soil_store.py:61` | 처방 파일이 깨지면 `continue` | **중 · 논리** — 깨진 처방은 조용히 사라지고 밑거름·웃거름이 "처방 없음"으로 간다. 파일이 있는데 없다고 말하는 셈 |
| `ingest/psis.py:158` | 깨진 캐시 → `pass` → 재조회 | **하 · 합리** — 동작은 옳다. 매번 깨져 있으면 매 조회가 API 를 때리는데 아무도 모른다 |

### 1-3. 판정 임계 리터럴 — 1건(`stage_decisions.py:317` `store_days <= 0`, 경계 판정). 임계는 전부 registry params. **합리 높음.**

### 1-4. 검사 규율 — 문자 창 고정 0 · 인자 리터럴 고정 0 · 운영 경로는 격리 검사 안에서만 · VELA 참조는 키 이식 스크립트뿐. 소스 텍스트 래칫 14파일 전부 블록 단위. **준수.**

## 2. 영역별 발견 (심각도순 · ✔ = 이 세션 재실행 확인)

### 2-1. 스키마 · 판정 핵 (schema/records · judge/boundary · run · envelope · registry · evolve · grid/schema)

| # | 급 | 축 | 위치 | 결함 | 근거 · 검증 |
|---|---|---|---|---|---|
| A1 | **상** | 논리 | `judge/evolve.py:132` | 피해 날을 창에 품는 예측이 없어도 `or preds` 폴백으로 **아무 예측**(뒤에 만든 것 포함)에 "놓친 경보" 빗나감을 적는다 → `propose()` 자동 등급 상한의 근거 오염 | ✔ 예측 9/10 · 피해 9/1 → `빗나감 "앞선 경보 없음"` 기록. m6 §7 "예측이 없으면 아무것도 적지 않는다" 위반 |
| A2 | **상** | 논리 | `judge/evolve.py:109` + `ingest/feedback.py` 예측 원장 | 예측 창 = **첫 줄** `observed_at`+horizon. 원장은 payload 가 바뀔 때만 한 줄이라 같은 경보가 매일 살아 있어도 창은 첫 발행일+7 에서 끝난다 → 그 뒤 피해는 "앞선 경보 없음"+"창 안 피해 없음" 둘 다 기록 | ✔ `_pred_window` = (9/10, 9/17). 제안: 예측 줄에 `last_seen_at` 갱신 |
| A3 | 중 | 정합 | `judge/boundary.py:54` | `gate_records` 가 kind·source·`values` 안 금지어만 보고 **레코드 필드 허용 목록을 안 본다**(파일 머리 "선언되지 않은 필드는 거부" 와 어긋남). kma·ncpms 레코드는 `sch.validate` 를 한 번도 안 거치므로 이 게이트가 유일한 방어 | ✔ `{"kind":"event","source":"farmer","stock":5,"unit_price":100}` 통과 |
| A4 | 중 | 논리 | `judge/registry.py:65` | 격자 칸 `required_axes="N/A"`(문자열, grid/schema 허용)를 set 으로 만들어 **글자 단위**('N','/','A')로 돈다 → 판단 불가(지식) detail 오염 | ✔ `check_against_grid` → `'/'`, `'N'` |
| A5 | 중 | 논리 | `grid/schema.py:108` | `recoverable` 을 존재만 보고 bool 검사 안 함. `"false"` 문자열이 통과하고 risk_alert 는 `is False` 비교라 **회복 가능**으로 읽어 경보 비대칭이 무너진다 | ✔ 실제 격자에 `"false"` 주입 → validate 오류 0 |
| A6 | 중 | 합리 | `judge/run.py:97` | `all_judgments` 가 4층에 **게이트 통과 후 subject(lat·lon·soil_chem 값)** 를 그대로 돌려준다. I-5 "원본 값·좌표는 4층에 안 나간다"가 호출 규약이 아니라 호출자의 절제에 걸려 있다(serve.py 는 label 만 쓴다) | 코드 대조 |
| A7 | 중 | 정합 | `grid/schema.py:102` ↔ `judge/plan.py` · `grid/capture.py` · `harvest_timing.py:83` | 스키마는 `window.basis in ("anchor","gdd")` 를 허용하지만 소비자 전부가 from/to_day 를 **기준일+일수**로만 읽는다. gdd 칸이 들어오는 순간 조용히 틀린 날짜 | 코드 대조(현재 데이터 전부 anchor) |
| A8 | 중 | 논리 | `judge/registry.py:50` | 같은 id 로 `register` 하면 조용히 덮어쓴다. `answers_policy` 어휘 검사 없음 | 코드 대조 |
| A9 | 중 | 정합 | `judge/envelope.py:43` | `result`·`caps` 가 자유 dict 라 "1·2층 값을 싣지 않는다"를 구조로 못 막는다(risk_alert `signals` 의 rain_mm 합, harvest `basis` 문자열의 tmin 이 봉투에 실림) | 코드 대조 — M-5 관문은 금지 **키**만 본다 |
| A10 | 하 | 논리 | `judge/evolve.py:136` | 과경보 판정은 `preds[-1]` 만 본다 — 앞선 예측은 창이 지나도 영원히 미판정 | 코드 대조 |
| A11 | 하 | 정합 | `judge/run.py:24` | `gather_pest` 가 `today` 를 안 받고 `date.today().year` — 재현·과거 판정 시 연도 불일치 | 코드 대조 |
| A12 | 하 | 정합 | `schema/records.py:174` | `SUBJECT_STATUS` 어휘를 `_validate_vocab` 이 안 본다(subjects.py 만 검사 — 파일 직접 편집은 통과) | 코드 대조 |
| A13 | 하 | 합리 | 여러 곳 | 중복 진실: `DAMAGE_TYPE="피해"` 2벌(events·evolve) · `"cultivation_unit"` 리터럴 10곳+ · 단계 표기 f-string 4곳 · 파일명 규칙 `replace('-','_')` 2벌 · 허용 오차 키(`"error_days"` 리터럴 vs `HARVEST_TOLERANCE_DAYS_KEY`) | grep |
| A14 | 하 | 논리 | `judge/envelope.py:18` | `weakest([])` 가 `"추정"` 을 돌려준다(대리값) | ✔ |

### 2-2. 결정 (harvest_timing · risk_alert · stage_decisions · plan_vs_actual · material_citation · 격자 데이터)

| # | 급 | 축 | 위치 | 결함 | 근거 · 검증 |
|---|---|---|---|---|---|
| B1 | **상** | 논리 | `judge/risk_alert.py` 수확 지연 합성(:31 규칙 · 말미 합성 블록) | 수확 창을 넘기면 **수확 사건이 있어도** `경보 수확 지연` 이 영구히 나간다 — `judge()` 가 사건 원장을 안 받아 수확 여부를 볼 길이 없음 | ✔ day 100 · 200 모두 `[('경보','수확 지연')]`, revisit 매일 |
| B2 | 중 | 논리 | `judge/stage_decisions.py:173` | `cert` 가 필요 축인데 없으면 `mats.get(cert, [])` 로 조용히 빈 자재 → **판단함** "자재(None) 없음" (필요 축 부재가 데이터 미비로 안 나온다 — fail-open) | ✔ cert 뺀 subject → top_dressing_1 판단함 |
| B3 | 중 | 논리 | `judge/stage_decisions.py`(웃거름 이행 블록) vs `judge/plan_vs_actual.py:_matched_event` | 같은 작업 '웃거름 1회' 이행 판정이 **두 벌**(허용 폭 7 하드코딩 vs params tol 3) | ✔ 시비 사건 day 17 · today 25 → top_dressing_1 `이행` / plan_vs_actual `미이행` |
| B4 | 중 | 정합 | `data/grid/jjokpa_autumn.json` 칸 경계 | 칸 경계일이 겹친다(10·30·50·70 이 두 칸에 속함). `stage_for_day(30)`=칸 3, risk_alert day 30 은 칸 3·4 둘 다 열림, material_citation 은 칸 3 만 — 같은 날 "오늘 칸"이 판정기마다 다르다 | 리뷰어 실측(미재확인) — M-5 §2 밖 |
| B5 | 중 | 논리 | `judge/stage_decisions.py` top_dressing_2 | `판단 불가(지식)` 반환이 창 지남 검사 **앞**에 있어 시즌 내내 지식 미비로 남는다(I-1 §3 순서 역전) | 리뷰어 실측 day 60 |
| B6 | 중 | 논리 | `judge/stage_decisions.py` ship_or_store + 격자 | 출하 마감 day 63 < 수확 창 끝 day 70 — 격자 자체 모순. target day 65 → "출하(저장 없이)" 와 caps '단기 저장 한계' 동시 | 리뷰어 실측 |
| B7 | 중 | 정합 | `judge/stage_decisions.py:298` · `schema/records.py` | `mall_supply is False` 분기는 라이브 경로에서 **도달 불가**(`PARCEL_FIELDS_TO_LAYER3` 에 없어 subject 에 None). D-8 판정은 `use` 문자열만으로 성립 | 코드 대조 |
| B8 | 중 | 정합 | `judge/risk_alert.py:199` vs registry 등록 | 등록 `optional_axes` 에 없는 `pest_regional` 을 봉투 inputs 에 싣는다 | 코드 대조 |
| B9 | 중 | 논리 | `judge/risk_alert.py:82` | `wet_run` 이 연속 **일**이 아니라 연속 **레코드**를 센다(for_day 연속성 검사 없음) → 노균병 경보 오발 가능 | 리뷰어 실측(+1, +4 → run 3) |
| B10 | 중 | 정합 | `judge/harvest_timing.py:62` | `w == NA`(해당 없음)와 키 부재(미채움)를 둘 다 판단 불가(지식)으로 합친다 — M-4 §3 와 다름 | 코드 대조 |
| B11 | 중 | 정합 | `judge/harvest_timing.py:79` (+3곳) | 등급을 unit 확신만 보고 정하고 **칸 confidence** 를 무시(M-4 §2 "칸 우선") | 코드 대조 |
| B12 | 중 | 정합 | `judge/stage_decisions.py` missing 항목 | `missing` 에 I-4 축이 아닌 이름(`observation`, `plan.target_date`) 또는 틀린 축(anchor 가 있는데 anchor) — 봉투 §2-4 계약 위반, 4층이 축으로 해석 못 함 | 리뷰어 실측 |
| B13 | 중 | 논리 | `judge/plan_vs_actual.py` | 조건부 작업("관수(건조 시)"·"웃거름 2회(필요 시)")과 기준점 이전 촬영을 무조건 `놓침`으로 세고 사유를 묻는다 | ✔ T+25 실산출 놓침 5 에 관수(건조 시)·칸1 촬영 포함 |
| B14 | 하 | 합리 | risk_alert · psis · evolve | 격자 위험명→병해충 대응표 **세 벌** | grep |
| B15 | 하 | 합리 | `judge/stage_decisions.py:221` | `_delegate_risk` 가 risk_alert 를 재호출 — 재배 단위당 3회 실행 | 코드 대조 |
| B16 | 하 | 합리 | `judge/stage_decisions.py` 출하 | 마감 63 을 코드에 복제 — 작업명이 바뀌면 63 을 지어낸다 | 코드 대조 |
| B17 | 하 | 논리 | `judge/harvest_timing.py:102-104` | `end + timedelta(days=0)` 사문 · `if forecast:` 중첩 | 코드 대조 |

### 2-3. 반입 (ingest/* · names/*)

| # | 급 | 축 | 위치 | 결함 | 근거 · 검증 |
|---|---|---|---|---|---|
| C1 | **상** | 정합 | `ingest/organic_materials.py:89` `search()` → `judge/material_citation.py:145` | 공시 자재 검색 항목에 **금지 필드 `price`** 를 넣고, 인용 판정기가 `i["values"]` 를 게이트 없이 봉투 result 에 그대로 싣는다 → 스키마가 금지한 값이 4층에 도달 | ✔ p001 material_citation 봉투 JSON 에 `"price"` 존재 |
| C2 | **상** | 논리 | `ingest/fertilizer.py:40,50` | 재배환경 미상이면 `DEFAULT_ENV="노지"` 로 메워 작물코드(07027)를 고른다 → 시설 필지에 노지 처방이 **정본 저장소**에 저장. 헌법 "fallback 대표값 강제 금지 — 수령 불명 시 되묻기" 위반 | ✔ `crop_code("쪽파","FrtlzrUse",None)` → 07027 |
| C3 | **상** | 논리 | `ingest/psis.py:42,168` → `judge/material_citation.py:100` | 쪽파 등록약제 0건이면 **`파`** 를 조회해 `crop="쪽파"` 레코드로 저장·인용. 인용문은 "등록 = 그 작물에 쓸 수 있음(PLS)" 으로 단정 → 농약 등록은 작물별(PLS)이라 **안전·법규 축**. `queried_as` 만 싣고 표기에서 대체임을 강제하지 않는다 | ✔ 코드 대조. **발행자 확인 대상** |
| C4 | 중 | 정합 | `ingest/parcels.py:17` | 등록부 경로를 **기본 인자에 import 시점으로** 묶는다 — R-4 위반(오늘 R-4 처방을 등록부 넷에 전수 적용했는데 필지가 빠졌다). conftest 에 `AGRODSS_PARCELS_PATH` 없음 | ✔ grep |
| C5 | 중 | 논리 | `ingest/chat.py:63` | 위험 경보 주제어 `"얼"`·`"습"` 과매칭 — "물을 **얼**마나 줘야 하나요" · "괜찮**습**니까" 가 risk_alert 로 답해진다 | 리뷰어 실측 → **말뭉치에 등재해 고친다**(M-13 정본 경로) |
| C6 | 중 | 논리 | `ingest/chat.py:154` | 월/일 표기를 항상 **올해**로 해석 → 1월에 "12월 20일에 심었다" 가 미래 사건 | ✔ 코드 대조 |
| C7 | 중 | 논리 | `ingest/chat.py:374` `confirm` + `frontend/serve.py` | 재확인 방지 없음(`confirmed_refs` 가 있어도 다시 사건을 쓴다) → 브라우저 POST 재전송이 그대로 중복 원장 | 코드 대조 |
| C8 | 중 | 논리 | `ingest/media.py:388` | 파일을 inbox 에서 **옮긴 뒤** stamp — stamp 실패 시 파일은 옮겨졌는데 원장 줄이 없다(고아) | 코드 대조 |
| C9 | 중 | 논리 | `ingest/media.py:149` | mvhd 페이로드가 잘린 파일이면 `buf[a]` IndexError 가 try 밖 → `list_inbox` 전체가 죽어 /media 가 500 | 리뷰어 실측 |
| C10 | 중 | 논리 | `ingest/kma.py:250` | 예보값이 `""` 이면 `float()` 이 안 잡혀 그날 예보 전부를 잃는다 | 리뷰어 실측 |
| C11 | 중 | 정합 | `ingest/kma.py:33` · `ncpms.py:26` · `config.py:56` | 같은 env `AGRODSS_INGEST_TIMEOUT_SEC` 를 기본값 **15/20/30** 세 벌로 읽는다. 셋 중 kma·ncpms·organic 은 `ingest.config` 를 import 하지 않아 **`.env` 도 안 실린다**(오늘 d9e2a01 처방이 세 모듈에 안 닿았다 — §7.5 지점 축) | ✔ grep |
| C12 | 중 | 정합 | `ingest/ncpms.py:112` | 관측일 없는 예찰 item 을 `observed_at=None` 으로 레코드화(soil_exam 은 같은 경우 error — 원천마다 규율이 다르다) | 코드 대조 |
| C13 | 중 | 논리 | `ingest/events.py:129` | `add_noncompliance` 만 `planned_day` 를 `_need_day` 로 검증하지 않는다 | 코드 대조 |
| C14 | 중 | 정합 | `ingest/profile.py:33` | 등록부 없으면 `recorded_at:""` 대리 레코드를 만들어 돌려준다(검증 통과) | 코드 대조 |
| C15 | 하 | 논리 | `ingest/chat.py:45` `"잘못"`·`"안 맞"` | "잘못 심어서 다시 심었다" 가 개선 요구 — 말뭉치 등재 대상 | 리뷰어 실측 |
| C16 | 하 | 정합 | events · media | 값 없는 `None` 키를 항상 쓴다(스키마 §"없는 값은 키 부재") · `recorded_at` 시계가 원장별 로컬/UTC 두 벌 · `axis` 필드 타입이 원천마다 str/list | grep |
| C17 | 하 | 합리 | JSONL append 전반 | 잠금 없음 — 화면 서버 + live_reproduce 3프로세스 + CLI 가 같은 파일에 쓴다. 지금은 등재(구조적 위험 2칸) | 코드 대조 |

### 2-4. 화면 · 몰 · 스크립트 (frontend/* · mall/* · scripts/* · 배치 · 훅)

| # | 급 | 축 | 위치 | 결함 | 근거 · 검증 |
|---|---|---|---|---|---|
| D1 | **상** | 정합 | `data/parcels.json`(git 추적) · `scripts/live_check.bat` · `docs/d1_first_farm.md` · `docs/m10_harvest_timing.md` · tests 4 | 필지 **주소(지번)** 가 저장소에 리터럴로 들어 있다. 스키마가 `address` 를 PII 로 선언하고 화면·몰은 그것을 지우는데 **저장소 자체가 값을 들고 있다**(원격 push 됨). 발행자 본인 필지라도 프로젝트 규칙상 PII | ✔ `git grep 갈금리` 9파일. **등재·처방 여부는 발행자 판단**(본인 정보). 처방 형태: 등록부 값은 gitignore 된 `data/soil/` 또는 `.env` 로, 배치·문서·검사는 자리표시자 |
| D2 | 중 | 정합 | `frontend/config.py:22` ↔ `ingest/config.py:27` ↔ `scripts/env_from_vela.py` | dotenv 로더 **두 벌**이 빈 값을 다르게 다룬다(frontend 는 `KEY=` 빈 값도 환경에 넣음, ingest 는 건너뜀). env_from_vela 는 `.env.example` 의 빈 `KEY=` 줄을 두고 **끝에 덧붙이므로** 화면 프로세스(frontend 먼저 import)는 키 없음, live_reproduce 는 키 있음으로 갈린다 — 발행자가 오늘 밟을 바로 그 경로 | ✔ 두 로더 코드 대조. 리뷰어가 merge 시뮬레이션으로 확인 |
| D3 | 중 | 논리 | `frontend/chat_pages.py`(사이드바 기준점 일수) · `mall/product.py` | `anchor` 형식을 아무도 검증하지 않아(스키마 통과) 비ISO 값 하나가 `date.fromisoformat` 으로 **모든 셸 화면**을 죽인다. UI 에서 복구 불가 | ✔ `validate(anchor="2026-9-20")` 통과 · `fromisoformat` ValueError |
| D4 | 중 | 논리 | `frontend/serve.py` do_GET/do_POST | 총괄 예외 처리가 없어 미처리 예외는 응답 없이 연결이 끊긴다(Content-Length 비정수 · `/improve/cycle` · NUL 경로) — D3 가 "무응답"이 되는 이유 | 코드 대조 |
| D5 | 중 | 논리 | `frontend/serve.py` 업로드 | 상한 초과 본문을 **잘라 읽고** 잘린 multipart 를 그대로 등록(413 없음) → 불완전 파일이 1층 관찰로 | 리뷰어 실측(600B 로 자른 파트가 등록 경로로 흐름) |
| D6 | 중 | 논리 | `frontend/serve.py` POST | Origin/Host 검사 없음 — 루프백 기본은 토큰도 쿠키도 없어 브라우저에 열린 아무 사이트가 폼 POST 로 원장을 쓸 수 있다(CSRF · DNS 리바인딩). LAN 모드만 SameSite | ✔ grep Origin/Host/Referer 0 |
| D7 | 중 | 논리 | `mall/product.py:33` `cert_label` | 필지 불리언 `cert_legal` 만 참이면 **농가 주장 유형**을 "인증(인증서 확인)" 으로 표기 — 인증서에 적힌 유형과 무관. **안전·법규 축 — 발행자 확인** | 리뷰어 실측 `cert_legal=True, cert=무농약` → "무농약 인증(인증서 확인)" |
| D8 | 중 | 논리 | `scripts/hook_block_shell_authoring.py:36` INLINE | `py -3 -c` · `/usr/bin/python3 -c` · `python -X utf8 -c` 를 **못 본다**(옵션 토큰·경로 lookbehind) — 배치가 고르는 바로 그 호출형 | ✔ 둘 다 PASS |
| D9 | 중 | 논리 | 훅 heredoc 분기 | 리다이렉트·tee 를 heredoc 과 **같은 줄**에서만 본다 — `{ cat <<EOF … } > out.txt` 통과 | ✔ PASS |
| D10 | 중 | 합리 | 훅 WRITERS | `sys.stdout.write` · `json.dump(…, sys.stdout)` 를 쓰기로 막는다(과잉 차단 — CLAUDE.md 가 경고한 "가드를 끄게 만드는" 형태) · `open("a…")` 처럼 파일명이 a/w/x 로 시작하면 읽기 열기를 쓰기로 오판 | ✔ stdout.write DENY. open 오판은 정규식 판독(`[^)]*` 가 비어 따옴표 뒤 첫 글자를 모드로 읽음) |
| D11 | 중 | 논리 | `scripts/live_check.bat` | UTF-8(BOM 없음) 배치의 한글 인자를 cmd 가 cp949 로 해석 → 주소·`--crop=쪽파` 가 깨져 토양·처방 단계가 **항상 실패** · `( … ) > log` 블록 안 `%errorlevel%` 은 블록 이전 값이라 라이브 3/3 결과가 로그에 틀리게 찍힌다 | 리뷰어 판독(cmd 규칙). 발행자가 오늘 밟을 경로 — D2 와 함께 **최우선** |
| D12 | 중 | 정합 | `scripts/build_crop_axes_doc.py` | "생성물"이라면서 손으로 박은 수치(버섯 12 · 180종)가 정본 CSV(버섯 8 · 202종)와 어긋난다 | ✔ CSV 집계 |
| D13 | 하 | 합리 | `frontend/serve.py:nav_html` ↔ `chat_pages.sidebar` | 좌측 내비 **두 벌** — 표 화면에 개선·몰·새 채팅 링크 없음 · 결정 라벨 사전 두 벌 | 코드 대조 |
| D14 | 하 | 논리 | `frontend/render.py:100` | `<title>` 미이스케이프(입력이 상수라 실해 없음) · 토큰 비교 접두 일치·쿠키 미파싱 · ACTION_JS 음성 타이머 재할당 시 이전 것 미해제 | 코드 대조 |
| D15 | 하 | 정합 | `frontend/chat_pages.py` mic title | "5초" 하드코딩(설정 `VOICE_SILENCE_MS` 와 별개) · `/me` 동기화 상태 문구가 토큰만 있는 경우를 안 가른다 · 401 화면은 nav 없음(의도 — 문서화 필요) | 코드 대조 |
| D16 | 하 | 합리 | `.claude/settings.json` | `python scripts/…` 상대 호출 — Windows Store 별칭 스텁이면 훅이 비차단 오류로 끝나 가드가 조용히 꺼진다(가드 창과 같은 결) | 코드 대조 |
| D17 | 하 | 합리 | `docs/render_backlog.py` · `scripts/diag_frontend.bat` | argv 무검사 · "read-only" 표기인데 포트 바인드 | 코드 대조 |

리뷰어가 **확인해 결함 아님**으로 닫은 것: `/doc` 경로 우회 · 업로드 파일명 · GET 원장 쓰기 · 사용자 문자열 이스케이프 · conftest 격리 범위 · 훅 exit 0.

## 3. 파일별 등급 (정합 / 논리 / 합리 — 높음·중간·낮음)

| 파일 | 정합 | 논리 | 합리 | 한 줄 |
|---|---|---|---|---|
| schema/records.py | 높음 | 중간 | 중간 | 허용 목록·출처·어휘가 문서와 일치. `kind=` 불일치 통과 · 사문 `public_fields` · SUBJECT_STATUS 미배선 |
| judge/boundary.py | 중간 | 높음 | 중간 | 게이트 위치·순서는 맞음. 필드 허용 목록을 안 본다(A3) |
| judge/run.py | 중간 | 높음 | 낮음 | 우회 경로 `all_harvest` · 4층에 원본 값 반환(A6) · today 무시 |
| judge/envelope.py | 중간 | 중간 | 높음 | 8종·등급 검사 간결. 값 격리를 구조로 안 막음(A9) |
| judge/registry.py | 높음 | 중간 | 중간 | 축 검사가 grid 와 같은 집합. N/A 문자열(A4) · 무음 덮어쓰기(A8) |
| judge/evolve.py | 중간 | **낮음** | 중간 | 보수만 자동은 잘 지켜짐. 그러나 A1·A2 가 잘못된 빗나감을 만들고 그것이 자동 상한으로 이어진다 |
| grid/schema.py · capture.py | 중간 | 중간 | 높음 | 빈칸 3종 집계 명료. recoverable bool 미검사(A5) · gdd basis 허용이 소비자와 안 맞음(A7) · 경계 겹침 미검사 |
| judge/harvest_timing.py | 중간 | 높음 | 중간 | 판별 순서·창 경계 일관, 실산출 정상. N/A↔미채움 합침 · 칸 확신 무시 |
| judge/risk_alert.py | 중간 | **낮음** | 중간 | 수확 지연 영구 경보(B1) · wet_run 비연속 · 미선언 축 · 대응표 세 벌 |
| judge/stage_decisions.py | 중간 | **낮음** | 중간 | cert fail-open(B2) · 이행 판정 두 벌(B3) · top_dressing_2 순서 · 출하/저장 모순 · 63·7 하드코딩 |
| judge/plan_vs_actual.py | 중간 | 중간 | 높음 | 단일 매처·params 잘 됨(stage_decisions 가 안 쓴다). 조건부·소급 작업을 놓침으로 |
| judge/material_citation.py | 높음 | 중간 | 높음 | 계열 추출·정직한 no_alias. 게이트 없이 `values` 를 싣는다(C1 의 출구) |
| ingest/chat.py | 높음 | 중간 | 중간 | stamp·필드 정확. 주제 과매칭 · 연도 가정 · 재확인 무방비 |
| ingest/events.py · feedback.py | 중간 / 높음 | 중간 / 높음 | 높음 | feedback 은 중복·전이 규율 충실. events 는 noncompliance 날짜 미검증 · None 키 |
| ingest/media.py | 중간 | **낮음** | 중간 | 이동 뒤 stamp(고아) · mvhd IndexError · 시간 기준 혼재 |
| ingest/subjects.py · profile.py · soil_store.py | 높음 / 중간 / 높음 | 중간 / 높음 / 높음 | 중간 / 높음 / 높음 | 기본 필지 p001 · 대리 프로필 레코드 · 깨진 처방 무음 |
| ingest/parcels.py | **낮음** | 높음 | 높음 | R-4 위반(C4) — 오늘 전수 처방에서 빠진 한 곳 |
| ingest/fertilizer.py | 높음 | **낮음** | 중간 | 코드 네임스페이스 분리는 명확. 재배환경 대리값(C2) |
| ingest/soil_exam.py | 높음 | 높음 | 높음 | 검정일 없음 차단 — 원천 규율의 모범 |
| ingest/psis.py | 높음 | **낮음** | 중간 | 파→쪽파 대체 인용(C3) — 법규 축 |
| ingest/kma.py · ncpms.py | 중간 | 중간 | 중간 | `.env` 미적재 · 타임아웃 세 벌(C11) · float 무가드 · observed_at None |
| ingest/organic_materials.py | **낮음** | 중간 | 중간 | price 금지 필드(C1) · import 시점 경로 · prev 경로 불일치 |
| ingest/config.py · names/* | 높음 | 높음 | 중간 / 높음 | config 는 다른 모듈이 안 쓰면 정본이 아니다(C11) |
| frontend/serve.py | 중간 | **낮음** | 중간 | 잘린 업로드 등록(D5) · 무응답 예외(D4) · CSRF(D6) · 내비 두 벌 |
| frontend/chat_pages.py · render.py | 중간 / 높음 | 중간 | 높음 / 중간 | anchor 로 전 화면 사망(D3) · 이스케이프는 일관 · 표 파서 두 벌 |
| frontend/config.py · scripts/env_from_vela.py | **낮음** | 높음 / 중간 | 높음 | 로더 두 벌 불일치가 키를 지운다(D2) |
| mall/product.py | 중간 | 중간 | 높음 | assert_public 재귀 · 명시 키 선택. 인증 유형 표기(D7) |
| scripts/hook_block_shell_authoring.py | 중간 | **낮음** | 중간 | `py -3`·경로 미탐(D8) · 다음 줄 리다이렉트 미탐(D9) · stdout 과잉 차단(D10) |
| scripts/live_check.bat | **낮음** | **낮음** | 중간 | PII 리터럴(D1) · cp949 인코딩 · errorlevel(D11) |
| scripts/live_reproduce.py · migrate_ledgers.py · build_*.py | 높음 | 높음 | 높음 | 3/3·미성립·캐시 의심 규율 그대로. build_crop_axes 만 손수치(D12) |
| tests/conftest.py | 높음 | 높음 | 높음 | env 쓰기 경로 전부 격리 — parcels 만 빠짐(C4) |

## 4. 처방 순서 (등재 문턱 §1 기준 — "지금 안 고치면 사용자에게 무슨 일이 나는가")

> **처방 상태(2026-09-19 같은 날)**: 칸 1 의 ①~⑥ 은 닫혔다 — ① 06484c2 · ②③ 87ef041 · ④ fefd4f1 · ⑤ 071064d · ⑥ 211db2d.
> 칸 2 도 세션 몫은 전부 닫혔다 — ⓐ 관절 정합 3fb88d2 · ⓑ 결정 논리 45c6fb1 · ⓒ 반입 경계 ce63bf8 · ⓓ 화면·훅 61d0ebc.
> 관문 421 → 464, 주입 31/31 적발. 남은 것은 ⑦(발행자 확인: C3 법규 · D7 법규 · D1 PII), 격자 지식 둘(B4 칸 경계 겹침 · B6 출하 마감<수확 창 끝 —
> 검토지 회신과 함께), 칸 3 하 급이다.
> 처방 중 드러난 것: C1 의 마지막 소비자는 화면(/judge 가 `i['price']` 렌더)이었고 관문이 그것을 3 failed 로 잡았다. D12 의 손수치(버섯류 12)는
> 재측정하니 맞았다(범위 버섯 8 + 채취 4) — 리뷰어가 범위 열만 본 오독. 그래도 생성물 안 손수치는 계산으로 바꿨다(다음 갱신에 어긋난다).

### 칸 1 — 안전 · 실사용 직격 (즉시 등재 제안 · 이번 주)

| 순서 | 항목 | 왜 먼저인가 | 처방 크기 |
|---|---|---|---|
| 1 | **D2 + D11** 로더 두 벌 · 배치 인코딩 · errorlevel | 발행자가 **오늘** 밟을 `live_check.bat` 경로가 키를 지우고 처방 단계를 항상 실패시키며 로그 수치를 틀리게 찍는다 | 로더 통일 1파일 · 배치 ASCII 화 · 주소를 `.env` 로(D1 과 함께) |
| 2 | **C2** 재배환경 대리값 | 정본 저장소에 틀린 처방이 들어간다. 헌법 위반 | `CodeError` 로 되묻기 — 3줄 |
| 3 | **C1** price 금지 필드 | 스키마가 이미 거부하는 값이 봉투·화면에 도달. 되돌리기 쉽고 래칫 한 줄 | 키 삭제 + `material_citation` 출구에 `sch.validate` |
| 4 | **A1 + A2** 되먹임 폴백 · 예측 창 | 자동 등급 하향(자율진화)의 **근거를 오염**한다 — 수확 뒤 첫 되먹임이 돌기 전에 | `or preds` 제거 · `last_seen_at` 갱신 |
| 5 | **B1** 수확 지연 영구 경보 | 수확 뒤 시즌 끝까지 매일 경보 — 첫 수확(10/14~) 전에 | `judge()` 에 수확 사건/status 전달 |
| 6 | **D3 + D4** anchor 검증 · 총괄 예외 | 값 하나가 화면 전체를 무응답으로 | `subjects.add` 검증 + 스키마 날짜 형식 + 500 페이지 |
| 7 | **C3** PSIS 파→쪽파 대체 인용 · **D7** 인증 유형 표기 · **D1** 주소 | **발행자 확인 대상**(법규 · PII). 세션은 `status="proxy"` 표기 강제와 자리표시자화까지 준비할 수 있다 | 발행자 결정 뒤 |

### 칸 2 — 구조적 위험 (등재 + 회수 대기 · 두 번째 작목·필지 전)

A3 게이트 필드 검사 · A4 N/A · A5 recoverable bool · A7 gdd basis · B2 cert fail-open · B3 이행 판정 통일 · B4 칸 경계 · B5/B6 순서·모순 ·
B7 mall_supply 배선 · C4 parcels R-4 · C6~C10 chat/media/kma 경계 · C11 config 정본 · D5 413 · D6 Origin 검사 · D8~D10 훅 보강 · D12 손수치.

### 칸 3 — 등재하지 않음 (핸드오버 부록)

하 급 전부(A10~A14 · B14~B17 · C15~C17 · D13~D17) · 사문 4건(§1-1) · 중복 진실 목록. 다음 리팩터 때 함께.

### 이 평가가 보지 않은 것

- **라이브 동작**(음성 5초 · EXIF · 실제 API 응답) — 코드와 문서의 대조이지 실행 확인이 아니다. 라이브 3/3 이 그 몫이다.
- **격자 지식의 옳고 그름** — 칸 값(창 · 임계 · 위험)이 농학적으로 맞는지는 검토지(review_jjokpa) 회신의 몫. 여기서는 격자 **자체 모순**(B4·B6)만 봤다.
- **성능** — 재배 단위 1 · 레코드 수십 건 규모라 측정하지 않았다. 다만 A6 의 원본 값 반환과 C17 의 잠금 없음은 규모가 커질 때 먼저 갈라진다.
