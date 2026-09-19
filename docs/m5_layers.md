# M-5 — 층 구조 + 출력 규칙 (마일스톤 1-3) 대조표

**무엇을 지키려는가**: 1층(사실)→2층(파생)→3층(판단)→4층(전달)이 한 방향으로만 흐르고,
3층은 정해진 8종 봉투로만 말하며, 봉투에는 값이 아니라 이름이 실린다. 판매·재고는
3층에 들어오지 않고(G1), 판단은 언제 무엇을 보고 어떤 규칙으로 했는지를 동반하며(G2),
빈 축은 대리값으로 메우지 않는다(G3).

작성 2026-09-19. 대장 M-5. 근거: `agrodss_milestones_20260918.md` 1-3 · 평가서 §6-2 · H.

## 0. 낡음 대조 — 왜 이제 닫는가

마일스톤 문서는 1-3 을 *"종이 위에서 끝난다"* 고 썼다(2026-09-18). 하루 사이 I-1·I-3·I-5·
M-10·M-11 이 그 다섯 조건을 **코드로** 각각 세웠고, 대장 M-5 행만 "대기"로 남아 있었다.
조각은 다 있는데 **함께 서 있는가**를 재는 관문이 없었다 — 이 문서와
`tests/test_m5_layers.py`(7건)가 그 관문이다. 실제 등록부(p001 쪽파) 위에서 잰다.

## 1. 다섯 조건 ↔ 코드 ↔ 래칫

| # | 조건 | 어디에 있나 | 이 관문의 검사 | 주입(2026-09-19) |
|---|---|---|---|---|
| ① | 1층 진입 3요건 — 시각·출처·해상도 | `schema/records.py` 1층 kind 전부의 `required`; `validate()` 가 `resolution` 빈값·사람 출처의 `observed_at` 빈값을 거부 | 1층 사실·1층 계획 kind 전부에 `source`·`resolution`·시각 필드가 필수인가 | — (①은 스키마 검사 `test_schema.py` 가 이미 주입 검증) |
| ② | 영상=1층 사실 · 판독=2층(§6-2) — 판독값은 3층의 축이 아니다 | `observation.video/image` 는 메타(파일·시각·필지·해상도)만; 결정 등록부 축 목록에 영상 판독 축 없음; `plan_vs_actual` 은 영상을 **찍었는가(시각)** 로만 쓴다 | kind 필드에 판독 칸 없음 · 등록부 축에 video/reading 없음 · `plan.capture` 분기가 `observed_at`·`id` 외 필드를 읽지 않음 | 판정기가 `v.get('reading')` 을 읽게 → 1 failed |
| ③ | 3층 산출 8종 | `judge/envelope.py` `KINDS` · `docs/i1_outputs.md` §2 | 코드 8 == 문서 8, 이름·순서 일치 | — (목록 대조는 그 자체가 양방향) |
| ④ | 4층 격리 — 봉투는 이름만 | `AxisUse` 5필드(값 없음); 3층 판정기는 `subject.soil_chem`·예보 `values` 를 읽되 봉투에 싣지 않는다 | 실제 등록부 12봉투를 재귀로 훑어 `mall.FORBIDDEN_KEYS`(PII ∪ soil_chem·values·raw·file…) 0건 · 모든 입력에 출처·해상도 | 결과에 `soil_chem` 을 실으면 → 1 failed |
| ⑤ G1 | 판매·재고 → 조언 입력 금지 | `schema.LAYER3_SUBJECT_FIELDS` · `LAYER3_INPUT_KINDS`; `judge/boundary.py` 게이트 1회(`test_boundary.py` 가 위치까지 고정) | 3층 주체 필드·3층 입력 kind 의 필드에 stock/order/demand/판매량 계열 이름 없음 | — (경계 게이트는 `test_boundary.py` 주입 검증) |
| ⑤ G2 | 관측일·판정 기준 동반 | 봉투 `as_of`·`inputs[].observed_at`; 결정 등록부 `Decision.rule`(빈 문장은 등록 거부) | 모든 봉투의 `decision_id` 가 등록부에 있고 규칙 문장이 있다 · 판단함은 등급+입력 필수 | — (등록 거부는 `test_harvest_timing.py`) |
| ⑤ G3 | 공백을 대리값으로 안 메움 | 기준점 없음 → `판단 불가(데이터)` + `missing[{axis, who_can_fill}]`; `Envelope.__post_init__` 가 다른 종류의 `missing` 을 거부 | 기준점 없는 주체에 창(window_*)을 만들지 않고 누가 채울 수 있는지를 싣는다 · `missing` 비어 있음 ⇔ 판단 불가(데이터) 아님 | 기준점을 `today-25일` 로 메우면 → 1 failed |

시각 필드는 **사실은 관측 시각, 계획은 계획일**이다(실측: `plan.task`·`plan.capture` 는
`work_date`, `plan.target_date` 는 `target_date`). 계획에 `observed_at` 을 요구하면 없는
관측을 지어내게 되므로 관문은 셋 중 하나를 본다.

## 2. 이 관문이 보지 않는 것

- **2층 자체**. 지금 2층 파생물은 격자(`grid_schema`)와 처방 계산뿐이고 영상 판독은
  없다(§6-2 규칙이 *"판독은 확인 요청 트리거만"* 이라 했고, 그 트리거도 아직 없다 —
  U-9 영상 판독 자동화 여부, 보류). 판독이 생기는 날 ②의 축 검사가 먼저 빨간불이 된다.
- **몰 화면의 4층 격리**는 M-11(`mall/product.py assert_public`)의 몫이다. 여기서는
  봉투 쪽만 본다 — 같은 `FORBIDDEN_KEYS` 를 쓰므로 목록은 한 벌이다.
- **G1 의 시세 허용**(KAMIS 등은 판매 상태가 아니라 외부 사실)은 아직 원천이 없어
  검사 대상이 없다. 붙이는 날 `external:` 접두 규칙(`test_schema.py`)이 그것을 받는다.
