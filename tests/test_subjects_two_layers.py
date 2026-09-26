# -*- coding: utf-8 -*-
# [U-24 2026-09-26] 재배 단위 등록부를 씨앗/덮개 **두 겹**으로 — 필지 등록부(U-18)와 같은 처방을 같은 형태의 파일에.
#
# 왜 — 추적 파일에 런타임이 쓰면 upstream 이 그 파일을 건드리는 순간 발행자 PC 의 pull 이 "commit or stash" 로 멈춘다.
# U-18 이 그것을 밟아 며칠치 옛 코드가 돌았고, 전수(2026-09-21)에서 subjects.json 이 같은 형태였다. 그동안은 `update.bat` 이
# 사본을 남기고 되돌려 지나갔지만 그러면 **농가가 추가한 재배 단위가 화면에서 사라진다**(사본에만 남는다).
#
# 거부와 통과를 둘 다 본다 — 씨앗에 안 쓰는가(거부) · 덮개가 읽힐 때 이기고 순서를 지키는가(통과) · 덮개가 없으면 씨앗 그대로인가(반대편).
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ingest import media, subjects
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent


def _seed() -> Path:
    return Path(os.environ["AGRODSS_SUBJECTS_PATH"])


def _local() -> Path:
    return Path(os.environ["AGRODSS_SUBJECTS_LOCAL_PATH"])


def test_adding_a_subject_writes_the_overlay_and_never_the_seed():
    before = _seed().read_bytes()
    assert not _local().exists()
    rec = subjects.add("쪽파", "2027 봄", status="계획")
    assert _seed().read_bytes() == before, "씨앗(추적 파일)에 썼다 — 발행자 pull 이 멈추는 형태"
    assert _local().exists()
    assert rec["id"] in {r["id"] for r in json.loads(_local().read_text(encoding="utf-8"))["subjects"]}
    assert subjects.by_id(rec["id"]) == rec                     # 읽으면 보인다 — 덮개가 목록에 든다


def test_changing_a_seed_row_keeps_the_seed_and_the_overlay_wins_in_place():
    sid = media.load_subjects()[0]["id"]
    n_seed = len(json.loads(_seed().read_text(encoding="utf-8"))["subjects"])
    before = _seed().read_bytes()
    subjects.set_status(sid, "종료", ended_at="2026-12-01")
    assert _seed().read_bytes() == before
    rows = media.load_subjects()
    assert rows[0]["id"] == sid and rows[0]["status"] == "종료" and rows[0]["ended_at"] == "2026-12-01"   # 자리를 지키고 덮개가 이긴다
    assert len(rows) == n_seed, "같은 id 를 두 번 셌다"
    subjects.set_anchor(sid, "2026-08-25", "파종(종구)")           # 두 번째 쓰기도 같은 줄을 바꾼다(덧붙이지 않는다)
    assert len(json.loads(_local().read_text(encoding="utf-8"))["subjects"]) == 1
    assert media.load_subjects()[0]["status"] == "재배 중"


def test_without_an_overlay_the_seed_is_exactly_what_you_get():
    """반대편 — 덮개가 없을 때 아무것도 지어내지 않는다."""
    assert not _local().exists()
    seed_rows = [sch.validate(s, kind="subject") for s in json.loads(_seed().read_text(encoding="utf-8"))["subjects"]]
    assert media.load_subjects() == seed_rows


def test_the_overlay_is_outside_git_and_is_the_only_write_path(monkeypatch, tmp_path):
    rel = "data/subjects_local.json"
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0, f"{rel} 이 git 안이다 — 다음 pull 이 또 멈춘다"
    assert rel not in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert subjects.path() == media.subjects_local_path() != media.subjects_path()
    monkeypatch.setenv("AGRODSS_SUBJECTS_LOCAL_PATH", str(tmp_path / "x.json"))   # R-4 — 호출 시점에 env 를 푼다
    assert subjects.path() == tmp_path / "x.json"


def test_the_runtime_state_ledger_no_longer_lists_subjects_as_an_exception():
    """전수 목록(운영 상태 파일)이 낡지 않게 — 두 겹으로 가른 뒤에도 예외로 남아 있으면 다음 사람이 '아직' 으로 읽는다."""
    from tests import test_runtime_state_files as R
    assert "data/subjects.json" not in R.TRACKED_ON_PURPOSE
    assert "subjects_local_path" in R.WRITE_ACCESSORS["ingest.media"]
