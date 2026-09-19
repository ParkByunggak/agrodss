# -*- coding: utf-8 -*-
# FILE: scripts/build_schema_doc.py
# ROLE: [M-6] schema/records.py(정본) → docs/schema_records.md(생성물). --check 는 동기 여부만(테스트가 쓴다).
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from schema import records as sch  # noqa: E402

OUT = ROOT / "docs" / "schema_records.md"


def build() -> str:
    lines = ["# 스키마 정본 — 레코드 종류 (생성물)", "",
             f"정본은 `schema/records.py` 다. 이 문서는 `scripts/build_schema_doc.py` 가 만든다 — 손으로 고치지 않는다. 버전 {sch.SCHEMA_VERSION}.", "",
             "허용 목록 방식: 선언되지 않은 필드는 거부된다. 경계(`judge/boundary.py`)의 허용 목록은 여기서 파생된다.", "",
             "| 종류 | 층 | 3층 입력 | 출처 | 필수 | 선택 | PII |", "|---|---|---|---|---|---|---|"]
    for k in sch.describe():
        lines.append(f"| `{k['kind']}` | {k['layer']} | {'예' if k['layer3_input'] else '—'} | {', '.join(f'`{s}`' for s in k['sources']) or '—'} | "
                     f"{', '.join(k['required'])} | {', '.join(k['optional']) or '—'} | {', '.join(k['pii']) or '—'} |")
    lines += ["", "## 어휘", "",
              f"- 요구 상태: {' · '.join(sch.REQUEST_STATUS)}",
              f"- 개선 항목 상태: {' · '.join(sch.ITEM_STATUS)}",
              f"- 개선 방향: {' · '.join(sch.DIRECTIONS)} — 보수만 자동 적용될 수 있다(D-14)",
              f"- 대상: {' · '.join(sch.TARGETS)}",
              f"- 대조 판정: {' · '.join(sch.VERDICTS)}",
              f"- 재배 단위 상태: {' · '.join(sch.SUBJECT_STATUS)}",
              f"- 금지 필드(문서용 — 검사는 허용 목록): {', '.join(sorted(sch.FORBIDDEN_FIELDS))}",
              f"- PII(화면·봉투·몰에 안 나감): {', '.join(sorted(sch.PII_FIELDS))}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("docs/schema_records.md 가 정본과 다르다 — python scripts/build_schema_doc.py")
            sys.exit(1)
        print("동기")
        sys.exit(0)
    OUT.write_text(text, encoding="utf-8")
    print("written", OUT)
