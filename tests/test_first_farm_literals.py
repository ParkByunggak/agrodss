# -*- coding: utf-8 -*-
# [발행자 2026-09-20 "쪽파는 하나의 사례 — 같은 유형의 작목 전부에 적용되는 로직"] 코드 안 첫 농가 리터럴 전수(§7.5 지점 축).
#   측정: 11파일에 '쪽파 · jjokpa · p001' 이 있었고 그중 **로직 기본값** 둘 — ingest.fertilizer 주소 모드의 --parcel=p001 · --crop=쪽파 기본값,
#   subjects.DEFAULT_PARCEL="p001"(새 재배 단위가 둘째 필지가 생겨도 첫 농가 필지에 붙는다). 나머지는 지식 표(작물 코드) · 출처 문구 · 문서 순서.
#   그리고 문서 셋에 실제 지번 주소가 있었다 — /doc 화면에 실린다(PII). 문서에서 뺐다(등록부 파일의 주소는 D1 발행자 결정 그대로).
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from ingest import parcels, subjects

ROOT = Path(__file__).resolve().parent.parent
ADDRESS = re.compile(r"연풍면|갈금리\s*\d")     # 첫 농가 지번의 변별 표지 — 값 자체를 검사에 적지 않는다


def test_default_parcel_only_when_registry_has_exactly_one():
    assert subjects.default_parcel() == "p001"                                   # 격리 사본의 등록부는 필지 하나
    s = subjects.add("배추", "2026 가을", status="계획")
    assert s["parcel"] == "p001"
    doc = json.loads(Path(parcels.parcels_path()).read_text(encoding="utf-8"))          # 격리 사본(conftest) — 운영 파일이 아니다
    doc["parcels"].append({**doc["parcels"][0], "id": "p002"})
    Path(parcels.parcels_path()).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert subjects.default_parcel() is None
    with pytest.raises(subjects.SubjectError, match="필지를 지정"):
        subjects.add("배추", "2027 봄", status="계획")
    assert subjects.add("배추", "2027 봄", status="계획", parcel="p002")["parcel"] == "p002"


def test_fertilizer_cli_address_mode_requires_parcel_and_crop():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "ingest.fertilizer", "어느 주소"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 2 and "--parcel=<필지 id>" in r.stdout and "--crop=<작목>" in r.stdout and "p001" not in r.stdout and "쪽파" not in r.stdout


def test_no_first_farm_default_in_code_and_no_address_in_docs():
    for rel in ("ingest", "judge", "frontend", "grid", "schema", "names", "mall", "scripts"):
        for py in (ROOT / rel).rglob("*.py"):
            code = "\n".join(ln.split("#", 1)[0] for ln in py.read_text(encoding="utf-8").splitlines())
            assert "DEFAULT_PARCEL" not in code, py
            assert not re.search(r'=\s*"p001"|get\("--parcel",\s*"p001"\)|get\("--crop",\s*"쪽파"\)', code), py   # 기본값 형태
    for md in (ROOT / "docs").glob("*.md"):
        assert not ADDRESS.search(md.read_text(encoding="utf-8")), md        # /doc 화면에 실리는 문서 — 지번 주소 금지
    assert not ADDRESS.search((ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
