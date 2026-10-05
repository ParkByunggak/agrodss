# -*- coding: utf-8 -*-
# [U-22 낡음 대조 2026-10-05] 「세션 시작 시 heredoc 파일 쓰기 1회로 가드 활성 확인」 은 2026-09-18 부터 핸드오버 0번과 가드 머리에 **글로** 있었다.
# 그런데 이 세션은 그 확인을 안 하고 시작해 규율을 **세 번** 어겼다(sed -i 1 · heredoc 파일 쓰기 2). 규율이 세 번 안 지켜지면 문서가 아니라 **경로**가 모자란 것이다.
# 그래서 확인을 한 줄 명령으로 만들었다(`scripts/hook_window_probe.sh`). 이 검사가 고정하는 것:
#   ① 판정기가 그 명령을 **실제로 막는다**(안 막으면 탐침이 아무것도 못 말한다 — 통과가 "훅 활성" 을 뜻하지 않게 된다)
#   ② 탐침은 임시 파일 하나만 쓰고 지운다(저장소·운영 자료를 안 건드린다)
#   ③ 세션 시작 절차(핸드오버 0번)가 그 스크립트를 **이름으로** 가리킨다 — 글과 경로가 어긋나면 다음 사람이 또 글만 읽는다
# 그리고 판정기가 **이 세션의 세 위반을 다 막는지**도 함께 잰다 — 판정기가 멀쩡한데 배선이 잠들어 있었다는 U-22 의 판독을 검사로 남긴다.
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "scripts" / "hook_window_probe.sh"
JUDGE = ROOT / "scripts" / "hook_block_shell_authoring.py"


def _verdict(command: str) -> str:
    out = subprocess.run([sys.executable, str(JUDGE)], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    return "deny" if out else "allow"


def _probe_command() -> str:
    """탐침이 실제로 돌리는 셸 — 주석을 걷고 heredoc 쓰기 줄만 남긴다(판정기에 먹이는 것은 사람이 치는 것과 같아야 한다)."""
    body = PROBE.read_text(encoding="utf-8")
    return "\n".join(ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))


def test_the_probe_exists_and_only_touches_a_temp_file():
    body = PROBE.read_text(encoding="utf-8")
    assert "TMPDIR" in body and "rm -f" in body, "탐침이 임시 파일을 안 쓰거나 안 지운다"
    assert "data/" not in body and "docs/" not in body and "ingest/" not in body, "탐침이 저장소 자료를 건드린다"


def test_the_judge_really_blocks_the_probe():
    """탐침의 뜻은 **막히는 것**이다 — 판정기가 이 명령을 통과시키면 탐침이 아무것도 못 말한다(통과가 두 가지 뜻이 된다)."""
    assert _verdict(_probe_command()) == "deny"


@pytest.mark.parametrize("command", [
    "sed -i 's/^CORPUS_MIN = 118 /CORPUS_MIN = 131 /' tests/test_chat_corpus.py",
    "sed -i 's/_past_declarative_end/_declarative_end/g' tests/test_endings_are_a_rule_not_a_list.py",
    "python - <<'PY'\nimport pathlib\np=pathlib.Path('ingest/chat.py'); s=p.read_text()\np.write_text(s)\nPY",
])
def test_the_judge_blocks_every_violation_this_session_made(command):
    """2026-10-05 의 세 위반을 그대로 먹인다 — **판정기는 멀쩡했다**(배선이 잠들어 있었다). 구멍이 생기면 여기서 터진다."""
    assert _verdict(command) == "deny", command


@pytest.mark.parametrize("command", ["python - <<'PY'\nprint(1)\nPY", "grep -rn x ingest/ | head -3", "python -c 'print(1)'"])
def test_read_only_measuring_still_passes(command):
    """반대편 — 읽기 전용 측정은 통과한다(과잉 차단은 다음 사람이 가드를 통째로 끄게 만든다)."""
    assert _verdict(command) == "allow", command


def test_the_session_start_step_names_the_script():
    """글과 경로가 어긋나면 다음 사람이 또 글만 읽는다 — 핸드오버 0번이 그 스크립트를 이름으로 가리킨다."""
    # 구조로 자른다 — 「훅 활성 확인」 이라는 **말**로 찾으면 다른 자리(순서 요약 줄)가 먼저 걸린다(첫 판이 그래서 깨졌다 · 창을 고정하지 않는다 §7.5)
    lines = (ROOT / "docs" / "handover_20260919.md").read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("0. ") and "훅 활성 확인" in ln)
    step = "\n".join(lines[i:i + 3])
    assert "hook_window_probe.sh" in step, "세션 시작 0번이 탐침 스크립트를 안 가리킨다"
