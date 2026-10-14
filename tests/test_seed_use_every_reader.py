# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-14 W-01 · W-02 · W-03 · W-06 · W-19 · W-24] 용도 「종구 생산」 을 넣으면 답들이 **서로 다른 말**을 했다 — 같은 날 같은 수확 칸을 두고
#     수확 시기   「아직 모릅니다 — 종구 재배의 수확 때는 재배 달력에 아직 없습니다」
#     물 · 약     「이번엔 할 일이 아닙니다 — 수확 칸에는 가뭄 · 관수 판단을 두지 않습니다」(잎 기준 단정 · W-01)
#     위험        「지금 창에 경보 없음」(본 칸이 없는데 없다고 · W-03)
#     촬영 안내   「수확 직전 전경 + 수확물 근접」(잎 수확 장면 — 대화 옆 칸 · 영상 반입 · 몰 · W-02) · 수확 후 칸은 「False」(W-06)
# 뿌리는 둘이었다. ① 용도가 **안 도착했다** — 필지 값이라 판정 회차만 붙여 넘겼고 촬영 안내 · 몰 · 달력 끝 줄은 날 재배 단위를 넘겼다(관문의 입력 축).
#                  ② 문이 **세 곳에만** 있었다 — 수확 시기 · 위험 경보 · 계획표. 물 · 약 · 촬영은 문 자체가 없었다(§7.5 지점 축).
# 그리고 「'일지에 넣기' 를 누르면 판단이 읽습니다」 가 「그 판정이 그 기록을 센다」 는 표에서 왔다 — 세는 것과 답이 바뀌는 것은 다르다(W-19).
#
# 고정하는 것(전부 양방향 — 용도가 없으면 전과 같다):
#   ① 입력 도착 — 날 재배 단위로 읽어도 용도가 붙는다(필지에서) · 재배 단위에 붙어 있으면 그것이 이긴다
#   ② 문은 키 단위 — 키 없이 못 부른다 · 덮어쓴 키만 연다(값이 온 키만 열리고 안 온 키는 따라 열리지 않는다) · 부르는 곳 전부가 키를 넘긴다
#   ③ 같은 날 같은 칸의 답이 같은 말을 한다(물 · 약 · 위험 · 수확)
#   ④ 촬영 안내 셋이 잎 장면을 안 낸다 · 「False」 가 안 나간다
#   ⑤ 위험: 보는 칸 전부 기준 없음 → 판단 불가(지식) · 일부 → 본 칸만 「경보 없음」 · 지난 수확 칸도 안 낸 칸으로 말한다 · 칸 카드가 빈 곳을 가리키지 않는다
#   ⑥ 「누르면 판단이 읽습니다」 는 넣은 셈으로 다시 낸 답이 바뀔 때만 — 그 셈이 실제로 넣은 것과 같다(도구 검증 · 양방향)
#   ⑦ 조사(W-24)
from __future__ import annotations

import ast
import copy
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import chat_pages, serve, words
from grid import capture as grid_capture, schema as grid_schema
from ingest import chat, parcels, subjects
from judge import run as judge_run
from judge.envelope import COUNTERS, reading_face
from mall import product

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
HARVEST, AFTER, MIDDLE, PAST = date(2026, 10, 15), date(2026, 11, 4), date(2026, 10, 7), date(2026, 11, 24)
WHERE = {HARVEST: "수확(5단계)", AFTER: "수확 후 · 후작(6단계)"}
DONT_KNOW = "[아직 모릅니다 — 기준이 없습니다]"
LEAF_SCENE = "수확 직전 전경 + 수확물 근접"


def _seed(on: bool = True) -> None:
    if on:
        parcels.set_fields("p001", use="종구 생산", overwrite=True)      # 격리 사본의 덮개에만(conftest)


def _ask(q: str, today: date) -> str:
    return chat.answer(subjects.by_id(SID), q, today)


def _env(did: str, today: date):
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == did)


# ── ① 입력 도착 ─────────────────────────────────────────────────────────────────────────────
def test_the_use_arrives_even_through_a_bare_subject():
    raw = subjects.by_id(SID)
    assert "use" not in raw, "전제부터 — 등록부의 재배 단위에는 용도가 없다(필지 값이다)"
    assert grid_schema.load_unit(raw)[0]["_use"] is None                     # 씨앗 필지는 「시험 재배(자가)」 — 종구가 아니다
    _seed()
    assert grid_schema.load_unit(raw)[0]["_use"] == "종구"                    # 날 재배 단위로도 도착한다(촬영 안내 · 몰 · 달력 끝 줄이 이 길로 읽는다)
    assert grid_schema.load_unit(dict(raw, use="시험 재배(자가)"))[0]["_use"] is None   # 붙어 있으면 그것이 이긴다(판정 회차가 붙여 넘긴 값)


