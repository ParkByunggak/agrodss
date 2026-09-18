# -*- coding: utf-8 -*-
# [I-7] 영상 반입 — 거부(시각 없음 · 중복 · 모르는 재배 단위)와 통과(메타 자동 · 수동 입력)를 둘 다 본다.
from __future__ import annotations

import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest import media

SUBJ = "p001-jjokpa-2026f"


def _atom(typ: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), typ) + payload


def make_mp4(creation_utc: datetime | None, w: int = 1920, h: int = 1080, gps: str | None = None) -> bytes:
    ct = int((creation_utc - media._QT_EPOCH).total_seconds()) if creation_utc else 0
    mvhd = _atom(b"mvhd", bytes([0, 0, 0, 0]) + struct.pack(">IIII", ct, ct, 1000, 12000) + bytes(80))
    tkhd = _atom(b"tkhd", bytes([0, 0, 0, 0]) + bytes(80) + struct.pack(">II", w << 16, h << 16))
    trak = _atom(b"trak", tkhd)
    udta = _atom(b"udta", _atom(b"\xa9xyz", struct.pack(">HH", len(gps), 0x15C7) + gps.encode())) if gps else b""
    moov = _atom(b"moov", mvhd + trak + udta)
    return _atom(b"ftyp", b"isom\x00\x00\x02\x00isomiso2mp41") + moov + _atom(b"mdat", b"\x00" * 64)


@pytest.fixture
def inbox(tmp_path):
    d = media.inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── 메타 판독 ───────────────────────────────────────────────────────────────────
def test_probe_reads_time_size_duration_gps(inbox):
    f = inbox / "a.mp4"
    f.write_bytes(make_mp4(datetime(2026, 9, 18, 6, 30, tzinfo=timezone.utc), gps="+36.7000+127.9000/"))
    p = media.probe_mp4(f)
    assert p.creation_time == "2026-09-18T06:30:00+00:00"
    assert (p.width, p.height) == (1920, 1080)
    assert p.duration_sec == 12.0
    assert p.gps == (36.7, 127.9)
    assert p.error is None


def test_probe_zero_time_is_none_not_epoch(inbox):
    f = inbox / "b.mp4"
    f.write_bytes(make_mp4(None))
    p = media.probe_mp4(f)
    assert p.creation_time is None          # 1904-01-01 로 메우지 않는다
    assert p.width == 1920


def test_probe_garbage_reports_error(inbox):
    f = inbox / "c.mp4"
    f.write_bytes(b"not a video at all")
    assert media.probe_mp4(f).error


# ── 등록: 통과 ───────────────────────────────────────────────────────────────────
def test_register_with_file_meta(inbox):
    (inbox / "a.mp4").write_bytes(make_mp4(datetime(2026, 9, 18, 6, 30, tzinfo=timezone.utc)))
    rec = media.register("a.mp4", SUBJ, note="파종 24일차")
    assert rec["kind"] == "observation.video"
    assert rec["observed_at"] == "2026-09-18T06:30:00+00:00" and rec["observed_at_source"] == "file_meta"
    assert rec["source"] == "farmer" and rec["resolution"] == "parcel" and rec["subject"] == SUBJ
    assert not (inbox / "a.mp4").exists()                      # inbox 에서 옮겨졌다
    assert (media.media_dir() / rec["file"]).exists()
    assert media.list_records(SUBJ)[0]["id"] == rec["id"]
    assert not media.list_inbox()


def test_register_with_manual_time_when_meta_missing(inbox):
    (inbox / "b.mp4").write_bytes(make_mp4(None))
    rec = media.register("b.mp4", SUBJ, observed_at="2026-09-18T15:30:00+09:00")
    assert rec["observed_at_source"] == "manual"


# ── 등록: 거부 ───────────────────────────────────────────────────────────────────
def test_register_rejects_when_no_time_anywhere(inbox):
    (inbox / "b.mp4").write_bytes(make_mp4(None))
    with pytest.raises(media.RegisterError, match="촬영 시각"):
        media.register("b.mp4", SUBJ)
    assert (inbox / "b.mp4").exists() and not media.list_records()   # 아무것도 안 바뀐다


def test_register_rejects_bad_time_format(inbox):
    (inbox / "b.mp4").write_bytes(make_mp4(None))
    with pytest.raises(media.RegisterError, match="형식"):
        media.register("b.mp4", SUBJ, observed_at="어제 오후")


def test_register_rejects_unknown_subject(inbox):
    (inbox / "a.mp4").write_bytes(make_mp4(datetime(2026, 9, 18, tzinfo=timezone.utc)))
    with pytest.raises(media.RegisterError, match="재배 단위"):
        media.register("a.mp4", "nope")


def test_register_rejects_duplicate_sha(inbox):
    data = make_mp4(datetime(2026, 9, 18, tzinfo=timezone.utc))
    (inbox / "a.mp4").write_bytes(data)
    (inbox / "a2.mp4").write_bytes(data)
    media.register("a.mp4", SUBJ)
    with pytest.raises(media.RegisterError, match="이미 등록"):
        media.register("a2.mp4", SUBJ)


def test_register_rejects_path_escape(inbox):
    with pytest.raises(media.RegisterError):
        media.register("../subjects.json", SUBJ)


# ── 격리 · 공개 뷰 ─────────────────────────────────────────────────────────────────
def test_tests_do_not_touch_repo_media_dir():
    assert Path(os.environ["AGRODSS_MEDIA_DIR"]).resolve() != (media.ROOT / "data" / "media").resolve()


def test_public_view_hides_coordinates():
    v = media.public_view({"gps": [36.7, 127.9], "id": "x"})
    assert v["gps"] == "있음"
    assert media.public_view({"gps": None})["gps"] == "없음"


# ── 동기화 폴더(감시): 복사하고 원본은 그대로, 등록된 것은 목록에서 빠진다 ───────────────
def test_watch_dir_copies_and_marks_seen(tmp_path, monkeypatch):
    phone = tmp_path / "OneDrive_camera"
    phone.mkdir()
    (phone / "VID_0001.mp4").write_bytes(make_mp4(datetime(2026, 9, 18, 7, 0, tzinfo=timezone.utc)))
    (phone / "IMG_0001.jpg").write_bytes(b"jpeg")            # 사진은 목록에 안 뜬다
    monkeypatch.setenv("AGRODSS_WATCH_DIRS", str(phone))
    items = media.list_inbox()
    assert [i["key"] for i in items] == ["watch:0:VID_0001.mp4"]
    rec = media.register("watch:0:VID_0001.mp4", SUBJ)
    assert rec["origin"] == "watch"
    assert (phone / "VID_0001.mp4").exists()                  # 원본 유지 — 폰에서 지워지지 않는다
    assert (media.media_dir() / rec["file"]).exists()
    assert media.list_inbox() == []                            # 등록된 것은 다시 안 뜬다


def test_watch_dir_missing_is_ignored(monkeypatch):
    monkeypatch.setenv("AGRODSS_WATCH_DIRS", "C:\\없는\\폴더;")
    assert media.list_inbox() == []


def test_subjects_registry_has_first_unit_and_no_address():
    subs = media.load_subjects()
    assert any(s["id"] == SUBJ for s in subs)
    raw = media.SUBJECTS_PATH.read_text(encoding="utf-8")
    assert "번지" not in raw and "갈금리" not in raw     # PII 는 필지 레코드로
