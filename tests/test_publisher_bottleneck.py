# -*- coding: utf-8 -*-
# [WO-PB-01 2026-09-29] 발행자 응답 병목 측정 — 지시서 §8 의 검사 넷 + 전수 래칫 + 문서 동기.
# ① P2 판정에 원천·경로가 없으면 P4 로 떨어진다 ② 미도달 원천은 "없음" 이 아니라 "미확인" 으로 기록된다
# ③ 이 작업이 격자·원장·대장 파일을 수정하지 않는다 ④ 대기 항목 수가 이 작업으로 줄지 않는다(측정일 뿐).
# 거부와 통과를 둘 다 본다(§7.1 — 막는 것을 검사하면 통과하는 것도 검사한다).
from __future__ import annotations

import hashlib
import re
import urllib.error
from datetime import date
from pathlib import Path

import pytest

from scripts import measure_publisher_bottleneck as pb

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 9, 29)


def _item(**kw) -> pb.Item:
    base = dict(id="X-1", ask="물음", since=date(2026, 9, 18), blocker="답", branch="P1", why="근거")
    base.update(kw)
    return pb.Item(**base)


def _tree_hash(*paths: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paths:
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file())
        for f in files:
            out[f.as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


# ── ① 갈래 규칙(§3) — 거부와 통과 ──
def test_a_p2_without_source_or_path_falls_to_p4_and_p3_without_a_place_falls_to_p1():
    ok = pb.classify(_item(branch="P2", source="농사로", path="nongsaro.go.kr → 쪽파"))
    assert ok.branch == "P2" and ok.fell == ""                                  # 통과 — 둘 다 있으면 P2 로 남는다
    for kw in (dict(source="", path="어딘가"), dict(source="농사로", path=""), dict(source=" ", path=" ")):
        fell = pb.classify(_item(branch="P2", **kw))
        assert fell.branch == "P4" and "P4" in fell.fell and "원천·경로" in fell.fell   # 거부 — "어딘가 있을 것" 은 P2 가 아니다
    assert pb.classify(_item(branch="P3", path="grid/capture.py")).branch == "P3"
    p3 = pb.classify(_item(branch="P3", path=""))
    assert p3.branch == "P1" and "P1" in p3.fell                                # 갈리면 사람 쪽
    with pytest.raises(ValueError):
        pb.classify(_item(branch="P5"))


def test_the_report_carries_a_source_and_a_path_on_every_p2_row_and_marks_a_fallen_row():
    doc = pb.DOC_PATH.read_text(encoding="utf-8")
    rows = [l for l in doc.splitlines() if l.startswith("| ") and "**P" in l]
    assert rows, "전수표 행이 없다"
    for l in rows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        branch = re.search(r"\*\*(P[1-4])\*\*", cells[6]).group(1)
        if branch == "P2":
            assert " — " in cells[8] and len(cells[8]) > 10, f"P2 행에 원천·경로가 없다: {cells[0]}"
        if branch == "P3":
            assert cells[8].strip(), f"P3 행에 고칠 자리가 없다: {cells[0]}"
    # 실제 판정에서 규칙에 떨어진 행이 있으면 그 사유가 표에 남는다(지금은 0 — 떨어지면 보이게)
    fallen = [i for i in pb.judged(TODAY) if i.fell]
    for i in fallen:
        assert i.fell in doc


# ── ② 도달성(§4) — 없음이라는 상태가 없다 ──
def test_an_unreached_source_is_unconfirmed_never_absent_and_a_2xx_is_reached():
    for code, err in ((None, ""), (None, "URLError"), (403, "프록시 거부"), (404, "HTTP 404"), (500, ""), (0, "")):
        s = pb.reach_status(code, err)
        assert s.startswith(pb.UNREACHED) and "없음" not in s, (code, err, s)
    assert pb.reach_status(200).startswith(pb.REACHED) and pb.reach_status(302).startswith(pb.REACHED)
    assert pb.reach_status(404, "HTTP 404") != pb.reach_status(403, "프록시 거부")   # 사유는 남긴다(가르지는 않는다)


def test_the_report_reach_table_has_a_status_per_target_and_never_says_absent():
    doc = pb.DOC_PATH.read_text(encoding="utf-8")
    sec = doc[doc.index("## 3."):doc.index("## 4.")]
    rows = [l for l in sec.splitlines() if l.startswith("| ") and "`http" in l]
    assert len(rows) == len(pb.REACH_TARGETS)
    for l in rows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        assert cells[2].startswith(f"**{pb.UNREACHED}") or cells[2].startswith(f"**{pb.REACHED}"), cells
        assert "없음" not in cells[2]
    assert "측정 시점" in sec and pb.REACH_MEASURED_AT in sec                     # 시점 축 — 시점 없는 수치는 인상이 된다
    snap_urls = {u for u, _, _ in pb.REACH_SNAPSHOT}
    assert snap_urls == {u for _, u, _ in pb.REACH_TARGETS}


def test_probe_maps_every_error_to_unconfirmed_and_writes_nothing(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        if "403" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 403, "forbidden", {}, None)
        raise urllib.error.URLError("blocked")

    monkeypatch.setattr(pb.urllib.request, "urlopen", fake_urlopen)
    before = _tree_hash(ROOT / "data", pb.BACKLOG)
    out = pb.probe(["http://x/403", "http://x/other"], timeout=1)
    assert [c for _, c, _ in out] == [403, None]
    assert all(pb.reach_status(c, e).startswith(pb.UNREACHED) for _, c, e in out)
    assert pb.main(["--probe"]) == 0 and len(calls) == 2 + len(pb.REACH_TARGETS)
    assert _tree_hash(ROOT / "data", pb.BACKLOG) == before


# ── ③ ④ 바이트 불변 · 대기 수 불변 ──
def test_generating_the_report_leaves_grid_ledgers_and_backlog_untouched(tmp_path):
    before = _tree_hash(ROOT / "data", pb.BACKLOG, pb.REVIEW)
    n_before = len(pb.open_backlog_rows(pb.BACKLOG.read_text(encoding="utf-8")))
    out = tmp_path / "r.md"
    assert pb.main([str(out), "--today", TODAY.isoformat()]) == 0
    assert out.exists() and "## 1. 대기 항목 전수표" in out.read_text(encoding="utf-8")
    assert _tree_hash(ROOT / "data", pb.BACKLOG, pb.REVIEW) == before, "측정이 격자·원장·대장을 바꿨다"
    assert len(pb.open_backlog_rows(pb.BACKLOG.read_text(encoding="utf-8"))) == n_before   # 대기 항목 수가 줄지 않는다(측정일 뿐)
    assert n_before >= 1


# ── 전수 래칫 — 대장이 바뀌면 판정을 다시 한다 ──
def test_every_open_backlog_row_is_judged_and_a_new_open_row_breaks_the_build():
    text = pb.BACKLOG.read_text(encoding="utf-8")
    rows = pb.open_backlog_rows(text)
    judged_ids = {i.id for i in pb.judged(TODAY, text) if i.group == "대장"}
    assert judged_ids == set(rows)
    assert all(v[1] in pb.OPEN_STATES for v in rows.values())
    assert all(v[2] is not None for v in rows.values()), "등재일 없는 열린 행"
    injected = text + "\n| D-99 | 가짜 물음 | 0 | 대기 | 09-29 | 근거 | |\n"
    with pytest.raises(SystemExit, match="D-99"):
        pb.judged(TODAY, injected)
    closed = text.replace("| D-16 |", "| D-16x |", 1)                            # 열린 행이 사라져도 어긋난다(닫혔으면 판정에서 뺀다)
    with pytest.raises(SystemExit, match="D-16"):
        pb.judged(TODAY, closed)


def test_open_rows_take_the_status_cell_not_a_word_in_the_text():
    txt = "| ID | 항목 | 단계 | 상태 | 등재 |\n|---|---|---|---|---|\n| D-1 | 대기 중인 것을 등재하자 | 0 | 완료 | 09-18 |\n| D-2 | 물음 | 0 | **등재(발행자) · 남은 것** | 09-20 |\n| D-3 | 물음 | 0 | 보류 | 09-21 |\n"
    rows = pb.open_backlog_rows(txt)
    assert set(rows) == {"D-2"} and rows["D-2"][1] == "등재" and rows["D-2"][2] == date(2026, 9, 20)


# ── §5 판정 ──
def test_the_verdict_follows_section_5_with_p2_p3_first_on_overlap():
    def c(p1, p2, p3, p4):
        return {"P1": (p1, p1), "P2": (p2, p2), "P3": (p3, p3), "P4": (p4, p4)}
    assert pb.verdict(c(4, 6, 0, 0))[0] == "H1"                # 60% 정확히
    assert pb.verdict(c(6, 4, 0, 0))[0] == "H2"
    assert pb.verdict(c(0, 0, 4, 6))[0] == "H3"
    assert pb.verdict(c(5, 5, 0, 0))[0] == "판정 조건 미충족"  # 50/50 — 과반도 60% 도 아니다
    assert pb.verdict(c(2, 2, 2, 2))[0] == "판정 조건 미충족"
    assert pb.verdict({"P1": (0, 0), "P2": (0, 0), "P3": (0, 0), "P4": (0, 0)})[0] == "판정 조건 미충족"


# ── 문서 동기 — 문서는 생성물이다(기준일 고정) ──
def test_the_doc_is_the_generator_output_for_its_stated_day():
    doc = pb.DOC_PATH.read_text(encoding="utf-8")
    m = re.search(r"기준일 \*\*(\d{4}-\d{2}-\d{2})\*\*", doc)
    assert m, "문서 머리에 기준일이 없다"
    assert pb.render(date.fromisoformat(m.group(1))) == doc, "문서가 생성기 출력과 다르다 — 손으로 고쳤거나 다시 생성하지 않았다"
    for word in ("## 0. 요약", "## 2. 갈래 비율", "## 3. P2 도달성", "## 5. 다음 한 수 하나", "## 6. 격자 · 원장 바이트 불변"):
        assert word in doc


def test_the_summary_states_the_verdict_and_the_long_open_count():
    items = pb.judged(TODAY)
    c = pb.counts(items)
    h, _ = pb.verdict(c)
    doc = pb.DOC_PATH.read_text(encoding="utf-8")
    assert f"판정: **{h}**" in doc
    assert f"30일 초과: **{len(pb.long_open(items, TODAY))}건**" in doc
    assert sum(v[1] for v in c.values()) == sum(i.n for i in items)