# ── ② 문은 키 단위 ──────────────────────────────────────────────────────────────────────────
def _unit_with(overrides: dict) -> dict:
    base = grid_schema.load(grid_schema.unit_path("jjokpa_autumn"))
    u = copy.deepcopy(base)
    s5 = next(s for s in u["stages"] if s["order"] == 5)
    s5[grid_schema.BY_USE_KEY] = {"종구": {"source": "검사용 — 값이 온 키만 열리는지", **overrides}}
    return grid_schema.apply_use(u, "종구")


def test_the_gate_opens_only_the_keys_that_came():
    s5_leaf = next(s for s in grid_schema.load(grid_schema.unit_path("jjokpa_autumn"))["stages"] if s["order"] == 5)
    u = _unit_with({"window": dict(s5_leaf["window"])})                      # 창 값만 왔다
    s5, s4 = (next(s for s in u["stages"] if s["order"] == o) for o in (5, 4))
    assert not grid_schema.use_gap(u, s5, ("window",))                        # 수확 때는 연다
    for keys in (("risks", "window"), grid_capture.CAPTURE_KEYS, ("water", grid_schema.DROUGHT_RULES_KEY), ("tasks",)):
        assert grid_schema.use_gap(u, s5, keys), keys                         # 안 온 키는 따라 열리지 않는다(칸 단위 문이면 다 열렸다)
        assert not grid_schema.use_gap(u, s4, keys), keys                     # 수확 칸 앞은 용도와 무관
    assert not grid_schema.use_gap(grid_schema.apply_use(grid_schema.load(grid_schema.unit_path("jjokpa_autumn")), None), s5, ("window",))
    for bad in ((), ("bogus",)):
        with pytest.raises(ValueError):
            grid_schema.use_gap(u, s5, bad)                                   # 키를 빼먹거나 모르는 키면 부르지 못한다


def test_the_gate_holds_for_partial_values_found_in_review(monkeypatch):
    """[2026-10-14 적대 검토 — 확인 셋] ① 약 · 물은 오늘 칸을 **기간**으로 고른다 — 할 일 값만 온 칸에서 잎 기간으로 그 값을 읽으면 다른 날의 값이다(window 도 연다)
    ② 문의 시작 칸은 잎 격자의 수확 칸 — by_use 가 decisions 를 덮어쓰면 합친 격자에 수확 칸이 사라져 문 전체가 꺼졌다
    ③ 할 일 값만 온 칸의 촬영 줄은 문에 걸려 빠지는데 계획 대 실제가 말하지 않았다."""
    from judge import plan
    s5_leaf = next(s for s in grid_schema.load(grid_schema.unit_path("jjokpa_autumn"))["stages"] if s["order"] == 5)
    u = _unit_with({"tasks": list(s5_leaf["tasks"])})                          # 할 일만 왔다(기간은 잎)
    s5 = next(s for s in u["stages"] if s["order"] == 5)
    assert plan.use_gapped(u, s5) and not grid_schema.use_gap(u, s5, plan.TASK_KEYS)          # ③ 할 일은 열리고 촬영 줄이 빠졌다 — 그 사실이 계획 대 실제에 실린다
    u2 = _unit_with({"decisions": ["ship_or_store"]})                         # ② 수확 시기 결정을 덮어써 뺀 칸
    s6 = next(s for s in u2["stages"] if s["order"] == 6)
    assert grid_schema.harvest_order(u2) is None and grid_schema.use_gap(u2, s6, ("risks", "window"))
    real = grid_schema.load

    def tasks_only(p):                                                        # ① 실제 판정기 자리 — 유기 자재는 할 일 값만으로 열리지 않는다
        x = real(p)
        if Path(p).name == grid_schema.unit_path("jjokpa_autumn").name:
            st = next(s for s in x["stages"] if s["order"] == 5)
            st[grid_schema.BY_USE_KEY] = {"종구": {"source": "검사용", "tasks": list(s5_leaf["tasks"])}}
        return x

    monkeypatch.setattr(grid_schema, "load", tasks_only)
    _seed()
    assert _env("material_citation", HARVEST).kind == "판단 불가(지식)"
    assert "5. 수확" in _env("plan_vs_actual", HARVEST).result["use_gap_stages"]        # ③ 실제 판정기에서도


