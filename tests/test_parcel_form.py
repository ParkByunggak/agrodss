# -*- coding: utf-8 -*-
# [발행자 2026-09-21] "필지 3문항(배수 · 주변 개방도 · 안개 빈도)과 토성·경사가 비어 있어서 … 나가서 보면 답이 나오는 것들입니다."
#
# 실측 둘이 이 검사의 뼈대다.
#   ① 답이 들어갈 자리가 **없었다** — `missing_inputs` 는 "입력 대기 10" 을 보여 주기만 했고, 쓰는 길은 CLI(`parcels.set_fields`) 뿐이었다.
#      밭에서 답을 받아 와도 JSON 을 손으로 고쳐야 했다. → /me 에 폼, /me/parcel 에 그 자리.
#   ② 그 값을 **읽는 쪽**을 같은 자리에서 전수로 셌다(§7.5 처방 직후 전수). 입력 대기 필드 중 판정·수집이 값을 읽는 것은
#      `use` · `environment` **둘뿐**이고, 나머지는 소비자 0 이다. 미기상은 격자 칸 3 축과 pest_alert 선택 축에 이름이 있고
#      docs/i4_axes_minimal.md 가 "병해충 칸 필지 보정 ②" 라고 적었는데 **값을 읽는 코드가 없다**(G1 — 정본이 있는데 소비자가 없다).
#      그래서 화면이 그 사실을 말한다. 아래 검사는 그 문면이 **양쪽 다** 붙는지 본다(읽는 값 · 쌓이기만 하는 값).
from __future__ import annotations

import http.client
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pytest

from frontend import chat_pages
from ingest import media, parcels
from judge import stage_decisions as SD
from tests.test_brand_home import srv  # noqa: F401

SID = "p001-jjokpa-2026f"


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _overlay() -> dict:
    return {r["id"]: r for r in json.loads(Path(parcels.local_path()).read_text(encoding="utf-8"))["parcels"]}


# ── 자리가 있는가 ────────────────────────────────────────────────────────────────
def test_the_screen_has_a_place_for_every_field_the_screen_asks_for(srv):
    """'입력 대기' 로 묻는 것에는 답할 칸이 있다 — 좌표·검정 참조만 예외이고 그 둘은 화면이 받을 값이 아니다."""
    st, body = _get(srv, "/me")
    assert st == 200
    for key in list(parcels.FIELD_CHOICES) + [k for k, _ in parcels.FIELD_LABELS]:
        assert f'name="{key}"' in body, key
    asked = set(parcels.missing_inputs(parcels.by_id("p001")))
    has_input = set(parcels.FIELD_CHOICES) | {k for k, _ in parcels.FIELD_LABELS}
    assert asked - has_input <= {"lat", "lon", "soil_exam_ref"}, sorted(asked - has_input)


def test_the_form_carries_no_pii_not_even_as_a_field(srv):
    """[D-1 · U-18] 주소·PNU·좌표는 폼에 **자리조차** 없다. 덮개에 든 값도 화면에 안 나온다."""
    parcels.set_fields("p001", pnu="4111100000000000000", lat=36.7, lon=127.9)
    st, body = _get(srv, "/me")
    assert st == 200
    for k in parcels.PRIVATE_FIELDS:
        assert f'name="{k}"' not in body, k
    assert "검사용 지번" not in body and "4111100000000000000" not in body and "36.7" not in body
    assert "위치 있음" in body                                                    # 있음/없음만 말한다


def _label_of(body: str, key: str) -> str:
    """그 칸의 <label> 한 덩이만 잘라 본다 — 앞뒤 N 자 창이 아니라 **구조**로 자른다(래칫 규율: 창을 고정하지 않는다)."""
    i = body.index(f'name="{key}"')
    start = body.rindex("<label", 0, i)
    return body[start:i]


def test_the_screen_says_which_answers_a_judgment_actually_reads(srv):
    """G1 전수의 화면 판 — 읽는 값과 쌓이기만 하는 값이 **양쪽 다** 표시된다(한쪽만이면 못 가른다)."""
    st, body = _get(srv, "/me")
    assert st == 200
    for key in list(parcels.FIELD_CHOICES) + [k for k, _ in parcels.FIELD_LABELS]:
        want = chat_pages.READS_LABEL if key in parcels.FIELDS_READ_BY_JUDGMENT else chat_pages.STORED_ONLY_LABEL
        other = chat_pages.STORED_ONLY_LABEL if want == chat_pages.READS_LABEL else chat_pages.READS_LABEL
        lab = _label_of(body, key)
        assert want in lab and other not in lab, (key, lab)
    assert chat_pages.READS_LABEL in body and chat_pages.STORED_ONLY_LABEL in body   # 두 표지가 다 쓰인다(한쪽만이면 가르지 못한다)


