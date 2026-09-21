# -*- coding: utf-8 -*-
# [운영 상태 파일 전수 2026-09-21] **런타임이 쓰는 것은 git 밖이다.**
#
# 왜 — U-18 이 이 함정을 이미 한 번 밟았다: `data/parcels.json` 이 추적 파일인데 런타임이 좌표·PNU 를 써 넣었고,
# upstream 이 같은 파일을 건드리자 발행자 PC 의 `git pull` 이 *"commit or stash"* 로 **멈췄다**. 그 멈춤이 며칠치
# 옛 코드를 돌게 했다. 처방(씨앗/덮개 두 겹)은 옳았는데 **한 파일에만** 적용됐다 — §7.5 지점 축.
#
# 전수(2026-09-21) 결과:
#
#   data/subjects.json                            추적 + 런타임 쓰기   작목 추가 · 상태 변경
#   data/crop_names.csv                           추적 + 런타임 쓰기   U-14 이름 승인
#   data/organic/organic_materials_public.json    추적 + 런타임 쓰기   공시자재 갱신 작업
#   docs/crop_names.md                            추적 + 런타임 쓰기   승인 때 다시 그린다
#   data/profile.json                             추적도 무시도 아님   `git add -A` 한 번이면 이름이 저장소로
#
# 마지막 것은 이 커밋에서 .gitignore 로 닫았다. 앞의 넷은 **정본이면서 운영 상태**라 사유를 적고 남긴다 —
# 대신 `update.bat` 이 그 충돌을 감당한다(사본을 남기고 되돌린 뒤 받는다. **버리지 않는다**).
#
# 여기서 재는 것 셋:
#   ① 모든 쓰기 대상은 git 밖이거나, 아래 목록에 **사유와 함께** 있다
#   ② 쓰는 모듈이 새로 생기거나 경로 접근자가 늘면 목록이 불완전해져 깨진다(새 파일이 조용히 끼지 못한다)
#   ③ 경로는 **호출 시점에** env 로 푼다(R-4) — 모듈 수준에 박으면 conftest 격리가 안 닿는다
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 추적하면서 런타임도 쓰는 파일 — 사유를 적는다. 늘리려면 "왜 정본이면서 운영 상태인가" 를 여기 한 줄로 답한다.
TRACKED_ON_PURPOSE = {
    "data/subjects.json": "재배 단위 등록부 — 씨앗이자 운영 상태. 두 겹으로 가르는 것은 회수 대기(U-24)",
    "data/crop_names.csv": "작목 이름 정본 — 승인(U-14)이 한 줄 붙인다. 사람의 명시적 행위라 드물다",
    "data/organic/organic_materials_public.json": "공시자재 정본 — 갱신 작업이 통째로 바꾼다. 사람이 돌린다",
    "docs/crop_names.md": "정본 CSV 의 렌더 — 승인 때 다시 그린다",
}

# 쓰는 모듈 → 그 모듈의 **쓰기 대상** 접근자. 읽기 전용 접근자는 아래 READ_ONLY 에 적어 둘 다 분류를 강제한다.
WRITE_ACCESSORS = {
    "ingest.chat": ("chat_dir", "index_path"),
    "ingest.events": ("events_dir", "index_path"),
    "ingest.feedback": ("feedback_dir", "index_path"),
    "ingest.media": ("media_dir", "inbox_dir", "index_path", "seen_path"),
    "ingest.organic_materials": ("data_path",),
    "ingest.parcels": ("local_path",),
    "ingest.profile": ("path",),
    "ingest.psis": ("psis_dir",),
    "ingest.soil_store": ("soil_dir",),
    "ingest.subjects": ("path",),
    "names.candidates": ("names_dir", "index_path"),
}
READ_ONLY = {
    "ingest.media": ("subjects_path",),          # 재배 단위를 읽기만 한다
    "ingest.parcels": ("parcels_path", "legacy_path"),   # 씨앗(추적) · 옛 파일 — 둘 다 읽기 전용(U-18)
}
# 접근자가 아닌 자리에서 쓰는 것 — 여기 손으로 적는다(자동 완전성 밖이라는 것을 문면으로 남긴다)
EXTRA_TARGETS = (("names.resolve", "names_csv_path"),)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _tracked() -> set[str]:
    return set(_git("ls-files").stdout.split())


