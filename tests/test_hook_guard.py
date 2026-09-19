# -*- coding: utf-8 -*-
# [U-13] 셸 파일 쓰기 차단 훅 — 거부와 통과를 **둘 다** 본다(과잉 차단은 다음 사람이 가드를 통째로 끄게 만든다) + 배선(settings.json).
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.hook_block_shell_authoring import verdict

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "hook_block_shell_authoring.py"
SQ, BT = chr(39), chr(96)


def blocked(cmd: str, tool: str = "Bash") -> bool:
    return verdict(cmd, tool) is not None


# ── 막는다 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cmd", [
    "cat > judge/x.py <<'EOF'\nprint(1)\nEOF",
    "cat <<'EOF' >> docs/agrodss_backlog.md\n| N-1 |\nEOF",
    "python - <<'PY'\nfrom pathlib import Path\np = Path('t.py')\np.write_text(p.read_text().replace('a', 'b'))\nPY",
    "python - <<'PY'\nwith open('x.json', 'w') as f:\n    f.write('{}')\nPY",
    "python - <<'PY' >/dev/null 2>&1\nprint(1)\nPY",
    "python - <<'PY' | tee out.txt\nprint(1)\nPY",
    "python3 -c \"open('x','w').write('1')\"",
    "python -c \"print('A' + " + BT + "echo X" + BT + " + 'B')\"",
    "python -c \"print('$(date)')\"",
    "node -e \"require('fs').writeFileSync('x','1')\"",
    # [코드 평가 D8] 배치가 고르는 호출형 · 경로 · 옵션 토큰 뒤의 -c
    "py -3 -c \"open('x','w').write('a')\"",
    "/usr/bin/python3 -c \"open('x','w').write('a')\"",
    "python -X utf8 -c \"open('x','w').write('a')\"",
    "python3.12 -c \"open('x','w').write('a')\"",
    # [코드 평가 D9] 리다이렉트·tee 가 heredoc 과 다른 줄에 있어도 파일로 흐르는 것이다
    "{ cat <<'EOF'\nhi\nEOF\n} > out.txt",
    "( python3 - <<'PY'\nprint(1)\nPY\n) > out.txt",
    "cat <<'EOF' |\nhi\nEOF\ntee out.txt",
])
def test_bash_write_paths_are_blocked(cmd):
    assert blocked(cmd), cmd


@pytest.mark.parametrize("cmd", [
    "Set-Content -Path x.md -Value 'a'", "'a' | Out-File x.md", "[IO.File]::WriteAllText('x','a')",
    "New-Item -Path x.md -Force", "echo a > x.md", "@\"\nline $(1+1)\n\"@ | Set-Content x",
    "python -c \"print(" + BT + "n)\"",
])
def test_powershell_write_paths_are_blocked(cmd):
    assert blocked(cmd, "PowerShell"), cmd


# ── 통과한다 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cmd", [
    "python - <<'PY'\nimport json\nprint(json.dumps({'a': 1}))\nPY",                         # 읽기 전용 측정
    "python - <<'PY' 2>&1\nprint(1)\nPY",                                                   # fd 복제는 파일이 아니다
    "python -c 'print(\"A\" + " + BT + "echo X" + BT + ")'",                                  # 작은따옴표 — 셸이 안 건드린다
    "python -m pytest -q tests/",
    "git log --oneline -3",
    "grep -rn heredoc scripts/ | head",
    "cat <<< 'herestring is not heredoc'",
    "python -c 'import sys; print(sys.version)'",
    "",
    # [코드 평가 D10] 표준출력 쓰기 · 읽기 열기는 측정이다 — 막으면 다음 사람이 가드를 통째로 끈다
    "python3 - <<'PY'\nimport sys; sys.stdout.write('measure')\nPY",
    "python3 - <<'PY'\nprint(open('agrodss_backlog.md').read()[:10])\nPY",
    "python3 - <<'PY'\nwith open('x.csv', 'r') as f: print(len(f.read()))\nPY",
    "python -c 'import json, sys; json.dump({\"a\": 1}, sys.stdout)'",
    "python3 - <<'PY'\nprint('a -> b')\nPY",                                                # 화살표는 리다이렉트가 아니다(D 리뷰 #29)
])
def test_bash_read_only_paths_pass(cmd):
    assert not blocked(cmd), cmd


@pytest.mark.parametrize("cmd", [
    "Get-Content x.md | Select-String a", "python -m pytest 2>$null", "dir | Out-Null", "@'\nliteral $(no) `n\n'@",
    "echo a > $null",
])
def test_powershell_read_only_paths_pass(cmd):
    assert not blocked(cmd, "PowerShell"), cmd


def test_powershell_rules_are_not_bash_rules():
    # PowerShell 에서 백틱은 이스케이프 — Bash 규칙을 그대로 옮기면 오탐. 반대로 Bash 에서 Set-Content 는 명령이 아니다
    assert not blocked("echo `n", "PowerShell") and not blocked("echo Set-Content", "Bash")


# ── 훅 계약(프로세스) · 배선 ───────────────────────────────────────────────────────
def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, encoding="utf-8", errors="replace")


def test_hook_process_denies_with_reason_and_passes_silently():
    r = _run({"tool_name": "Bash", "tool_input": {"command": "cat > x.md <<'EOF'\nhi\nEOF"}})
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["hookSpecificOutput"]["permissionDecision"] == "deny" and "[U-13]" in out["hookSpecificOutput"]["permissionDecisionReason"]
    r = _run({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert r.returncode == 0 and r.stdout.strip() == ""
    r = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, encoding="utf-8")
    assert r.returncode == 0 and r.stdout.strip() == ""                        # 판정 불능은 통과 — 가드가 작업을 인질로 잡지 않는다


def test_settings_wire_the_hook_for_bash_and_powershell():
    cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = cfg["hooks"]["PreToolUse"]
    entry = next(e for e in pre if "Bash" in e["matcher"])
    assert "PowerShell" in entry["matcher"]
    assert any("hook_block_shell_authoring.py" in h["command"] for h in entry["hooks"])