# ── 받은 답이 어떻게 되는가 ──────────────────────────────────────────────────────
def test_filled_answers_are_saved_and_blanks_are_left_alone(srv):
    """밭에서 받아 온 답이 들어가고, **빈 칸은 아무것도 안 한다** — 지우지도 메우지도 않는다(대리값 금지)."""
    before = Path(parcels.parcels_path()).read_bytes()
    st, body = _post(srv, "/me/parcel", {"id": "p001", "soil_texture": "양토", "slope": "완경사", "drainage": "보통",
                                         "microclimate": "동향 · 안개 잦음", "area_m2": "330", "irrigation": "", "night_light": "",
                                         "environment": "", "use": "", "seed_source": "", "cert_legal": ""})
    assert st == 200 and "필지 p001 저장" in body
    rec = parcels.by_id("p001")
    assert rec["soil_texture"] == "양토" and rec["slope"] == "완경사" and rec["drainage"] == "보통"
    assert rec["area_m2"] == 330 and isinstance(rec["area_m2"], int)              # 숫자로 들어간다(문자열 "330" 이 아니라)
    assert rec["use"] == "시험 재배(자가)" and rec["environment"] == "노지"          # 빈 칸이 **있던 값을 지우지 않았다**
    assert "night_light" not in rec and "irrigation" not in rec                   # 빈 칸을 '없음' 으로 메우지도 않았다
    assert Path(parcels.parcels_path()).read_bytes() == before                    # 쓰기는 덮개에만(씨앗은 커밋으로만)
    assert _overlay()["p001"]["soil_texture"] == "양토"


def test_a_corrected_answer_wins_so_the_screen_does_not_swallow_it(srv):
    """고쳐 적은 답은 덮는다 — `set_fields` 기본은 '있는 값은 안 덮는다' 라, 그대로 두면 화면이 받아 놓고 조용히 버린다."""
    parcels.set_fields("p001", slope="평지")
    st, body = _post(srv, "/me/parcel", {"id": "p001", "slope": "급경사"})
    assert st == 200 and parcels.by_id("p001")["slope"] == "급경사", body


def test_an_empty_form_changes_nothing_and_says_so(srv):
    before = json.dumps(_overlay(), ensure_ascii=False, sort_keys=True)
    st, body = _post(srv, "/me/parcel", {"id": "p001"})
    assert st == 400 and "채운 칸이 없다" in body
    assert json.dumps(_overlay(), ensure_ascii=False, sort_keys=True) == before


# ── 어휘 관문 — 거부와 통과를 둘 다 본다 ─────────────────────────────────────────
def test_the_vocabulary_gate_refuses_outside_words_and_passes_the_listed_ones(srv):
    """[게이트 검사는 양방향] 막는 것만 보면 '열어놓고 깨진 상태' 를 못 본다."""
    for key, opts in parcels.FIELD_CHOICES.items():
        assert parcels.set_fields("p001", overwrite=True, **{key: opts[-1]})[key] == opts[-1]      # 통과
        with pytest.raises(parcels.ParcelError) as e:
            parcels.set_fields("p001", overwrite=True, **{key: "아무말"})                            # 거부
        assert key in str(e.value) and opts[0] in str(e.value)                    # 사유가 고를 말을 알려 준다
    st, body = _post(srv, "/me/parcel", {"id": "p001", "area_m2": "서른 평"})
    assert st == 400 and "숫자여야 한다" in body
    with pytest.raises(parcels.ParcelError):
        parcels.set_fields("p001", area_m2=0, overwrite=True)


def test_the_environment_vocabulary_is_one_canon_not_two(srv):
    """재배환경 어휘는 등록부가 정본이고 시비 수집이 그것을 본다 — 목록이 두 벌이면 화면과 CLI 가 어긋난다."""
    from ingest import fertilizer as fz
    assert fz.ENVIRONMENTS is parcels.FIELD_CHOICES["environment"]
    assert set(fz.CROP_CODES["쪽파"]["FrtlzrUse"]) == set(parcels.FIELD_CHOICES["environment"])      # 작물코드표와 같은 말


# ── 판정 쪽 — 채운 값이 무엇을 여는가(정직) ──────────────────────────────────────
def test_use_changes_a_judgment_and_microclimate_changes_none(srv):
    """FIELDS_READ_BY_JUDGMENT 가 사실인지 **동작으로** 잰다 — 소스 문자열이 아니라(자기 도구 오류 계열).

    `use` 를 자가로 두면 출하 결정이 '해당 없음' 이고, 판매로 바꾸면 납품 계획일을 묻는다(읽는다).
    미기상은 무엇을 넣어도 병해충 경보 봉투가 그대로다(오늘은 읽는 쪽이 없다).
    """
    today = date(2026, 9, 21)

    def _subject() -> dict:
        raw = next(s for s in media.load_subjects() if s["id"] == SID)
        return parcels.enrich_subject(raw, parcels.by_id("p001"))

    def _body(e) -> dict:
        d = e.to_dict()
        d.pop("as_of")                                                            # 시각은 매번 다르다 — 판정 본문만 견준다
        return d

    parcels.set_fields("p001", mall_supply=True, overwrite=True)                  # 몰 납품 여부는 따로 선 게이트 — 그것을 열고 use 만 흔든다
    assert SD.judge_ship_or_store(_subject(), today).kind == "해당 없음"            # 용도가 '시험 재배(자가)' — D-8
    parcels.set_fields("p001", use="판매", overwrite=True)
    sold = _subject()
    assert SD.judge_ship_or_store(sold, today).kind == "판단 불가(데이터)"           # 읽었다 — 답이 달라진다
    base = _body(SD.judge_pest_alert(sold, today))
    parcels.set_fields("p001", microclimate="사방 트임 · 안개 없음", overwrite=True)
    assert _body(SD.judge_pest_alert(_subject(), today)) == base                  # 안 읽었다 — G1(선언만 있는 축)
    assert "microclimate" not in parcels.FIELDS_READ_BY_JUDGMENT                  # 대장의 말과 동작이 같은 것을 가리킨다