def _ignored(rel: str) -> bool:
    return _git("check-ignore", "-q", rel).returncode == 0


@pytest.fixture
def no_env(monkeypatch):
    """conftest 가 건 격리 env 를 걷는다 — **운영 기본값**을 봐야 한다(격리된 tmp 경로를 재면 아무것도 못 잡는다)."""
    import os
    for k in [k for k in os.environ if k.startswith("AGRODSS_")]:
        monkeypatch.delenv(k, raising=False)


def _targets(no_env_applied: bool = True) -> list[tuple[str, str, Path]]:
    out = []
    for mod, names in list(WRITE_ACCESSORS.items()) + [(m, (n,)) for m, n in EXTRA_TARGETS]:
        m = importlib.import_module(mod)
        for n in names:
            out.append((mod, n, Path(getattr(m, n)())))
    return out


def test_every_runtime_write_target_is_outside_git_or_declared(no_env):
    """① 계약 — 런타임이 쓰는 것은 git 밖이다. 아니면 **왜 정본이면서 운영 상태인지** 목록이 답한다."""
    tracked, offenders = _tracked(), []
    for mod, name, p in _targets():
        rel = p.resolve().relative_to(ROOT).as_posix()
        if _ignored(rel) or (rel not in tracked and rel not in TRACKED_ON_PURPOSE):
            continue                                  # git 밖이거나, 아직 없는 파일(무시 규칙이 덮는다)
        if rel not in TRACKED_ON_PURPOSE:
            offenders.append(f"{mod}.{name}() -> {rel}")
    assert offenders == [], ("추적 파일에 런타임이 쓴다 — 발행자 pull 이 멈출 수 있다. "
                            f"git 밖으로 내보내거나 TRACKED_ON_PURPOSE 에 사유를 적는다: {offenders}")


def test_the_declared_exceptions_are_really_tracked_and_really_written(no_env):
    """목록이 **낡지 않게** — 이미 git 밖으로 나간 파일이 예외로 남아 있으면 다음 사람이 잘못 읽는다."""
    tracked = _tracked()
    written = {p.resolve().relative_to(ROOT).as_posix() for _, _, p in _targets()}
    for rel, why in TRACKED_ON_PURPOSE.items():
        assert rel in tracked, f"{rel} 은 더는 추적 파일이 아니다 — 목록에서 뺀다"
        assert len(why) > 10, f"{rel} 의 사유가 비어 있다"
    # docs/crop_names.md 는 접근자가 아니라 상수로 쓰인다(EXTRA 밖) — 그 사실을 문면으로 고정한다
    assert "docs/crop_names.md" not in written
    assert "NAMES_DOC_PATH" in (ROOT / "names" / "candidates.py").read_text(encoding="utf-8")


def test_the_profile_registry_cannot_be_committed_by_accident():
    """발행자 이름이 든 파일이 `git add -A` 로 저장소에 들어가던 자리 — 추적도 무시도 아니었다(U-18 과 같은 축)."""
    assert _ignored("data/profile.json")
    assert "data/profile.json" not in _tracked()


def _writer_modules() -> dict[str, list[str]]:
    """쓰는 모듈 → 0인자 경로 접근자 이름들. **측정으로** 구한다 — 손 목록이 낡으면 여기서 깨진다."""
    found: dict[str, list[str]] = {}
    for p in sorted(list((ROOT / "ingest").glob("*.py")) + list((ROOT / "names").glob("*.py"))):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        # [자기 도구 오류 2026-09-21] 첫 판은 `open(...)` **내장 호출**만 봤고 `index_path().open("a")` 를 못 봤다 —
        # 원장 셋(chat · events · feedback)이 통째로 '안 쓰는 모듈' 로 세어졌다. 부르는 형태 둘을 다 본다.
        def _is_write(n: ast.Call) -> bool:
            if isinstance(n.func, ast.Attribute) and n.func.attr == "write_text":
                return True
            attr = isinstance(n.func, ast.Attribute)
            name = n.func.attr if attr else getattr(n.func, "id", "")
            if name != "open":
                return False
            # 모드가 놓이는 자리가 다르다 — `open(경로, "w")` 는 두 번째, `경로.open("a")` 는 **첫 번째**.
            # 첫 판은 둘 다 두 번째로 봐서 원장 셋을 놓쳤다(같은 회차에 낸 탐지기 오류 둘째).
            args = n.args if attr else n.args[1:]
            mode = next((a for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)), None)
            kw = next((k.value for k in n.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)), None)
            m = str((mode or kw).value) if (mode or kw) else ""
            return any(c in m for c in "wax+")

        writes = any(_is_write(n) for n in ast.walk(tree) if isinstance(n, ast.Call))
        if not writes:
            continue
        mod = f"{p.parent.name}.{p.stem}"
        found[mod] = [f.name for f in tree.body if isinstance(f, ast.FunctionDef) and not f.args.args
                      and (f.name.endswith("path") or f.name.endswith("dir"))]
    return found