def test_every_gate_call_names_its_keys():
    """부르는 곳 **전부**가 읽는 키를 넘긴다 — 시그니처가 강제하지만 위치 인자 둘로 부르는 옛 꼴이 남아 있으면 여기서 보인다(래칫은 호출형까지 · 인자 표현식은 안 본다)."""
    calls = []
    for p in sorted([*ROOT.glob("judge/*.py"), *ROOT.glob("grid/*.py"), *ROOT.glob("mall/*.py"), *ROOT.glob("ingest/*.py"), *ROOT.glob("frontend/*.py")]):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", None)) == "use_gap":
                calls.append((p.name, n.lineno, len(n.args) + len(n.keywords)))
    assert len(calls) >= 9, calls                                             # 수확 · 위험(둘) · 계획표(둘) · 계획 대 실제(둘) · 가뭄(둘) · 약 · 촬영(둘) — 줄면 문이 빠진 것이다
    assert all(k == 3 for _f, _l, k in calls), [c for c in calls if c[2] != 3]


def test_the_seed_value_reaches_a_bare_subject_reader(monkeypatch):
    """값이 오면 날 재배 단위로 읽는 자리(촬영 안내)도 그 값을 읽는다 — 문이 섰는지와 **입력이 도착하는지**는 다른 검사다."""
    real = grid_schema.load
    s5_leaf = next(s for s in real(grid_schema.unit_path("jjokpa_autumn"))["stages"] if s["order"] == 5)

    def with_seed(p):
        u = real(p)
        if Path(p).name == grid_schema.unit_path("jjokpa_autumn").name:
            s5 = next(s for s in u["stages"] if s["order"] == 5)
            s5[grid_schema.BY_USE_KEY] = {"종구": {"source": "검사용", "window": dict(s5_leaf["window"]),
                                                   "capture": {"shoot": True, "scene": "검사용 종구 장면"}}}
        return u

    monkeypatch.setattr(grid_schema, "load", with_seed)
    _seed()
    h = grid_capture.hint_for(subjects.by_id(SID), HARVEST)
    assert h["scene"] == "검사용 종구 장면" and h["shoot"] is True and "use_gap_use" not in h, h
    assert _env("drought_alert", HARVEST).kind == "판단 불가(지식)"            # 물 값은 안 왔다 — 그 문은 그대로 닫혀 있다


def test_the_observation_fetch_sees_the_same_gate(monkeypatch):
    """[주입 H 미적발 → 추가] 관측을 며칠치 부를지(judge.run.drought_days_needed)도 같은 문을 본다 — 지금 수확 칸의 잎 임계는 N/A 라 문이 없어도 0 이 나와
    가려졌다(가드가 다른 사실에 가린다 · §7.1 1번). 잎 임계가 수에 있는 칸으로 만들어 잰다(양방향: 용도가 없으면 그 날수를 부른다)."""
    real = grid_schema.load

    def with_leaf_threshold(p):
        u = real(p)
        if Path(p).name == grid_schema.unit_path("jjokpa_autumn").name:
            s5 = next(s for s in u["stages"] if s["order"] == 5)
            s5[grid_schema.DROUGHT_RULES_KEY] = {"dry_days": 9, "source": "검사용 — 잎 기준 임계가 수인 칸"}
        return u

    monkeypatch.setattr(grid_schema, "load", with_leaf_threshold)
    assert judge_run.drought_days_needed(subjects.by_id(SID), HARVEST) == 9          # 잎 수확 — 임계 날수만큼 부른다
    _seed()
    assert judge_run.drought_days_needed(subjects.by_id(SID), HARVEST) == 0          # 종구 — 판정기가 관측 전에 「기준이 없습니다」 로 간다(부르지 않는다)


# ── ③ 같은 날 같은 칸 · 같은 말 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("today", [HARVEST, AFTER])
def test_every_answer_on_the_gapped_stage_says_the_same_thing(today):
    plain = {q: _ask(q, today) for q in ("물 줘야 하나", "약 뭐 쳐요")}
    assert all("이번엔 할 일이 아닙니다" in a for a in plain.values()), plain     # 대조군 — 용도가 없으면 잎 기준 답 그대로(D-22 · 수확 후 칸 N/A)
    _seed()
    for q in ("물 줘야 하나", "약 뭐 쳐요", "위험한 거 있나", "서리 오나", "병충해 뭐 봐야 하나"):
        a = _ask(q, today)
        # 위험은 보는 칸에 더해 지난 수확 칸도 안 낸 칸으로 말한다(수확 후 칸 날에는 둘) — 오늘 칸이 그 안에 있는지를 본다
        assert a.startswith(DONT_KNOW) and "재배 달력의 " in a and WHERE[today] in a and "잎 수확 기준으로는 말하지 않습니다" in a, (q, a[:160])
        assert "이번엔 할 일이 아닙니다" not in a and "지금 창에 경보 없음" not in a, (q, a[:160])
    assert "종구 재배의 수확 때는 재배 달력에 아직 없습니다" in _ask("수확 언제 해요", today)


