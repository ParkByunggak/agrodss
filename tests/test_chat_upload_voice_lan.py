# -*- coding: utf-8 -*-
# [M-13 · 발행자 2026-09-19] 채팅 입력창 사진·영상 반입(메타 시각 · 없으면 날짜 요구 · inbox 잔류) · 음성 5초 무신호 종료 상수 ·
#        휴대폰 동기화(D-16) 옵트인 — 토큰 없으면 루프백 밖 바인드 거부, 토큰 있으면 쿠키/쿼리 없는 요청은 401.
from __future__ import annotations

import http.client
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from frontend import chat_pages, config, serve
from ingest import chat, media
from schema import records as sch
from tests.test_media import make_mp4

SID = "p001-jjokpa-2026f"


def make_jpeg_with_exif(dt: str | None) -> bytes:
    """최소 JPEG: SOI + APP1(Exif, TIFF little-endian, IFD0 에 DateTime 0x0132 하나) + EOI."""
    if dt is None:
        return b"\xff\xd8\xff\xd9"
    s = dt.encode("ascii") + b"\x00"                          # "YYYY:MM:DD HH:MM:SS\0" = 20 bytes
    ifd = struct.pack("<H", 1) + struct.pack("<HHII", 0x0132, 2, len(s), 8 + 2 + 12 + 4) + struct.pack("<I", 0)
    tiff = b"II*\x00" + struct.pack("<I", 8) + ifd + s
    app1 = b"Exif\x00\x00" + tiff
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


