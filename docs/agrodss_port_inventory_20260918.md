# agrodss 신축 — VELA 1층 자산 이식 목록 (결합도 실측)

> **폐기 (2026-09-18, 같은 날 발행자 결정): "이식하지 않고, 새로 한다."**
> §5 이식 순서 · §1 등급 처리는 무효다. 남는 용도는 둘뿐이다 — ①§2·§4 의 **외부 API
> 원천과 키 이름 목록**(무엇이 있는지의 사전) ②§6 "가져가지 말아야 할 것"(새로 쓸 때도
> 같은 결함을 재현하지 않기 위한 기록). 파일 단위 등급은 읽지 않는다.
>
> **부분 복권 (2026-09-18, D-9): "외부 API 는 LLM 을 제외하고 모두 d:\vela 에서 인용."**
> §2 의 표는 **인용 대상 목록**으로 다시 유효하다 — 단 1층 클라이언트(A·B 등급)만이고,
> C 등급(3층 판단 · 2층 파생 엔진)과 LLM 은 여전히 제외. 인용은 복사가 아니라 다시 쓰기다:
> `ingest/` 에 표준 라이브러리로, 원본 경로·버전을 머리에 적고, 1층 3요건을 붙인다.
> 첫 사례: `ingest/soil_exam.py` ← `location_to_soil.py` L2.1.0. 나머지는 **축이 필요로 할
> 때 하나씩**(대장 M-15).

작성 2026-09-18. 발행자 결정: agrodss 는 **별도 위치(`d:\agrodss`)에 신축**한다.
그러면 `design_tree_review_20260918.md` 의 "저장소 연동 있음" 열은 *"이미 됐다"* 가
아니라 **이식 후보 자산 목록**이 된다. 이 문서는 그 후보를 파일 단위로 재어 *그대로
복사할 수 있는 것*과 *VELA 내부에 얽힌 것*을 가른다.

측정 방법(2026-09-18, `backend_new/` HEAD 9570634): 파일별 줄 수 · `backend_new.*`
내부 import · 참조하는 설정 키 이름. **키 값은 어디에도 적지 않는다**(SEC-02).

> 시점 기재: 아래 수치는 2026-09-18 측정값이다. 이식 착수 시 다시 잰다.

---

## 1. 이식 원칙 (트리 F 층 구조에서 도출)

```
가져온다     1층 사실 클라이언트 — 외부 API 를 호출해 관측 시각·출처·해상도를 붙이는 코드
가져온다     계산 축 엔진 — 일장·적산온도 (API 아님, 순수 계산)
가져온다     외부 유래 정본 데이터 — 공시자재·관측소 목록 (재수집 가능하므로 사본은 초기값)
재료로만     VELA 내부 지식 JSON — 격자(D)의 전신이지만 스키마가 다르다. 채우기 재료
안 가져온다  3층 판단 로직 — 트리가 새로 정의한다(산출 7종·판정/금지 축 선언)
안 가져온다  4층·LLM 조립 — 경계 밖
```

이식할 때 내부 결합은 **`config` 하나로 치환**한다. 아래 표의 "내부 import" 가
`config` 뿐이면 설정 객체만 agrodss 것으로 바꾸면 끝난다(A 등급).

| 등급 | 기준 | 처리 |
|---|---|---|
| A | 내부 import 가 `config` 뿐 | 복사 + 설정 치환 |
| B | 내부 의존 1~2개, 절단 가능 | 복사 + 의존 절단(함수 인자로 승격) |
| C | VELA 판단 로직에 얽힘 | 호출부만 참고, 새로 쓴다 |

---

## 2. 클라이언트별 실측