def test_the_withheld_judgment_says_it_once():
    """머리가 말했으면 꼬리를 또 붙이지 않는다 — 한 답에 「기준이 오면」 은 한 번."""
    _seed()
    for q in ("물 줘야 하나", "약 뭐 쳐요", "위험한 거 있나"):
        assert _ask(q, HARVEST).count("기준이 오면") == 1, q


# ── ④ 촬영 안내 셋 ─────────────────────────────────────────────────────────────────────────
def test_no_capture_guide_shows_the_leaf_scene_under_the_seed_use(monkeypatch):
    monkeypatch.setenv("AGRODSS_TODAY", HARVEST.isoformat())
    s = subjects.by_id(SID)
    assert LEAF_SCENE in grid_capture.hint_for(s, HARVEST)["scene"]          # 대조군 — 용도가 없으면 잎 수확 장면
    _seed()
    h = grid_capture.hint_for(s, HARVEST)
    assert h["shoot"] is None and h["use_gap_use"] == "종구" and not h["scene"], h      # None — 「안 찍는 칸」(False)과 다른 사실이다
    said = words.capture_said(h)
    assert said.startswith("종구 재배의 찍을 장면 기준은 재배 달력의 수확(5단계)에 아직 없습니다"), said
    side = chat_pages.thread_panel(s, HARVEST)
    _code, media_html = serve.media_page()
    view = product.product_view(SID, today=HARVEST)
    mall = chat_pages.mall_main(view)
    for page in (side, media_html, mall):
        assert said in page and LEAF_SCENE not in page, page[:200]
    row = next(t for t in view["timeline"] if t["stage"].startswith("5."))
    assert row["state"] == product.GAP_STATE and not row["scene"] and not row["window"], row
    product.assert_public(view)                                              # 소비자 쪽 경계는 그대로


def test_the_side_card_never_prints_a_python_value(monkeypatch):
    """W-06 — 안 찍는 칸(수확 후)과 달력 밖에서 「False」 · 「None」 이 찍혔다. 갈래 문장은 4층 하나."""
    s = subjects.by_id(SID)
    for today, want in ((AFTER, "이 단계는 찍는 단계가 아닙니다"), (PAST, "재배 달력이 끝나 찍을 단계가 없습니다")):
        side = chat_pages.thread_panel(s, today)
        card = side[side.index("찍을 장면"):][:300]
        card = card[:card.index("</div></div>")]
        assert want in card and "False" not in card and "None" not in card, (today, card)


# ── ⑤ 위험 ────────────────────────────────────────────────────────────────────────────────
def test_risk_withheld_whole_or_in_part():
    _seed()
    whole = _env("risk_alert", HARVEST)
    assert whole.kind == "판단 불가(지식)" and whole.result["use_gap_stages"] == ["5. 수확"], (whole.kind, whole.result)
    part = _env("risk_alert", MIDDLE)
    assert part.kind == "판단함" and part.result["use_gap_stages"] == ["5. 수확"] and part.result["alerts"]   # 생육 중기 칸은 본다(과습은 용도와 무관)
    # 경보가 없고 일부만 안 봤으면 본 칸만 이름을 부른다 — 「지금 창에 경보 없음」 은 안 본 칸까지 없다고 말한다
    quiet = type(part)("판단함", "risk_alert", SID, part.as_of, grade="추정", revisit_at=part.revisit_at,
                       result={"alerts": [], "stages": ["4. 생육 중기 · 비대", "5. 수확"], "use_gap_stages": ["5. 수확"], "use_gap_use": "종구"})
    said = chat.summarize_envelope(quiet)
    assert "생육 중기 · 비대(4단계)에는 경보 없음" in said and "지금 창에 경보 없음" not in said and said.count("기준이 오면") == 1, said
    plain = type(part)("판단함", "risk_alert", SID, part.as_of, grade="추정", revisit_at=part.revisit_at, result={"alerts": [], "stages": ["4. 생육 중기 · 비대"]})
    assert "지금 창에 경보 없음" in chat.summarize_envelope(plain)            # 용도가 없으면 전과 같다


