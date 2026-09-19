# -*- coding: utf-8 -*-
# FILE: scripts/env_from_vela.py
# ROLE: [D-9 키 인용] D:\vela\.env 에서 agrodss 가 쓰는 키를 **이름만 보고** D:\agrodss\.env 로 옮긴다. 값은 화면에 찍지 않는다.
#   · .env.example 에 적힌 이름이 대상. VELA 는 EXTERNAL_API__ 접두(중첩 설정)로도 두므로 둘 다 본다.
#   · 이미 값이 있는 이름은 건드리지 않는다. 없는 이름만 붙인다(append). 원본 VELA .env 는 읽기만.
#   · 사용: python scripts\env_from_vela.py [D:\vela\.env]
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VELA_ENV = Path(r"D:\vela\.env")
PREFIXES = ("", "EXTERNAL_API__")


def wanted_names(example_text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^([A-Z][A-Z0-9_]*)=", example_text, re.M)]


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def merge(agrodss_env_text: str, vela_env_text: str, names: list[str]) -> tuple[str, list[str], list[str]]:
    """(새 .env 본문, 옮긴 이름, VELA 에도 없는 이름). 값이 이미 있으면 건드리지 않는다."""
    have = parse_env(agrodss_env_text)
    vela = parse_env(vela_env_text)
    copied: list[str] = []
    missing: list[str] = []
    lines = [agrodss_env_text.rstrip("\n")] if agrodss_env_text.strip() else []
    for n in names:
        if have.get(n):
            continue
        val = next((vela[p + n] for p in PREFIXES if vela.get(p + n)), None)
        if val:
            lines.append(f"{n}={val}")
            copied.append(n)
        else:
            missing.append(n)
    if copied:
        lines.insert(len(lines) - len(copied), "# [D-9 키 인용] D:\\vela\\.env 에서 옮김 — 값은 이 파일에만")
    return "\n".join(lines) + "\n", copied, missing


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    vela_env = Path(argv[0]) if argv else DEFAULT_VELA_ENV
    if not vela_env.exists():
        print(f"VELA .env 없음: {vela_env} — 경로를 인자로 준다")
        return 2
    names = wanted_names((ROOT / ".env.example").read_text(encoding="utf-8"))
    names = [n for n in names if n.endswith("_KEY")]                 # 키만 옮긴다(폴더 · 포트 · D-16 은 사람이 정한다)
    target = ROOT / ".env"
    cur = target.read_text(encoding="utf-8") if target.exists() else ""
    new, copied, missing = merge(cur, vela_env.read_text(encoding="utf-8"), names)
    if copied:
        target.write_text(new, encoding="utf-8")
    print(f"옮김 {len(copied)}: {', '.join(copied) or '없음'}")
    print(f"VELA 에도 없음 {len(missing)}: {', '.join(missing) or '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
