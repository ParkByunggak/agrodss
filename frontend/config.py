# -*- coding: utf-8 -*-
# FILE: frontend/config.py
# ROLE: 내부 화면 설정 — 값은 여기 한 곳(하드코딩 금지). 환경변수로 덮어쓴다.
from __future__ import annotations

import os
from pathlib import Path


# [코드 평가 D2 · 2026-09-19] .env 로더는 ingest.config.load_dotenv **하나**다. 여기 두 벌째가 있었고 빈 값(KEY=)을 환경에 넣어
# 화면 프로세스에서 옮긴 키가 사라졌다(ingest 로더는 빈 값을 건너뛴다). import 가 곧 적재다(ingest.config 모듈 말미).
from ingest import config as _ingest_config  # noqa: F401  — .env 적재 정본

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
# [발행자 2026-09-19 21:40 "수정된 것들은 리프레시하면 반영이 되어야 한다"] 데이터는 요청마다 다시 계산되니 원래 그렇다. 코드는 파이썬이
# 기동 시점 것을 붙들고 있어 재시작이 필요했다 → 서버가 git HEAD 변화를 스스로 보고 종료 코드 3 으로 나가면 run_frontend.bat 가 새 코드로
# 다시 띄운다(브라우저 새 창 없이). 끄려면 AGRODSS_RELOAD=0. VELA 의 "--reload 없음" 결정은 uvicorn 파일 감시의 폭주 때문이었고 이것은
# HEAD 문자열 비교 한 번뿐이다.
RELOAD_ON_HEAD_CHANGE: bool = os.environ.get("AGRODSS_RELOAD", "1") != "0"
RELOAD_POLL_SEC: float = float(os.environ.get("AGRODSS_RELOAD_POLL_SEC", "2"))
RESTART_EXIT_CODE: int = 3
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