def test_the_harvest_delay_that_was_not_raised_is_said():
    """달력 끝 뒤 — 용도 없이는 「수확 지연」 경보 · 용도가 있으면 그 경보를 **안 냈다**고 말한다(전에는 말없이 빠져 「경보 없음」)."""
    assert "수확 지연" in _ask("위험한 거 있나", PAST)
    _seed()
    a = _ask("위험한 거 있나", PAST)
    assert "재배 달력에 지금 볼 단계가 없습니다" in a and "수확(5단계)에 아직 없어 그 칸의 위험은 내지 않습니다" in a and "지금 창에 경보 없음" not in a, a[:300]
    assert _env("risk_alert", AFTER).result["use_gap_stages"] == ["5. 수확", "6. 수확 후 · 후작"]   # 지난 수확 칸과 보는 칸 — 달력 순서로


def test_the_stage_card_does_not_point_at_an_empty_place():
    """병해충 · 배수 카드는 위험 경보를 칸으로 잘라 낸다 — 그 칸을 안 볼 때 「그 칸의 위험은 「위험 경보」 에 전부 있습니다」 라고 했는데, 용도 기준이 없어
    안 낸 칸이면 거기 가도 없다. 달력이 끝난 날은 「없음 칸을 봅니다」 였다(W-24)."""
    assert "「위험 경보」 에 전부 있습니다" in _env("pest_alert", MIDDLE).result["summary"]          # 대조군
    assert "재배 달력에 볼 칸이 더 없습니다" in _env("drainage_alert", PAST).result["summary"]
    assert "없음 칸" not in _ask("배수 괜찮나", PAST)
    _seed()
    mid = _env("pest_alert", MIDDLE)
    assert "「위험 경보」 에 있습니다" in mid.result["summary"] and "전부" not in mid.result["summary"], mid.result["summary"]
    for today in (HARVEST, PAST):
        e = _env("drainage_alert", today)
        assert e.kind == "해당 없음" and "「위험 경보」" not in e.result["summary"] and e.result["use_gap_stages"], (today, e.result)
        assert "아직 없어 그 칸의 위험은 내지 않습니다" in _ask("배수 괜찮나", today)


def test_the_stage_cards_see_what_the_risk_alert_sees():
    """[2026-10-14 검토] 칸 카드 둘은 위험 경보를 칸으로 잘라 낸다 — ① 사건 원장을 안 받아 수확을 넣은 뒤에도 카드만 「수확 칸의 위험은 안 냈다」 를 말했고
    ② 제 칸을 볼 때도 다른 칸의 용도 메모를 실어 이 카드가 용도를 읽는 것처럼 셌다(「넣으면 다시 답합니다」 가 안 바뀌는 카드 답에 붙을 자리)."""
    _seed()
    risk_mid, drain_mid = _env("risk_alert", MIDDLE), _env("drainage_alert", MIDDLE)
    assert any(n.startswith("용도 '") for n in risk_mid.notes) and not any(n.startswith("용도 '") for n in drain_mid.notes), drain_mid.notes
    chat.ev.add_event(SID, "수확", "2026-11-02")                                 # 수확을 넣었다 — 수확 지연은 이제 사실이 아니다(B1)
    risk_past, drain_past = _env("risk_alert", PAST), _env("drainage_alert", PAST)
    assert risk_past.result.get("use_gap_stages") == [] == drain_past.result.get("use_gap_stages"), (risk_past.result, drain_past.result)


# ── ⑥ 「누르면 판단이 읽습니다」 는 잰 것만 ────────────────────────────────────────────────────
def _draft(said: str, today: date) -> dict:
    m, _r = chat.send(SID, said, today=today, now=datetime(today.year, today.month, today.day, 9, tzinfo=timezone.utc))
    assert any(d["kind"] == "event" for d in m["drafts"]), (said, m["drafts"])
    return m


