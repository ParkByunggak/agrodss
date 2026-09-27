# -*- coding: utf-8 -*-
# [격리 완전성 2026-09-27 · §7.5 관문의 입력] 격리(conftest)는 관문이고, 쓰기 접근자는 그 관문의 입력이다.
# 쓰기 접근자 전수(test_runtime_state_files.WRITE_ACCESSORS — 측정으로 완전성이 보장된다)와 conftest 의 격리 목록을 **대조**하니
# `organic_materials.data_path`(AGRODSS_ORGANIC_PATH) 하나가 빠져 있었다 — 갱신 작업을 부르는 검사가 생기면 운영 정본에 쓴다.
# R-4 가 그렇게 33줄을 썼다. 목록 둘을 손으로 맞추지 않고 **접근자가 실제로 읽는 env 이름**을 따라가 센다.
from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

from tests.test_runtime_state_files import EXTRA_TARGETS, WRITE_ACCESSORS

ROOT = Path(__file__).resolve().parent.parent
_ENV = re.compile(r'environ\.get\("(AGRODSS_[A-Z_]+)"')
_CALL = re.compile(r"(?:(\w+)\.)?(\w+)\(\)")


def _envs_read_by(mod, fn_name: str, depth: int = 2) -> set[str]:
    """접근자 본문의 env 이름. 없으면 그것이 부르는 0인자 함수(같은 모듈 · `모듈.함수()` 꼴)를 한두 단계 따라간다."""
    fn = getattr(mod, fn_name)
    src = inspect.getsource(fn)
    envs = set(_ENV.findall(src))
    if envs or depth == 0:
        return envs
    for owner, callee in _CALL.findall(src):
        target_mod = getattr(mod, owner, None) if owner else mod
        if target_mod is not None and callable(getattr(target_mod, callee, None)) and (owner or callee != fn_name):
            try:
                envs |= _envs_read_by(target_mod, callee, depth - 1)
            except (TypeError, OSError):
                continue
    return envs


def _isolated_by_conftest() -> set[str]:
    return set(re.findall(r'setenv\("(AGRODSS_[A-Z_]+)"', (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")))


def test_every_runtime_write_target_is_isolated_by_conftest():
    isolated = _isolated_by_conftest()
    missing = {}
    for mod_name, names in list(WRITE_ACCESSORS.items()) + [(m, (n,)) for m, n in EXTRA_TARGETS]:
        mod = importlib.import_module(mod_name)
        for n in names:
            envs = _envs_read_by(mod, n)
            assert envs, f"{mod_name}.{n}() 이 읽는 env 를 못 찾았다 — 경로가 env 로 안 풀리면 격리가 닿지 않는다(R-4)"
            for e in envs - isolated:
                missing[f"{mod_name}.{n}()"] = e
    assert missing == {}, f"검사가 운영 파일에 쓸 수 있다 — conftest 격리가 빠졌다: {missing}"


def test_the_organic_canon_is_read_through_a_session_copy():
    """반대편 — 격리하면서 읽기를 잃지 않는다(사본이 실제로 있고, 운영 정본이 아니다)."""
    from ingest import organic_materials as om
    p = om.data_path()
    assert p.exists() and p.resolve() != om.DEFAULT_PATH.resolve(), p
