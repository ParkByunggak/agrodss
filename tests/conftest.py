# -*- coding: utf-8 -*-
# 운영 원장 격리 — 테스트는 data/media/ 에 쓰지 않는다(운영 상태 파일 신설 시 격리를 짝으로).
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_media_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_MEDIA_DIR", str(tmp_path / "media"))
    yield