def test_the_face_ignores_the_tally_and_the_clock_but_nothing_else():
    """「판단이 읽는다」 의 잣대 — 읽은 기록 **수**와 낸 시각만 빼고 나머지는 다 센다(장부를 읽음으로 세던 W-19 오측정 · 근거에만 실리는 값도 놓치지 않는다)."""
    e = _env("plan_vs_actual", MIDDLE)
    tally = type(e)(e.kind, e.decision_id, e.subject, "2099-01-01T00:00:00+00:00", inputs=list(e.inputs), grade=e.grade, revisit_at=e.revisit_at,
                    result={**e.result, **{k: 999 for k in COUNTERS}}, notes=list(e.notes))
    assert reading_face(tally) == reading_face(e)                               # 셈 · 시각만 다르면 같은 판단
    moved = type(e)(e.kind, e.decision_id, e.subject, e.as_of, inputs=list(e.inputs), grade=e.grade, revisit_at=e.revisit_at,
                    result=dict(e.result), notes=[*e.notes, "근거에만 실린 값"])
    assert reading_face(moved) != reading_face(e)                               # 메모 · 근거에만 실려도 판단이 바뀐 것이다
    assert set(COUNTERS) <= set(e.result), sorted(e.result)                     # 그 셈들이 실제로 봉투에 있다(없는 키를 빼는 헛 잣대가 아니다)


def test_the_press_promise_is_made_only_when_the_answer_moves():
    """씨앗 용도 · 수확 칸 · 수확 초안 — 넣어도 할 일 답이 안 바뀐다(수확 칸 할 일이 없다). 반대로 09-20 · 웃거름 초안은 바뀐다(아래).
    까닭 절(「그 날이 든 수확(5단계)에는 … 기준이 아직 없어」)은 **잰 까닭**일 때만 — 잎 기준에서는 그 기록이 판단을 바꾸는 날(10-24 수확)."""
    T = date(2026, 10, 25)
    _seed()
    _draft("어제 수확했다", T)
    a = _ask("오늘 뭐 해야 하나", T)
    assert "누르면 판단이 읽습니다" not in a and "영농일지에 남지만, 그 날이 든 수확(5단계)에는 종구 재배 기준이 아직 없어" in a, a[-300:]
    look = _ask("수확 일지 보여줘", T)
    assert "일지에 들어가 이 조회에도 나옵니다" in look and "판단이 읽습니다" not in look, look


def test_the_reason_is_said_only_when_it_was_measured():
    """[2026-10-14 검토] 날이 안 본 칸에 든다고 그것이 까닭은 아니다 — 잎 기준에서도 그 기록이 판단을 안 바꾸면 「종구 기준이 없어서」 는 지은 까닭이다 — 일반 꼬리로 말한다.
    [W-15 2026-10-14 뒤] 첫 판의 예(10-19 수확 기록 — 계획 수확 줄과 안 이어졌다)는 W-15 를 고치자 **잎 기준에서 읽히는 기록**이 됐다(그래서 이제 까닭을 말한다 · 아래 둘째).
    잎 기준에서도 안 읽히는 수확 기록은 이제 **이미 이행된 줄 뒤의 기록**이다 — 수확 줄은 한 기록으로 이행이고 둘째 기록은 그 줄을 안 바꾼다."""
    T = date(2026, 10, 20)
    _seed()
    first = _draft("10월 15일에 수확했다", T)
    chat.confirm(first["id"], 0)
    _draft("어제 수확했다", T)
    a = _ask("오늘 뭐 해야 하나", T)
    assert "영농일지에 남고, 그 기록으로는 지금 답이 바뀌지 않습니다" in a and "기준이 아직 없어 기준이 오기 전에는" not in a, a[-300:]
    look = _ask("수확 일지 보여줘", T)
    assert "일지에 들어가 이 조회에도 나옵니다" in look and "판단이 읽습니다" not in look, look      # 조회는 판단이 아니다 — 잰 사실만(이 조회에 든다)


def test_a_harvest_record_in_the_first_week_is_read_by_the_leaf_answer():
    """[W-15 2026-10-14] 수확 칸 첫 주(10-19)의 수확 기록은 이제 잎 기준 계획에서 수확 줄을 이행으로 만든다 — 그래서 종구 용도에서 그 기록이 안 읽히는 까닭은
    **잰 까닭**이다(그 날이 든 수확 칸에 종구 기준이 없다). 전에는 잎 기준에서도 안 읽혀 일반 꼬리였다(위 검사의 첫 판 — W-15 그 자체)."""
    T = date(2026, 10, 20)
    _seed()
    _draft("어제 수확했다", T)
    a = _ask("오늘 뭐 해야 하나", T)
    assert "영농일지에 남지만, 그 날이 든 수확(5단계)에는 종구 재배 기준이 아직 없어" in a, a[-300:]