# ── 사진 메타 · 반입 ────────────────────────────────────────────────────────────────
def test_probe_image_reads_exif_datetime_or_says_missing(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_bytes(make_jpeg_with_exif("2026:09:18 07:12:30"))
    assert media.probe_image(p).creation_time == "2026-09-18T07:12:30"
    q = tmp_path / "b.jpg"
    q.write_bytes(make_jpeg_with_exif(None))
    pr = media.probe_image(q)
    assert pr.creation_time is None and "입력 필요" in (pr.error or "")


def test_save_upload_then_register_image_and_video():
    key = media.save_upload("잎 근접.jpg", make_jpeg_with_exif("2026:09:18 07:12:30"))
    assert key.startswith("inbox:")
    rec = media.register(key, SID, note="잎 근접")
    assert rec["kind"] == "observation.image" and rec["id"].startswith("img_") and rec["observed_at"] == "2026-09-18T07:12:30"
    sch.validate(rec)
    key2 = media.save_upload("clip.mp4", make_mp4(datetime(2026, 9, 18, 1, 0, tzinfo=timezone.utc)))
    rec2 = media.register(key2, SID)
    assert rec2["kind"] == "observation.video" and rec2["observed_at_source"] == "file_meta"
    with pytest.raises(media.RegisterError, match="영상·사진 파일이 아니다"):
        media.save_upload("memo.txt", b"x")
    with pytest.raises(media.RegisterError, match="빈 파일"):
        media.save_upload("x.jpg", b"")
    media.save_upload("dup.mp4", b"\x00" * 16)
    assert media.save_upload("dup.mp4", b"\x00" * 16) == "inbox:dup_1.mp4"   # 같은 이름이 inbox 에 있으면 뒤에 번호


def test_an_image_without_exif_is_taken_in_and_a_typed_date_still_wins():
    """[발행자 2026-09-23] EXIF 없는 사진도 들어간다(이름에도 날짜가 없으면 '올린 때'). 그리고 **적어 주신 날짜가 가장 세다**
    — 발행자 요청 둘째: *"사진을 올릴 때 특정 날짜를 지정하면 그 날짜를 시스템이 인식해야 한다."*"""
    key = media.save_upload("no_exif.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID)
    assert rec["observed_at_source"] == "upload_time"
    key2 = media.save_upload("no_exif2.jpg", make_jpeg_with_exif(None) + b"\x00")   # 다른 바이트 — 같은 파일 거부와 섞지 않는다
    rec2 = media.register(key2, SID, observed_at="2026-09-19")
    assert rec2["observed_at_source"] == "manual" and rec2["observed_at"] == "2026-09-19"


def test_chat_send_with_media_refs_makes_message_and_reply():
    key = media.save_upload("a.jpg", make_jpeg_with_exif("2026:09:18 07:12:30"))
    rec = media.register(key, SID)
    m, r = chat.send(SID, "", media_refs=[rec], now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    assert m["input_mode"] == "file" and m["media_refs"] == [rec["id"]] and m["text"].startswith("[반입]")
    assert rec["id"] in r["text"]          # 받은 것을 말한다(문면은 사람 말로 바뀔 수 있다)
    m2, r2 = chat.send(SID, "잎 끝이 누렇게 보인다", media_refs=[rec], now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    assert m2["drafts"][0]["kind"] == "observation.note" and rec["id"] in r2["text"]
    assert chat.plain_why(m2["drafts"][0]) in r2["text"]


# ── 화면 · HTTP multipart ──────────────────────────────────────────────────────────
def _multipart(fields: dict[str, str], files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    b = b"----agrodssBoundary7"
    out = b""
    for k, v in fields.items():
        out += b"--" + b + b"\r\nContent-Disposition: form-data; name=\"" + k.encode() + b"\"\r\n\r\n" + v.encode("utf-8") + b"\r\n"
    for name, fn, data in files:
        out += (b"--" + b + b"\r\nContent-Disposition: form-data; name=\"" + name.encode() + b"\"; filename=\"" + fn.encode("utf-8")
                + b"\"\r\nContent-Type: application/octet-stream\r\n\r\n" + data + b"\r\n")
    out += b"--" + b + b"--\r\n"
    return out, "multipart/form-data; boundary=" + b.decode()


def test_parse_body_multipart_and_urlencoded():
    body, ct = _multipart({"text": "잎 근접", "observed_at": ""}, [("file", "a.jpg", b"\xff\xd8\xff\xd9")])
    fields, files = serve.parse_body(ct, body)
    assert fields == {"text": "잎 근접", "observed_at": ""} and files == [("a.jpg", b"\xff\xd8\xff\xd9")]
    fields, files = serve.parse_body("application/x-www-form-urlencoded", b"text=%EC%95%88%EB%85%95&x=1")
    assert fields == {"text": "안녕", "x": "1"} and files == []


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def _post_multipart(port, path, fields, files):
    body, ct = _multipart(fields, files)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=body, headers={"Content-Type": ct, "Content-Length": str(len(body))})
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def test_upload_through_chat_composer(srv):
    st, loc, _ = _post_multipart(srv, f"/c/{quote(SID)}/send", {"text": "두둑 전경", "observed_at": ""},
                                 [("file", "field.jpg", make_jpeg_with_exif("2026:09:19 08:00:00"))])
    assert st == 302
    recs = media.list_records(SID)
    assert len(recs) == 1 and recs[0]["kind"] == "observation.image" and recs[0]["note"] == "두둑 전경"
    msgs = chat.list_messages(SID)
    assert msgs[0]["media_refs"] == [recs[0]["id"]] and recs[0]["id"] in msgs[1]["text"]
    # [발행자 2026-09-23] 전에는 여기서 400 + "반입 대기함" 이었다 — EXIF 없는 사진은 **언제나** 거절당했다.
    # 이제 사다리가 받고(이 이름엔 날짜가 없으니 '올린 때'), 답이 **어디서 온 시각인지**를 말한다.
    st, loc, _ = _post_multipart(srv, f"/c/{quote(SID)}/send", {"text": "", "observed_at": ""},
                                 [("file", "noexif.jpg", make_jpeg_with_exif(None) + b"\x01")])
    assert st == 302
    recs2 = media.list_records(SID)
    assert len(recs2) == 2 and recs2[-1]["observed_at_source"] == "upload_time"
    assert "올리신 때" in chat.list_messages(SID)[-1]["text"]
    assert not any(i["name"].startswith("noexif") for i in media.list_inbox()), "이제 반입 대기함에 남지 않는다"
    st, _, body = _post_multipart(srv, f"/c/{quote(SID)}/send", {"text": "", "observed_at": ""}, [])
    assert st == 400 and "빈 발화" in body


def test_composer_has_attach_and_silence_constants():
    html = chat_pages.thread_main({"id": SID, "label": "x"}, datetime(2026, 9, 19).date())
    assert 'id="attach"' in html and 'type="file"' in html and 'enctype="multipart/form-data"' in html and 'name="observed_at"' in html
    assert f"SILENCE_MS = {config.VOICE_SILENCE_MS}" in html and "armSilence" in html and "rec.continuous = true" in html
    assert config.VOICE_SILENCE_MS == 5000


# ── D-16 동기화 옵트인 ─────────────────────────────────────────────────────────────
def test_lan_bind_refused_without_token_and_allowed_with(monkeypatch):
    monkeypatch.setattr(config, "LAN_TOKEN", "")
    with pytest.raises(RuntimeError, match="D-6"):
        config.assert_local("0.0.0.0")
    monkeypatch.setattr(config, "LAN_TOKEN", "short")
    with pytest.raises(RuntimeError, match="D-6"):
        config.assert_local("0.0.0.0")
    monkeypatch.setattr(config, "LAN_TOKEN", "x" * config.LAN_TOKEN_MIN)
    assert config.assert_local("0.0.0.0") == "0.0.0.0"
    with pytest.raises(RuntimeError):
        config.assert_local("192.168.0.10")                                 # 특정 주소도 안 된다 — 옵트인 형태는 하나
    assert config.assert_local("127.0.0.1") == "127.0.0.1"


def test_token_gate_401_then_cookie(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    monkeypatch.setattr(config, "LAN_TOKEN", "t" * 20)
    s = serve.make_server()                                                  # BIND 는 여전히 루프백 — 토큰만 켠다
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        port = s.server_address[1]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("GET", f"/c/{quote(SID)}")
        r = c.getresponse()
        assert r.status == 401
        r.read()
        c.request("GET", f"/c/{quote(SID)}?t=" + "t" * 20)
        r = c.getresponse()
        assert r.status == 200 and config.COOKIE_NAME in (r.getheader("Set-Cookie") or "")
        r.read()
        c.request("GET", f"/c/{quote(SID)}", headers={"Cookie": f"{config.COOKIE_NAME}=" + "t" * 20})
        r = c.getresponse()
        assert r.status == 200
        r.read()
    finally:
        s.shutdown()
        s.server_close()