| 파일 | 줄 | 내부 import | 설정 키(이름) | 등급 | 트리 항목 |
|---|---|---|---|---|---|
| `services/kma_daily_temp.py` | 193 | config | KMA_API_HUB_KEY · API_HUB_BASE_URL · GDD_BACKFILL_MAX_DAYS | **A** | E 관측(기온) · B6 · L 수확기 예측 |
| `services/kma_climate_normal.py` | 180 | config | KMA_API_HUB_KEY · API_HUB_BASE_URL | **A** | A1 외부 기준(평년) · L 첫해 |
| `services/farmmap_agri_weather_service.py` | 353 | config | DATA_GO_KR_API_KEY · FARMMAP.REQUEST_TIMEOUT | **A** | E 관측(농업기상) |
| `core/gdd_engine.py` | 367 | config | KMA_API_HUB_KEY | **A** | E 계산(적산온도) · B6 · L |
| `core/photoperiod_notice.py` | 88 | core.gdd_engine | — | **A** (gdd 와 짝) | E 계산(일장) · E 광③ |
| `services/kma`… `weather_intelligence_engine.py` | 544 | config + **내부 7개**(fertilization_climate_advisor · temperature_reading · ldaps · nwp · synoptic · ultra_short · farmmap) | KMA_FORECAST_API_KEY · NWP_ENABLED · HARVEST_CLEAR_STREAK_MIN_DAYS | **C** | 2층 파생에 가깝다 — 1층이 아님 |
| `services/location_to_soil.py` | 449 | config | SOIL_API_KEY · VWORLD_API_KEY · VWORLD_BASE_URL | **A** | G 필지(위치→토양) · B2 |
| `services/soil_api_client.py` | 191 | config | SOIL_API_KEY | **A** | G 토성·배수 초기값 |
| `services/soil_stat_service.py` | 291 | config + services.soil_service | SOIL_STAT_API_KEY · SOIL_STAT_BASE_URL | **B** | G 읍면동 대표값 |
| `services/heuktoram_avg_client.py` | 113 | core.agri_crawl.base_crawler | — (크롤 — robots 확인 주석 있음) | **B** | G 읍면동 대표값 |
| `services/fertilizer_std_service.py` | 577 | config | FERTILIZER_STD_API_KEY · FERTILIZER_STD_BASE_URL | **A** | B3 · **E 양분 축(신설)** |
| `services/fertilizer_service.py` | 677 | config + **내부 5개**(crop_coverage · fertilizer_advisor · farmmap_soil · soil_service …) | FERTILIZER_API_KEY · FERTILIZER_BASE_URL | **C** | 1층 호출부(FrtlzrUse)만 떼어낸다 |
| `services/ncpms_api.py` | 191 | services(패키지) | NCPMS_API_KEY · NCPMS_BASE_URL | **A** (패키지 import 는 형식뿐) | E 병해충⑤ · L 광역 예찰 |
| `services/psis_client.py` | 170 | config + core.crop_alias_canon | PSIS_API_KEY · PSIS_BASE_URL | **B** (작물명 정규화 의존) | H 자재(관행) |
| `services/psis_api.py` | 78 | services.psis_client | 동상 | **A** | 동상 |
| `core/organic_materials_job.py` | 86 | config | ORGANIC_MATERIAL_API_KEY (data.go.kr 15080748) | **A** | H 자재(유기) · H 유기 임계 |
| `core/organic_materials_scheduler.py` | 79 | config + organic_materials_job | RUN_WEEKDAY · RUN_HOUR | **A** | 동상 |
| `core/organic_materials.py` | 93 | — | — | **A** | 동상(정본 읽기) |
| `core/organic_control_map.py` | 165 | core.crop_ph_registry | — | **B** | H 유기 계열 지식 — 격자 재료 |
| `services/nongsaro_service.py` | 403 | config + core.crop_calendar · core.crop_disease_calendar | NONGSARO_API_KEY · NONGSARO_BASE_URL · NONGSARO_ENDPOINTS | **B** | D 격자 초기 채움 · L 표준 방제력 |
| `services/agrimaterial_service.py` | 189 | config | PESTICIDE · FERTILIZER_SPEC · SEED_INFO 각 API_KEY/BASE_URL | **A** (단 키 미승인 2026-06-08) | C 품종 분화 · H 자재 |
| `services/auction_price_client.py` | 478 | config + services | DATA_GO_KR_API_KEY · AUCTION_AT_BASE_URL · AUCTION_MAFRA_* | **A** | B10 · H G1 허용(시세) |
| `services/customs_trade_client.py` | 139 | config | DATA_GO_KR_API_KEY | **A** | B10 (수급) |
| `services/oasis_growth_client.py` | 107 | config | OASIS_GROWTH.TIMEOUT_SEC | **A** | K 관측 리포트(페이지 한정) |
| `core/pesticide_api_gate.py` | 137 | data_gap_log · growth_stage_gate · organic_materials | — | **C** | 3층 판단 — 새로 쓴다(H 필터 "위험 쪽으로 기움"의 VELA 판) |

집계: A 16 · B 6 · C 3. **A 등급만으로 트리 L 첫해 값 넷이 전부 선다**
(KMA 둘 + gdd + photoperiod → 수확기 예측·달력 경보 / ncpms → 광역 예찰 /
nongsaro 는 B 지만 절단이 한 줄 — crop_calendar 의존은 검증용이라 떼면 된다).

---

## 3. 정본 데이터 파일