def test_the_reason_clause_is_said_only_for_days_in_a_withheld_stage():
    """[주입 e 미적발 → 추가] 「그 날이 든 수확(5단계)에는 … 기준이 아직 없어」 는 초안의 날이 **그 답이 안 본 칸**에 들 때만 — 생육 중기 칸 날의 기록에 그 까닭을
    대면 거짓이다(그 칸은 잎 기준대로 본다). 까닭을 못 대면 일반 꼬리(「그 기록으로는 지금 답이 바뀌지 않습니다」)."""
    _seed()
    env = _env("plan_vs_actual", date(2026, 10, 20))
    assert env.result["use_gap_stages"] == ["5. 수확", "6. 수확 후 · 후작"]
    assert chat._gapped_days(SID, [{"observed_at": "2026-10-18"}], env) == ["5. 수확"]
    assert chat._gapped_days(SID, [{"observed_at": "2026-10-10"}], env) is None                    # 4단계 날 — 까닭이 아니다
    assert chat._gapped_days(SID, [{"observed_at": "2026-10-18"}, {"observed_at": "2026-10-10"}], env) is None   # 하나라도 아니면 까닭을 대지 않는다
    assert "기준이 아직 없어" not in words.not_in_diary_many([("제초", 1)], "일지에 넣기", then="idle")          # 까닭 없이 부르면 일반 꼬리


def test_a_sowing_record_on_a_farm_without_a_planting_date_is_said_to_open_the_answer():
    """[2026-10-14 검토 — 높음] 넣기는 기록만 쓰는 것이 아니다: 심은 날이 없는 농사에 파종을 넣으면 심은 날이 선다(_confirm_locked → subjects.set_anchor).
    셈이 그것을 빼면 판단을 통째로 여는 기록에 「지금 답은 그대로」 라고 말한다. 셈과 실제 넣기를 둘 다 잰다."""
    T = date(2026, 9, 2)
    s2 = subjects.add(crop="쪽파", season="2027 가을", parcel="p001", status="계획")
    assert s2.get("grid_unit") and not s2.get("anchor"), s2                     # 전제 — 달력은 이어졌고 심은 날은 없다
    m, _r = chat.send(s2["id"], "어제 파종했다", today=T, now=datetime(T.year, T.month, T.day, 9, tzinfo=timezone.utc))
    assert any(d["kind"] == "event" and d.get("type") == "파종" for d in m["drafts"]), m["drafts"]
    a = chat.answer(subjects.by_id(s2["id"]), "오늘 뭐 해야 하나", T)
    assert "아직 일지에 넣지 않은 파종 기록 1건이 있습니다 — '일지에 넣기' 를 누르면 판단이 읽습니다" in a, a[-300:]
    before = reading_face(next(e for e in judge_run.judgments_for(s2["id"], today=T) if e.decision_id == "plan_vs_actual"))
    chat.confirm(m["id"], next(i for i, d in enumerate(m["drafts"]) if d["kind"] == "event"))
    after = reading_face(next(e for e in judge_run.judgments_for(s2["id"], today=T) if e.decision_id == "plan_vs_actual"))
    assert subjects.by_id(s2["id"]).get("anchor") and after != before                  # 실제로도 열렸다(셈과 같다)


def test_one_answer_fetches_each_outside_source_once(monkeypatch):
    """[2026-10-14 검토] 넣은 셈으로 다시 내는 회차가 바깥 원천(예찰 · 예보 …)을 **다시 불렀다** — 답 하나가 호출을 서너 배로 늘리고, 그 사이 원천이 달라지면
    「그 기록이 답을 바꾼다」 로 오측정한다. 한 답 안에서는 한 번(judge.run.same_sources) · 답 밖(판정 화면)은 부를 때마다(양방향)."""
    from ingest import ncpms
    calls = []
    monkeypatch.setattr(ncpms, "api_key", lambda: "검사용")
    monkeypatch.setattr(ncpms, "fetch_forecast", lambda crop, year=None: calls.append(crop) or {"status": "error", "message": "검사용 — 원천 없음"})
    T = date(2026, 9, 20)
    for said in ("어제 웃거름 줬다", "어제 물 줬다"):
        _draft(said, T)                                                           # 보내기도 답한다 — 한 번씩
    assert len(calls) == 2, calls
    calls.clear()
    _ask("오늘 뭐 해야 하나", T)                                                 # 본 답 + 답할 수 있는 것 + 넣은 셈(둘) — 판정을 네 번 넘게 돌린다
    assert len(calls) == 1, calls
    calls.clear()
    judge_run.judgments_for(SID, today=T)
    judge_run.judgments_for(SID, today=T)
    assert len(calls) == 2, calls                                                 # 답 밖에서는 그대로 부른다(낡은 원천을 붙들지 않는다)


