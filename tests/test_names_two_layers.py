# -*- coding: utf-8 -*-
# [U-38 2026-09-27] 작목 이름 사전도 씨앗/덮개 두 겹 — 재배 단위 등록부(U-24 · U-37)와 같은 형태를 같은 처방으로.
#
# 전에는 발행자 승인(U-14)이 추적 CSV 에 줄을 붙이고 추적 문서(docs/crop_names.md)까지 다시 그렸다. 발행자 PC 의 다음 update.bat 은
# 수정된 추적 파일을 사본으로 옮기고 되돌린다 — 그 순간 **승인한 이름이 사전에서 사라진다**. 거부와 통과를 둘 다 본다.
from __future__ import annotations

import csv
import os
from pathlib import Path

from names import candidates as nc, resolve as names

ROOT = Path(__file__).resolve().parent.parent


def _seed() -> Path:
    return Path(os.environ["AGRODSS_NAMES_CSV"])


def _local() -> Path:
    return Path(os.environ["AGRODSS_NAMES_LOCAL_CSV"])


def _backup() -> Path:
    return Path(os.environ["AGRODSS_NAMES_BACKUP_CSV"])


def _write_csv(p: Path, rows: list[dict[str, str]]) -> None:
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(names.HEADER))
        w.writeheader()
        w.writerows(rows)


def _row(canon: str, alias: str, src: str = "발행자 승인 2026-09-20") -> dict[str, str]:
    return {"정본명": canon, "이명": alias, "관계": names.IDENTITY, "이명종류": "사투리", "출처": src, "비고": ""}


def test_an_approval_lands_in_the_overlay_and_resolves_without_touching_seed_or_doc():
    before, doc = _seed().read_bytes(), (ROOT / "docs" / "crop_names.md").read_bytes()
    c = nc.add("땡파", context="new_chat")
    nc.approve(c["id"], "도라지", by="publisher")
    assert _seed().read_bytes() == before and (ROOT / "docs" / "crop_names.md").read_bytes() == doc
    assert _local().exists() and names.resolve("땡파").canonical == "도라지"
    assert next(csv.reader(_local().open(encoding="utf-8"))) == list(names.HEADER)   # 덮개는 씨앗과 같은 열


def test_rows_the_updater_backed_up_come_back_through_the_overlay_only():
    """[U-37 과 같은 되살리기] 두 겹 이전 승인이 씨앗에 붙어 있다가 update.bat 사본으로 옮겨진 경우."""
    seed_rows = names._read(_seed())
    _write_csv(_backup(), seed_rows + [_row("도라지", "땡파"), _row("쪽파", "쫑파")])
    before = _seed().read_bytes()
    assert names.ensure_local() == 2
    assert _seed().read_bytes() == before
    assert names.resolve("땡파").canonical == "도라지" and names.resolve("쫑파").canonical == "쪽파"
    assert len(names._read(_local())) == 2, "씨앗에 이미 있는 줄까지 덮개로 끌어왔다"
    assert names.ensure_local() == 0, "멱등이 아니다"


def test_nothing_is_invented_without_a_backup_and_the_server_wires_the_restore():
    assert names.ensure_local() == 0 and not _local().exists()
    from frontend import serve
    src = open(serve.__file__, encoding="utf-8").read()
    body = src[src.index("def make_server"):src.index("\ndef ", src.index("def make_server") + 10)]
    assert "_names.ensure_local()" in body, "기동이 되살리기를 부르지 않는다"


def test_the_overlay_is_outside_git_and_the_seed_is_read_only_for_runtime():
    import subprocess
    rel = "data/crop_names_local.csv"
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0
    src = open(nc.__file__, encoding="utf-8").read()
    body = src[src.index("def approve"):src.index("\ndef ", src.index("def approve") + 10)]
    assert "append_local(" in body and "names_csv_path()" not in body and "NAMES_DOC_PATH" not in body
