# -*- coding: utf-8 -*-
# 운영 원장 격리 — 테스트는 data/ 아래 운영 파일에 쓰지 않는다(운영 상태 파일 신설 시 격리를 짝으로).
# [R-4 2026-09-19] 재배 단위 등록부(subjects.json)가 쓰기 대상이 되자 첫 실행에서 테스트가 운영 등록부에 33줄을 썼다 —
# 기본 인자에 경로를 묶어 두면 monkeypatch 가 안 닿는다. 경로는 호출 시점에 env 로 푼다.
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REAL_SUBJECTS = Path(__file__).resolve().parent.parent / "data" / "subjects.json"


@pytest.fixture(autouse=True)
def _isolate_media_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("AGRODSS_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("AGRODSS_FEEDBACK_DIR", str(tmp_path / "feedback"))
    monkeypatch.setenv("AGRODSS_CHAT_DIR", str(tmp_path / "chat"))
    reg = tmp_path / "subjects.json"
    reg.write_text(_REAL_SUBJECTS.read_text(encoding="utf-8"), encoding="utf-8")   # 운영 등록부의 사본 — 읽기는 같고 쓰기는 tmp
    monkeypatch.setenv("AGRODSS_SUBJECTS_PATH", str(reg))
    monkeypatch.setenv("AGRODSS_SUBJECTS_LOCAL_PATH", str(tmp_path / "subjects_local.json"))   # [U-24] 덮개(쓰기 대상) — 없는 경로로 시작
    monkeypatch.setenv("AGRODSS_SUBJECTS_BACKUP_PATH", str(tmp_path / "subjects_backup.json"))  # [U-37] update.bat 사본(읽기) — 이 PC 의 실제 사본이 검사에 새지 않게
    parcels = tmp_path / "parcels.json"                                            # [코드 평가 C4] 필지 등록부 — R-4 전수에서 빠졌던 한 곳
    parcels.write_text((_REAL_SUBJECTS.parent / "parcels_seed.json").read_text(encoding="utf-8"), encoding="utf-8")   # [U-18 2단계] 씨앗(PII 없음)의 사본
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(parcels))
    local = tmp_path / "parcels_local.json"                                        # [U-18] 덮개(PII · 런타임 기록) — 검사용 가짜 지번, 실제 주소는 어디에도 없다
    local.write_text(json.dumps({"parcels": [{"id": "p001", "address": "검사용 지번 1"}]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(local))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(tmp_path / "parcels_legacy.json"))  # 옛 추적 파일(이주 원천) — 검사는 운영 파일을 읽지 않는다(없는 경로)
    monkeypatch.setenv("AGRODSS_PROFILE_PATH", str(tmp_path / "profile.json"))   # 사용자 등록부도 쓰기 대상 — 격리 짝(R-4)
    monkeypatch.setenv("AGRODSS_SOIL_DIR", str(tmp_path / "soil"))               # 토양 원천 저장소(PII) — 격리 짝
    monkeypatch.setenv("AGRODSS_PSIS_DIR", str(tmp_path / "psis"))               # PSIS 캐시 — 격리 짝
    monkeypatch.setenv("AGRODSS_NAMES_DIR", str(tmp_path / "names"))             # 이름 후보 원장 — 격리 짝
    names_csv = tmp_path / "crop_names.csv"                                        # 정본 CSV 도 쓰기 대상(승인) — 사본으로
    names_csv.write_text((Path(__file__).resolve().parent.parent / "data" / "crop_names.csv").read_text(encoding="utf-8-sig"), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_NAMES_CSV", str(names_csv))
    monkeypatch.setenv("AGRODSS_NAMES_LOCAL_CSV", str(tmp_path / "crop_names_local.csv"))     # [U-38] 승인 덮개(쓰기 대상) — 없는 경로로 시작
    monkeypatch.setenv("AGRODSS_NAMES_BACKUP_CSV", str(tmp_path / "crop_names_backup.csv"))   # [U-38] update.bat 사본(읽기)
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(tmp_path / "climate_outlook.json"))       # [D-21 장기] 발행자 등재 정본(읽기) — 계약 검사가 운영 등재분을 읽지 않게(없는 경로 = 등재 없음)
    monkeypatch.setenv("AGRODSS_OUTLOOK_LOCAL_PATH", str(tmp_path / "climate_outlook_local.json"))   # [D-21 장기] 덮개(발행자 손 · git 밖) — 같은 이유
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "decisions_local.json"))   # [WO-PB-01 다음 한 수 2026-09-29] 결정 답 덮개(쓰기 대상) — 없는 경로로 시작
    monkeypatch.setenv("AGRODSS_ASKS_PATH", str(tmp_path / "chat" / "asks.json"))   # [WO-ASK-01 §8 2026-10-03] 묻기 원장(쓰기 대상) — 채팅 폴더와 같은 자리 · 없는 경로로 시작
    monkeypatch.setenv("AGRODSS_PROBES_LOCAL_PATH", str(tmp_path / "utterance_probes_local.json"))   # [손 노릇 2026-10-07] 문장 형태 점검 기대 덮개(쓰기 대상) — 없는 경로로 시작(운영 상태 파일 신설 시 격리를 짝으로)
    monkeypatch.setenv("AGRODSS_AUTO_PULL_SEC", "0")       # [U-39] 검사가 띄우는 화면(자식 프로세스)이 원격을 부르지 않게 — 아래 setattr 는 이 프로세스 몫
    from frontend import config as _cfg
    monkeypatch.setattr(_cfg, "AUTO_PULL_SEC", 0.0)
    from ingest import dropped as _dropped
    _dropped.clear()                                       # [⑤b 2026-09-28] '읽다 버린 것' 은 프로세스 전역 — 앞 검사의 버림이 뒤 검사의 /changes 에 실려 사람 말 래칫이 붉었다(격리 짝)
    from names import resolve as _names
    _names.reload()
    yield
    _names.reload()


@pytest.fixture(autouse=True, scope="session")
def _isolate_organic_canon(tmp_path_factory):
    """[격리 완전성 2026-09-27] 쓰기 접근자 전수(test_runtime_state_files.WRITE_ACCESSORS)와 이 파일의 격리 목록을 대조하니
    `organic_materials.data_path`(AGRODSS_ORGANIC_PATH) 하나가 빠져 있었다 — 갱신 작업을 부르는 검사가 생기면 운영 정본(790KB)에
    쓴다. 매 검사마다 복사하면 관문 한 번에 700MB 를 쓰므로 **세션에 한 번** 사본을 뜨고 그쪽을 가리킨다(읽기는 같고 쓰기는 사본)."""
    import shutil
    src = Path(__file__).resolve().parent.parent / "data" / "organic" / "organic_materials_public.json"
    dst = tmp_path_factory.mktemp("organic") / "organic_materials_public.json"
    shutil.copyfile(src, dst)
    mp = pytest.MonkeyPatch()
    mp.setenv("AGRODSS_ORGANIC_PATH", str(dst))
    yield
    mp.undo()