def test_a_new_writer_or_a_new_path_cannot_slip_in_unclassified():
    """② 완전성 — 새 쓰기 모듈이나 새 경로 접근자가 생기면 여기서 깨진다. 그때 분류하면서 ①을 다시 통과해야 한다."""
    measured = _writer_modules()
    assert set(measured) == set(WRITE_ACCESSORS), (
        f"쓰는 모듈 목록이 어긋난다 — 측정 {sorted(set(measured) - set(WRITE_ACCESSORS))} / "
        f"목록에만 {sorted(set(WRITE_ACCESSORS) - set(measured))}")
    for mod, accs in measured.items():
        classified = set(WRITE_ACCESSORS[mod]) | set(READ_ONLY.get(mod, ()))
        assert set(accs) == classified, f"{mod} 의 경로 접근자가 분류되지 않았다: {sorted(set(accs) ^ classified)}"


def test_paths_are_resolved_when_called_not_when_imported():
    """③ [R-4] 경로를 모듈 수준에서 env 로 풀면 import 뒤의 `monkeypatch.setenv` 가 **안 닿는다** — 검사가
    운영 파일에 쓰게 되는 형태다(R-4 실측: 첫 실행에서 운영 등록부에 33줄). 모듈 수준 대입만 본다(함수 본문은 호출 시점)."""
    bad = []
    for p in sorted(list((ROOT / "ingest").glob("*.py")) + list((ROOT / "names").glob("*.py"))
                    + list((ROOT / "grid").glob("*.py")) + list((ROOT / "judge").glob("*.py"))):
        for node in ast.parse(p.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.Assign):
                continue
            for n in ast.walk(node.value):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
                        and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "environ"
                        and n.args and isinstance(n.args[0], ast.Constant)
                        and ("PATH" in str(n.args[0].value) or "DIR" in str(n.args[0].value))):
                    bad.append(f"{p.relative_to(ROOT).as_posix()}:{n.lineno} {ast.unparse(node.targets[0])}")
    assert bad == [], f"경로가 import 시점에 고정됐다 — 호출 시점 함수로 푼다(R-4): {bad}"


def test_the_updater_keeps_a_copy_before_it_restores():
    """[전수의 짝] 목록에 남긴 넷은 upstream 이 고치면 발행자 pull 을 멈출 수 있다. `update.bat` 이 그것을
    감당하되 **버리지 않는다** — 사본이 먼저고, 사본이 실패하면 되돌리지도 않는다."""
    text = (ROOT / "scripts" / "update.bat").read_text(encoding="ascii")
    body = "\n".join(ln for ln in text.splitlines() if not ln.strip().upper().startswith("REM"))
    pres = body[body.index(":preserve"):body.index(":preservefailed")]
    assert pres.index("copy ") < pres.index("git checkout"), "되돌리기가 사본보다 앞이다 — 그러면 잃는다"
    assert "if errorlevel 1 goto preservefailed" in pres, "사본이 실패해도 되돌린다 — 그러면 잃는다"
    assert "_local_backup" in pres and _ignored("data/_local_backup/"), "사본 자리가 git 안이면 다음 pull 이 또 멈춘다"
    assert "git diff --name-only -- data/" in body, "무엇이 수정됐는지 보지 않고 지나간다"