def test_the_promise_still_stands_where_it_is_true():
    T = date(2026, 9, 20)
    _draft("어제 웃거름 줬다", T)
    a = _ask("웃거름 언제 줘요", T)
    assert "아직 일지에 넣지 않은 시비 기록 1건이 있습니다 — '일지에 넣기' 를 누르면 판단이 읽습니다" in a, a[-300:]


@pytest.mark.parametrize("use,today,said,did", [(False, date(2026, 9, 20), "어제 웃거름 줬다", "top_dressing_1"),
                                                (True, date(2026, 10, 20), "10월 18일에 수확했다", "plan_vs_actual")])
def test_the_counterfactual_is_what_confirming_does(use, today, said, did):
    """도구 검증 — 넣은 셈(원장에 안 씀)으로 낸 판단이 **실제로 넣은 뒤**의 판단과 같은 답을 낸다(양방향: 바뀌는 쪽 · 안 바뀌는 쪽)."""
    _seed(use)
    m = _draft(said, today)
    env = _env(did, today)
    drafts = [d for d in m["drafts"] if d["kind"] == "event"]
    guessed = chat._answer_moves(SID, did, drafts, today, env)
    before = reading_face(env)
    assert not [r for r in chat.ev.list_records(SID, "event")], "셈하는 동안 원장에 썼다"
    for i, d in enumerate(m["drafts"]):
        if d["kind"] == "event":
            chat.confirm(m["id"], i)
    really = reading_face(_env(did, today)) != before
    assert guessed is really is (not use), (guessed, really)


WAIT_SAID = "이 답은 용도 값 없이 낸 것입니다"


def _declared() -> None:
    """발행자 PC 상태 — 일지가 「종구생산을 위한 목적이다」 를 말하고 밭 정보 용도는 아직 「시험 재배(자가)」(카드가 기다린다)."""
    chat.ev.add_observation(SID, "종구생산을 위한 목적이다", "2026-10-04")


def test_the_waiting_value_line_is_said_only_where_the_value_moves_the_answer():
    """[W-19 값 쪽 · 처방 직후 전수] 용도를 읽는 판단이 여덟이 되자(날 넷의 합) 「이 답은 용도 값 없이 낸 것입니다 — … 넣으면 다시 답합니다」 가 그 값으로 **오늘은 안 바뀌는**
    답(10-08 의 물 답 · 생육 중기 칸)에도 붙을 자리가 생겼다. 넣은 셈으로 다시 내 보고 바뀔 때만 붙는다(양방향)."""
    _declared()
    early = date(2026, 10, 8)
    assert WAIT_SAID in _ask("수확 언제 해요", early)                         # 수확 때는 그 날도 바뀐다
    assert WAIT_SAID not in _ask("물 줘야 하나", early)                        # 생육 중기 칸 — 넣어도 물 답은 그대로
    assert WAIT_SAID in _ask("물 줘야 하나", HARVEST)                          # 수확 칸 — 넣으면 「기준이 없습니다」 로 바뀐다


@pytest.mark.parametrize("today,moves", [(date(2026, 10, 8), False), (HARVEST, True)])
def test_the_value_counterfactual_is_what_putting_it_in_does(today, moves):
    """도구 검증 — 넣은 셈(등록부에 안 씀)이 실제로 넣은 뒤와 같은 답을 낸다(바뀌는 날 · 안 바뀌는 날)."""
    _declared()
    env = _env("drought_alert", today)
    guessed = chat._value_moves(subjects.by_id(SID), "drought_alert", "use", "종구 생산", today, env)
    assert parcels.by_id("p001").get("use") == "시험 재배(자가)", "셈하는 동안 등록부에 썼다"
    before = reading_face(env)
    _seed()
    really = reading_face(_env("drought_alert", today)) != before
    assert guessed is really is moves, (guessed, really)


# ── ⑦ 조사 ────────────────────────────────────────────────────────────────────────────────
def test_the_grid_cell_word_takes_its_own_particle():
    assert words.plain("기준점 후 91일에 열린 격자 칸이 없다") == "심은 날 후 91일에 열린 재배 달력 단계가 없다"
    a = _ask("물 줘야 하나", PAST)
    assert "단계가 없다" in a and "단계이" not in a, a[:120]
