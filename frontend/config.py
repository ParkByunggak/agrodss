# -*- coding: utf-8 -*-
# FILE: frontend/config.py
# ROLE: 내부 화면 설정 — 값은 여기 한 곳(하드코딩 금지). 환경변수로 덮어쓴다.
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """루트 .env 의 KEY=VALUE 를 환경에 넣는다(이미 있는 키는 덮지 않는다). 값은 여기 말고 .env 에만."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# [D-6 절대 제약] 외부 배포 금지 — 루프백에만 묶는다. 이것은 설정값이 아니라 **제약**이라
# 환경변수로 덮어쓰지 않는다. tests/test_frontend_local_only.py 가 양방향으로 고정한다.
HOST: str = "127.0.0.1"

PORT: int = int(os.environ.get("AGRODSS_FRONTEND_PORT", "8765"))

ROOT: Path = Path(__file__).resolve().parent.parent
DOCS_DIR: Path = ROOT / "docs"

# 첫 페이지(M-13 관문: 대장이 첫 화면)
LEDGER_DOC: str = "agrodss_backlog.md"

# 화면 왼쪽 목차 순서 — 여기 없는 docs/*.md 는 뒤에 이름순으로 붙는다
NAV_ORDER: tuple[str, ...] = (
    "agrodss_backlog.md",
    "agrodss_milestones_20260918.md",
    "design_tree_review_20260918.md",
    "agrodss_mall_tree_20260918.md",
    "d1_first_farm.md",
    "review_jjokpa_20260918.md",
    "m10_harvest_timing.md",
    "grid_jjokpa_autumn.md",
    "m4_grid_schema.md",
    "crop_names.md",
    "crop_axes.md",
    "i1_outputs.md",
    "i2_nutrient_axis.md",
    "i3_inputs.md",
    "i4_axes_minimal.md",
    "i5_boundary.md",
)

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}

# [M-13 음성 · 반입 · 동기화 — 발행자 2026-09-19]
VOICE_SILENCE_MS: int = int(os.environ.get("AGRODSS_VOICE_SILENCE_MS", "5000"))   # 이만큼 입력 신호가 없으면 질문 종료
VOICE_MAX_MS: int = int(os.environ.get("AGRODSS_VOICE_MAX_MS", "90000"))          # 한 질문의 최대 녹음 길이
MAX_UPLOAD_MB: int = int(os.environ.get("AGRODSS_MAX_UPLOAD_MB", "300"))          # 채팅 반입 한 번의 본문 상한
# [D-16 대기] 휴대폰 동기화 — 같은 Wi-Fi 안에서만 · 토큰 없이는 절대 열리지 않는다. 기본은 루프백(D-6).
BIND: str = os.environ.get("AGRODSS_BIND") or HOST
LAN_TOKEN: str = os.environ.get("AGRODSS_LAN_TOKEN", "").strip()
LAN_TOKEN_MIN: int = 16
LAN_BIND = "0.0.0.0"
COOKIE_NAME = "agrodss_t"


def assert_local(host: str) -> str:
    """루프백이 아니면 기동 자체를 거부한다. 반환값은 검증된 host.
    예외 하나(D-16 옵트인): host=0.0.0.0 이고 AGRODSS_LAN_TOKEN(16자 이상)이 있을 때만 — 그때도 토큰 없는 요청은 401."""
    if host in _LOOPBACK:
        return host
    if host == LAN_BIND and len(LAN_TOKEN) >= LAN_TOKEN_MIN:
        return host
    raise RuntimeError(
        f"[D-6] 외부 배포 금지 — 루프백이 아닌 host 에 묶을 수 없다: {host!r} "
        f"(같은 Wi-Fi 동기화는 AGRODSS_BIND=0.0.0.0 + AGRODSS_LAN_TOKEN {LAN_TOKEN_MIN}자 이상 — D-16)"
    )