| 파일 | 크기 | 성격 | 처리 |
|---|---|---|---|
| `data/organic_materials_public.json` | 1,098K | 외부 유래(농관원, fetched_at 2026-09-07) | 초기 사본 복사 후 스케줄러로 재수집 |
| `data/stations.json` | 1,145K | 외부 유래(KMA 관측소) | 복사 |
| `data/oasis_growth_measure.json` | 997K | 외부 유래(KREI) | 복사 |
| `data/kamis_monthly_history.json` | 137K | 외부 유래(KAMIS) | 복사 |
| `data/crop_master_list.json` | 250K | VELA 내부(2.1.0, 2026-07-10) — **180종 목록의 정본 후보** | M2 "목록 성격 확인" 의 입력. 복사하되 격자 아님 |
| `data/crop_taxonomy.json` | 36K | VELA 내부 — 대/중/유형/소분류 | C 분류의 재료. 트리 C 는 축이 다르다(생애주기×수확형태) — 재분류 대상 |
| `data/crop_calendar_data.json` | 253K | VELA 내부 — 월별 권장/주의/금지 | D 격자 재료 — 단위가 "월" 이라 트리 D(기준일 기반 단계)와 다름 |
| `data/growth_stage_db.json` | 192K | VELA 내부 — 작목별 단계 | D 단계명·순서 재료 |
| `data/pesticide_db.json` · `pest_disease_db.json` | 74K · 34K | VELA 내부 | D 병해충 칸 재료 |
| `data/nutrient_db.json` | 53K | VELA 내부 — target_quality 에 조건 필드 있음(N-149) | E 양분 축 재료. **조건 필드를 함께 싣는다** |
| `data/improvement_drafts.json` · `feedbacks.json` | 240K · 77K | 사용자 발화 | G 관찰의 유일한 실증 재료 — 읽기 전용으로 가져간다 |

내부 지식 JSON 은 전부 **"채운 뒤 격자 스키마(M5)로 옮기는 재료"** 다. 스키마를
고정하기 전에 복사하면 두 벌이 된다.

---

## 4. 설정 키 이름 목록 (agrodss `.env` 골격 — 값 없음)

```
KMA_API_HUB_KEY            KMA_FORECAST_API_KEY
DATA_GO_KR_API_KEY         (farmmap · 관세청 · aT 경락 · 공시자재 공용)
ORGANIC_MATERIAL_API_KEY   (비면 DATA_GO_KR_API_KEY 로 대체하는 로직이 job 에 있음)
SOIL_API_KEY               SOIL_STAT_API_KEY        VWORLD_API_KEY
FERTILIZER_API_KEY         FERTILIZER_STD_API_KEY
NCPMS_API_KEY              PSIS_API_KEY             NONGSARO_API_KEY
PESTICIDE_API_KEY          FERTILIZER_SPEC_API_KEY  SEED_INFO_API_KEY   ← 승인 여부 재확인
```

값은 VELA `.env` 에만 있고 이 문서·커밋·핸드오버에 옮겨 적지 않는다.

---

## 5. 이식 순서 제안 (트리 M · L 에 맞춤)

| 순서 | 묶음 | 근거 |
|---|---|---|
| 1 | KMA 둘 + gdd_engine + photoperiod_notice + stations.json | A 등급, L "수확기 예측·달력 경보" 가 이것만으로 선다. 계산 축(일장·적산온도) 포함 |
| 2 | ncpms_api | A, L "광역 예찰" — E 병해충⑤ 우선순위 1 |
| 3 | nongsaro_service (crop_calendar 의존 절단) | L "표준 방제력", D 격자 초기 채움. **M5 스키마 뒤에** — 채울 곳이 있어야 |
| 4 | psis + organic_materials 셋 + 공시 사본 | H 자재 분리 — 관행/유기 대칭. 인증 유형은 `farming_method` 를 G 필지 정보로 옮긴다 |
| 5 | location_to_soil + soil_api_client + fertilizer_std | G 필지 초기값(토성·배수) · **E 양분 축 신설** 뒤에 |
| 6 | auction/customs/oasis | B10 · K — 상시 군이라 뒤 |
| — | weather_intelligence_engine · fertilizer_service · pesticide_api_gate | C — 가져오지 않는다. 트리 3층을 세운 뒤 필요하면 호출부만 참고 |

순서 3·5 가 **트리 즉시 4건**(산출 7종·양분 축·입력 5종·축 최소 고정 → M5)에
걸린다. 1·2·4 는 트리 결정과 무관하게 지금 옮길 수 있다.

---

## 6. 가져가지 말아야 할 것 (명시)

- **3층 판단** — `pesticide_api_gate` · `block_gate` · `response_assembly` · 유기 게이트
  계열. VELA 이력(N-97·N-136·N-147)은 이것이 **경로마다 붙어 새는 형태**였다는 기록이다.
  트리 F 는 "산출 레벨 말미 1회" 를 처음부터 구조로 둔다. 옮기면 그 결함도 옮겨진다.
- **월 단위 달력**(`crop_calendar_data.json`) 을 격자로 오인하는 것 — D 단위는
  기준일이다.
- **VELA `.env`** — 키 재발급이 아니라 값 복사도 SEC-02 위반은 아니지만, 두 시스템이
  한 키를 쓰면 쿼터 경합·회전 시 한쪽 단절이 난다. agrodss 는 키를 따로 받는다.
