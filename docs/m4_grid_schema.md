# M-4 — 격자 스키마 고정 (공통분모만)

**무엇을 지키려는가**: 작목 지식이 들어갈 **칸의 모양**을 하나로 고정한다. 칸이 참조하는 축은
I-4 의 이름 밖을 가리킬 수 없고, 빈칸 3종(값 있음 / 해당 없음 / 아직 안 채움)이 구분되며,
회복 불가 위험은 경보 정책 없이는 등록되지 않는다. 검증기는 `grid/schema.py`, 이 문서는 그 설명이다.

작성 2026-09-18. 대장 M-4. 근거: 트리 D · I-1 · I-4 · 몰-C(촬영 시점 칸) · d1(시즌 중 소급 입력).

## 1. 단위(unit) — 하나의 연속된 재배 일정

```
unit.id            "jjokpa-autumn"          정본명(I-8) × (작기 | 품종)
unit.crop          "쪽파"                    names/resolve 의 정본명이어야 한다
unit.kind          "season" | "variety"      작형 결정권(C) — 작기가 결정 / 품종이 결정
unit.anchor_kind   "파종(종구)" 등            기준점의 종류. 시간축 0 일
unit.source        출처 · 확신               격자 전체의 기본 출처(칸이 덮어쓸 수 있다)
variety_correction time_shift_days · cell_overrides   트리 D 보정 2종
```

기준일이 다르면 별개 단위다(배추 → 작기별, 사과 → 품종별, 옥수수 → 파종 회차별).

## 2. 칸(stage) — 단계 하나

| 필드 | 형 | 뜻 · 규칙 |
|---|---|---|
| `order` · `name` | int · str | 순서 유일 |
| `window` | `{from_day, to_day, basis}` | 기준점 기준 상대 일수. `basis` = `anchor` 만 — `gdd` 는 예약어(스키마가 거부. [코드 평가 A7 2026-09-19] 소비자 넷이 전부 기준일+일수로만 읽어 열어 두면 조용히 틀린 날짜가 난다 — 적산온도 판정기가 생길 때 여기와 검증기를 함께 연다) |
| `risks[]` | 아래 | 위험 + **회복 가능성** |
| `tasks[]` | 아래 | 작업 + 도구 + 자재 + 작업일/준비 착수일 |
| `required_axes[]` · `forbidden_axes[]` | I-4 id | 판정 축 / 금지 축. 교집합 없음. **I-4 밖 id 는 검증 실패** |
| `water` | `{demand, deficit_sensitivity, excess_sensitivity}` | 각각 낮음/중간/높음 |
| `variety_dependence` | `time_only` \| `traits` | 품종 의존 정도 |
| `unit_scope` | `parcel` \| `cultivation_unit` | 적용 단위 |
| `judge_without_variety` | `ok` \| `range` \| `no` | 품종 미확인 시 판단 가능 여부 |
| `capture` | `{shoot, scene}` | **촬영 시점 칸**(몰-C). 시즌 중 소급 입력 허용 |
| `decisions[]` | str | 이 칸이 답하는 결정 id — M-8 등록과 이어진다 |
| `source` · `confidence` | str · 상/중/하 | 칸 단위 출처. 없으면 unit.source |

### risks[]

| 필드 | 규칙 |
|---|---|
| `name` · `trigger` | |
| `recoverable` | bool. **false 면 `alert` 가 `oversignal_ok` 여야 한다**(H 경보 비대칭 — 오경보 감수) |
| `alert` | `oversignal_ok` \| `confident_only` |
| `axes[]` | 이 위험을 판정하는 축 — I-4 id |
| `parcel_correction` | bool. 병해충 칸만 true(트리 D) |

### tasks[]

| 필드 | 규칙 |
|---|---|
| `name` · `work_day` | 이름(계획표가 이 키로 사건을 잇는다) · 작업일(기준점 상대 정수). 둘 다 필수 |
| `lead_days` | `{own, rental}` **정수** — 조달 경로별 리드타임. 준비 착수일 = work_day − lead. 다른 단계로 넘어갈 수 있다 → F 선제 발화 |
| `tools[]` | |
| `materials` | `{"관행": [...], "유기": [...]}` — **인증 유형별 분리**(H). 한쪽이 없으면 빈 목록이 아니라 `"N/A"` |
| `retry` | `{possible, deadline_day}` — `possible` 은 bool, `deadline_day` 는 정수 또는 **`null`**. 두 키 다 **있어야** 한다 |

> **마감을 모르면 `deadline_day: null` 로 적는다 — 키를 빼지 않는다**(2026-09-20). 빼면 관문이 통과시키고, 그 뒤
> 결정기가 창 끝으로 마감을 지어낸다(대리값 금지 위반). `null` 이면 그 작업을 쓰는 결정이 **판단 불가(지식)** 로 나간다.
> 모른다고 적을 자리가 스키마에 있어야 격자를 쓰는 사람이 숫자를 지어내지 않는다.

## 3. 빈칸 3종

```
값 있음        필드에 값
해당 없음      필드 값이 문자열 "N/A"        아무리 채워도 이 결정이 적용되지 않는다
아직 안 채움   필드가 없다(키 부재)          → 3층 산출 "판단 불가(지식)" 의 근거(I-1 §2-5)
```

`null` 은 쓰지 않는다 — "값이 null" 인지 "안 채움" 인지 구분이 안 된다. 완성도는
검증기가 센다(값 / N/A / 미채움).

## 4. 검증 규칙 (grid/schema.py)

1. `unit.crop` 이 정본명이다.
2. `order` 유일, 1부터 연속.
3. 모든 축 id 가 I-4 목록 안이다(`humidity_air` 는 금지 축으로만 허용).
4. `required_axes ∩ forbidden_axes = ∅`.
5. 회복 불가 위험은 `alert == oversignal_ok`.
6. `parcel_correction == true` 인 위험은 축에 `pest_*` 또는 `microclimate` 가 있어야 한다.
7. 단위에 `capture.shoot == true` 인 칸이 하나 이상 있다(몰 대원칙 — 영상이 상세페이지).
8. `materials` 는 dict(관행/유기) 또는 `"N/A"`.
9. `judge_without_variety == "no"` 인 칸은 `variety_dependence == "traits"` 여야 한다(품종을 모르면 판단 불가인데 시간축만 의존한다는 것은 모순).

## 5. 이 스키마가 못 담는 것 (명시)

- 버섯(별도 구조 — 시간이 아니라 조작으로 전환). 트리 C. 지금 안 만든다.
- 대목(목본) — U-5. `variety_correction` 아래에 자리를 예약만 한다.
- 관측 기반 기준점(개화기)의 **판정 규칙** — 기준점 종류는 적지만 "개화기를 언제로 볼 것인가"는 3층 결정이다.
