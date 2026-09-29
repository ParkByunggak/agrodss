# -*- coding: utf-8 -*-
# FILE: scripts/measure_misclassified.py
# ROLE: [WO-LLM-01 측정 · 읽기 전용 · 콘솔 껍데기] 정본은 `ingest/misclassified.py` — [검토표 ③ 2026-09-29] 화면(/changes)이 같은 수를
#       상시로 내게 되면서 세는 코드를 4층이 부를 수 있는 자리로 옮겼다(정본 하나 · 어휘 두 벌 금지). 여기서는 그것을 불러 콘솔에 낸다.
#   규율: 아무것도 쓰지 않는다. 출력에 발화 원문이 실리므로 파일로 저장하지 말고 판독 뒤 폐기한다(PII 규율).
#   쓰는 법:  python -m scripts.measure_misclassified        (발행자 PC · 운영 원장)
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.misclassified import MIN_SET, STATEMENT_KEY, measure, report, status_line  # noqa: E402,F401 — 정본 재수출(옛 호출부 그대로)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report(measure()))
