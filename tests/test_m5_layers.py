# -*- coding: utf-8 -*-
# [M-5] 층 구조 + 출력 규칙 — 마일스톤 1-3 의 다섯 조건을 **한 관문**에서 본다.
#   ① 1층 진입 3요건  ② 영상=1층/판독=2층(§6-2)  ③ 3층 산출 8종  ④ 4층 격리  ⑤ H 3조건(G1·G2·G3)
#   각 조건은 I-1·I-3·I-5·M-10·M-11 에서 따로 만들어졌다. 여기서는 그 조각이 **함께** 서 있는가를 실제 등록부 위에서 잰다
#   (낡음 대조 2026-09-19: 마일스톤 문서는 "종이 위에서 끝난다"고 했으나 코드가 먼저 닫았다 — docs/m5_layers.md).
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from ingest import media
from judge import envelope as E
from judge import harvest_timing as H
from judge import plan_vs_actual as PVA
from judge import registry as R
from judge import run
from mall import product as mall
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 9, 19)
LAYER1 = ("1층 사실", "1층 계획")
TIME_FIELDS = ("observed_at", "work_date", "target_date")     # 시각 — 사실은 관측 시각, 계획은 계획일(실측 2026-09-19: plan.* 3종)


def _envelopes() -> list[E.Envelope]:
    return [e for _, envs, _ in run.all_judgments(TODAY) for e in envs]


def _keys(obj, acc: set[str]) -> set[str]:
    if isinstance(obj, dict):
        acc |= set(obj)
        for v in obj.values():
            _keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, acc)
    return acc


# ── ① 1층 진입 3요건 ──────────────────────────────────────────────────────────────
def test_every_layer1_kind_requires_time_source_resolution():
    layer1 = {n: k for n, k in sch.KINDS.items() if k.layer in LAYER1}
    assert layer1, "1층 kind 가 하나도 없다"
    short = {}
    for n, k in layer1.items():
        miss = [f for f in ("source", "resolution") if f not in k.required]
        if not any(t in k.required for t in TIME_FIELDS):
            miss.append("시각(observed_at|work_date|target_date)")
        if miss:
            short[n] = miss
    assert not short, short


# ── ② 영상은 1층 사실, 판독은 2층 — 판독값은 3층의 축이 아니다 (§6-2) ────────────────
def test_video_is_fact_only_and_no_reading_axis_reaches_layer3():
    for name in ("observation.video", "observation.image"):
        k = sch.KINDS[name]
        assert k.layer == "1층 사실"
        # 파일 + 시각 + 필지(subject) + 해상도뿐 — 판독(생육 상태 · 병징)을 담는 칸이 없다
        assert not {f for f in k.required + k.optional if re.search(r"reading|symptom|state|stage|판독|병징", f)}, name
    axes = set()
    for d in R.all_decisions().values():
        axes |= set(d.required_axes) | set(d.optional_axes)
    assert not {a for a in axes if re.search(r"video|image|reading|vision", a)}, axes
    # 계획 대 실제는 영상을 "찍었는가(시각)" 로만 쓴다 — 내용을 읽지 않는다
    src = Path(PVA.__file__).read_text(encoding="utf-8")
    blk = src[src.index('p["kind"] == "plan.capture"'):]
    blk = blk[:blk.index("else:")]
    assert set(re.findall(r"v\.get\(\"(\w+)\"", blk)) | set(re.findall(r"hit\[0\]\.get\('(\w+)'", blk)) <= {"observed_at", "id"}, blk


# ── ③ 3층 산출 8종 — 코드와 I-1 문서가 같은 목록 ─────────────────────────────────────
def test_eight_output_kinds_match_i1_doc():
    doc = (ROOT / "docs" / "i1_outputs.md").read_text(encoding="utf-8")
    listed = re.findall(r"^### 2-\d\. (.+?)\s*$", doc, re.M)
    norm = lambda s: re.sub(r"—(.+)$", r"(\1)", re.sub(r"\s", "", s))     # "판단 불가 — 데이터" ≡ "판단 불가(데이터)"
    assert len(E.KINDS) == 8 and len(listed) == 8, (E.KINDS, listed)
    assert [norm(x) for x in listed] == [norm(x) for x in E.KINDS], (listed, E.KINDS)


# ── ④ 4층 격리 — 봉투는 이름만 싣는다, 값은 안 싣는다 ───────────────────────────────
def test_envelopes_carry_axis_names_not_values_on_real_registry():
    envs = _envelopes()
    assert envs, "등록부에 판정 대상이 없다"
    assert set(E.AxisUse.__dataclass_fields__) == {"axis", "observed_at", "source", "resolution", "grade"}
    found = _keys([e.to_dict() for e in envs], set())
    assert not (found & mall.FORBIDDEN_KEYS), found & mall.FORBIDDEN_KEYS
    assert all(a.source and a.resolution for e in envs for a in e.inputs)


# ── ⑤ H 3조건 ──────────────────────────────────────────────────────────────────────
def test_h_g1_no_sales_or_stock_field_in_layer3_subject():
    banned = re.compile(r"stock|inventory|order|demand|sales|revenue|재고|주문|판매량")
    assert not {f for f in sch.LAYER3_SUBJECT_FIELDS if banned.search(f)}
    assert not {f for n in sch.LAYER3_INPUT_KINDS for f in sch.KINDS[n].fields if banned.search(f)}


def test_h_g2_every_envelope_names_its_time_and_rule():
    for e in _envelopes():
        assert e.as_of, e.decision_id
        d = R.get(e.decision_id)
        assert d is not None and d.rule.strip(), e.decision_id            # 판정 기준이 등록부에 있다
        if e.kind == "판단함":
            assert e.grade in E.GRADES and e.inputs, e.decision_id       # 무엇을 언제 봤는지 없이 판단하지 않는다


def test_h_g3_gap_is_reported_not_filled():
    subj = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
    env = H.judge({**subj, "anchor": None}, today=TODAY)
    assert env.kind == "판단 불가(데이터)" and env.missing and all(m.get("who_can_fill") for m in env.missing)
    dumped = json.dumps(env.to_dict(), ensure_ascii=False)
    assert "window_start" not in dumped and "window_end" not in dumped   # 대리 기준점으로 창을 만들지 않는다
    for e in _envelopes():                                                 # missing 은 판단 불가(데이터)에서만
        assert bool(e.missing) == (e.kind == "판단 불가(데이터)"), e.decision_id
