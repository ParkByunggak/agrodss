# 스키마 정본 — 레코드 종류 (생성물)

정본은 `schema/records.py` 다. 이 문서는 `scripts/build_schema_doc.py` 가 만든다 — 손으로 고치지 않는다. 버전 1.

허용 목록 방식: 선언되지 않은 필드는 거부된다. 경계(`judge/boundary.py`)의 허용 목록은 여기서 파생된다.

| 종류 | 층 | 3층 입력 | 출처 | 필수 | 선택 | PII |
|---|---|---|---|---|---|---|
| `subject` | 등록부 | 예 | `d1_first_farm.md (발행자 2026-09-18)`, `farmer`, `publisher` | id, parcel, label, crop, season, source | anchor, anchor_kind, grid_unit, cert, status, recorded_at, note | — |
| `user` | 등록부 | — | `farmer`, `publisher` | id, name, role, parcels, source, recorded_at | note | — |
| `parcel` | 등록부 | — | `farmer`, `publisher` | id, source, recorded_at, observed_at, resolution | address, pnu, lat, lon, area_m2, area_source, use, mall_supply, environment, soil_texture, slope, drainage, irrigation, microclimate, night_light, cert_claimed, cert_legal, cert_since, seed_source, variety, soil_exam_ref, note | address, pnu, lat, lon |
| `observation.video` | 1층 사실 | 예 | `farmer` | id, subject, observed_at, observed_at_source, recorded_at, source, resolution, origin, file, sha256, bytes | width, height, duration_sec, gps, note | gps |
| `observation.image` | 1층 사실 | 예 | `farmer` | id, subject, observed_at, observed_at_source, recorded_at, source, resolution, origin, file, sha256, bytes | width, height, duration_sec, gps, note | gps |
| `event` | 1층 사실 | 예 | `farmer`, `mall:settlement` | id, type, subject, observed_at, recorded_at, source, resolution | advice_ref, materials, quantity, quality_grade, return_reason, note, chat_ref, risk, severity | — |
| `observation.note` | 1층 사실 | 예 | `farmer` | id, subject, text, observed_at, recorded_at, source, resolution | tags, chat_ref | — |
| `plan.farmer` | 1층 계획 | 예 | `farmer` | id, subject, task, planned_day, recorded_at, observed_at, source, resolution | note, chat_ref, done_ref | — |
| `decision.noncompliance` | 1층 사실 | 예 | `farmer` | id, subject, planned_task, planned_day, reason, observed_at, recorded_at, source, resolution | — | — |
| `observation.weather_daily` | 1층 사실 | 예 | `external:` | axis, observed_at, fetched_at, source, resolution, values, station | — | — |
| `reference.climate_normal` | 1층 사실 | 예 | `external:` | axis, observed_at, fetched_at, source, resolution, values, station, for_day | — | — |
| `forecast.weather_daily` | 1층 사실 | 예 | `external:` | axis, observed_at, fetched_at, source, resolution, values, for_day | hourly_tmp, sky, pty | — |
| `observation.pest_forecast` | 1층 사실 | 예 | `external:` | axis, observed_at, fetched_at, source, resolution, values, region, crop_requested, crop_code_crop, raw, schema_confirmed | proxy_reason | — |
| `reference.organic_material_notice` | 1층 사실 | 예 | `external:` | axis, observed_at, source, resolution, values | — | — |
| `observation.soil_exam` | 1층 사실 | 예 | `external:` | status, pnu, axis, source, resolution, observed_at, fetched_at | exam_year, address_label, values, units, message | pnu, address_label |
| `reference.fertilizer_prescription` | 1층 사실 | 예 | `external:` | axis, status, pnu, crop_code, observed_at, fetched_at, source, resolution, values, units | crop_name, raw, message | pnu |
| `reference.pesticide_registration` | 1층 사실 | 예 | `external:` | axis, status, crop, pest, observed_at, fetched_at, source, resolution, total, items | queried_as, message | — |
| `reference.fertilizer_standard` | 1층 사실 | 예 | `external:` | axis, status, crop_code, observed_at, fetched_at, source, resolution, values, units | crop_name, raw, message | — |
| `plan.task` | 1층 계획 | 예 | `computed:grid` | source, resolution, stage, task, work_day, work_date, prep_date_own, prep_date_rental, tools, materials, retry_possible, deadline_day, deadline_date, source_note | — | — |
| `plan.capture` | 1층 계획 | 예 | `computed:grid` | source, resolution, stage, task, work_day, work_date, prep_date_own, prep_date_rental, tools, materials, retry_possible, deadline_day, deadline_date, source_note | — | — |
| `plan.target_date` | 1층 계획 | 예 | `farmer` | subject, target_date, source, resolution | id, recorded_at, observed_at, note, chat_ref | — |
| `chat.message` | 1층 사실 | — | `computed:chat`, `farmer`, `publisher` | id, subject, role, text, observed_at, recorded_at, source, resolution | drafts, confirmed_refs, reply_ref, retry_of, edit_of, request_ref, input_mode, media_refs | — |
| `feedback.request` | 되먹임 | — | `farmer`, `publisher` | id, text, target, status, observed_at, recorded_at, source, resolution | subject, target_ref, response, item_ref | — |
| `feedback.prediction` | 되먹임 | — | `computed:judge` | id, subject, decision_id, envelope_kind, payload, payload_hash, observed_at, recorded_at, source, resolution | grade, code_head, last_seen_at | — |
| `feedback.outcome` | 되먹임 | — | `computed:evolve` | id, subject, decision_id, prediction_id, verdict, detail, observed_at, recorded_at, source, resolution | actual_ref | — |
| `names.candidate` | 되먹임 | — | `farmer`, `publisher` | id, query, normalized, context, status, observed_at, recorded_at, source, resolution | subject, canonical, alias_kind, note | — |
| `verification.live` | 되먹임 | — | `computed:verify` | id, subject, subjects, code_head, runs, verdict, live, agree, total, diffs, cache_suspect, observed_at, recorded_at, source, resolution | — | — |
| `improvement.item` | 되먹임 | 예 | `computed:evolve`, `farmer`, `publisher` | id, origin, target, proposal, direction, status, auto_applied, observed_at, recorded_at, source, resolution | subject, target_ref, applied_ref, verify, note, history | — |

## 어휘

- 요구 상태: 접수 · 검토 · 채택 · 반영 · 거부 · 보류
- 개선 항목 상태: 제안 · 검토 · 채택 · 반영 · 검증 · 거부 · 보류
- 개선 방향: 보수 · 확장 — 보수만 자동 적용될 수 있다(D-14)
- 대상: grid · decision · dictionary · screen · schema · input · other
- 대조 판정: 적중 · 빗나감 · 대조 불가
- 재배 단위 상태: 계획 · 재배 중 · 종료
- 금지 필드(문서용 — 검사는 허용 목록): demand, demand_forecast, inventory, inventory_qty, order_qty, orders_pending, price, rating, revenue, review_score, sales_velocity, settlement_amount, stock, unit_price, views, 단가, 리뷰, 수요, 수요예측, 재고, 정산액, 조회수, 주문, 주문잔량, 판매속도, 평점
- PII(화면·봉투·몰에 안 나감): address, address_label, gps, lat, lon, pnu
