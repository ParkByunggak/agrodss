# -*- coding: utf-8 -*-
# [M-11 몰 MVP 목업] 상품 = 재배 단위 · 상세 = 촬영 칸 시계열 · 인증서 없이 인증 표기 금지 · 판정은 consumer_visible+판단함만 ·
#        뷰 어디에도 필지 상세·원본 값·파일 경로가 없다(재귀 게이트) · 화면 경로.
from __future__ import annotations

import http.client
import threading
from datetime import date, datetime, timezone
from urllib.parse import quote

import pytest

from frontend import config, serve
from ingest import media
from judge.envelope import Envelope
from mall import product as mp
from tests.test_media import make_mp4

SID = "p001-jjokpa-2026f"
T25 = date(2026, 9, 19)


def test_product_view_is_video_timeline_without_pii():
    key = media.save_upload("clip.mp4", make_mp4(datetime(2026, 9, 18, 1, 0, tzinfo=timezone.utc), gps="+36.8000+128.0000/"))
    rec = media.register(key, SID, note="두둑 전경")
    assert rec["gps"]                                                          # 원장에는 좌표가 있다
    v = mp.product_view(SID, today=T25)
    assert v["product_id"] == SID and v["title"] == "쪽파 · 2026 가을" and v["clips_total"] == 1
    tl = {t["stage"]: t for t in v["timeline"]}
    assert len(tl) == 5 and tl["3. 생육 초기 (잎 2~4매)"]["state"] == "촬영됨" and tl["3. 생육 초기 (잎 2~4매)"]["clips"][0]["kind"] == "영상"
    assert tl["1. 종구 준비 · 파종"]["state"] == "미촬영(창 지남)" and tl["5. 수확"]["state"] == "촬영 예정"
    mp.assert_public(v)
    flat = str(v)
    assert "36.8" not in flat and "gps" not in flat and "address" not in flat and "sha256" not in flat and "갈금리" not in flat


def test_cert_label_requires_legal_certificate():
    s = {"cert": "유기"}
    assert mp.cert_label({"cert_claimed": "유기"}, s) == mp.NO_CERT_LABEL
    assert mp.cert_label(None, s) == mp.NO_CERT_LABEL
    assert mp.cert_label({"cert_claimed": "유기", "cert_legal": True}, s) == "유기 인증(인증서 확인)"
    assert mp.cert_label({"cert_claimed": "유기", "cert_legal": False}, s) == mp.NO_CERT_LABEL
    assert mp.product_view(SID, today=T25)["cert_label"] == mp.NO_CERT_LABEL      # 첫 농가: 주장만 있고 인증서 미확인


def test_judgments_only_when_consumer_visible_and_judged():
    e1 = Envelope("판단함", "harvest_timing", SID, "2026-09-19T00:00:00", grade="추정", result={"summary": "창 10-14~11-03"})
    e2 = Envelope("판단함", "harvest_timing", SID, "2026-09-19T00:00:00", grade="추정", consumer_visible=True, result={"summary": "창 10-14~11-03"})
    e3 = Envelope("판단 불가(데이터)", "replant", SID, "2026-09-19T00:00:00", consumer_visible=True, missing=[{"axis": "observation", "who_can_fill": "x"}])
    assert mp.visible_judgments([e1]) == []
    out = mp.visible_judgments([e1, e2, e3])
    assert len(out) == 1 and out[0]["decision"] == "수확 시기" and out[0]["as_of"] == "2026-09-19" and out[0]["basis"]
    assert mp.product_view(SID, today=T25)["judgments"] == []                      # D-2 전: 실질 0건


def test_assert_public_catches_forbidden_keys_anywhere():
    mp.assert_public({"a": [{"b": {"c": 1}}]})
    with pytest.raises(mp.MallBoundaryError, match="gps"):
        mp.assert_public({"timeline": [{"clips": [{"gps": [1, 2]}]}]})
    with pytest.raises(mp.MallBoundaryError, match="soil_chem"):
        mp.assert_public({"x": {"soil_chem": {}}})


def test_mall_page_renders_and_unknown_product_404(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        port = s.server_address[1]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("GET", f"/mall/{quote(SID)}")
        r = c.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "목업" in body and "촬영 예정" in body and mp.NO_CERT_LABEL in body and "예약 판매 없음" in body
        assert "갈금리" not in body and 'class="brand"' in body
        c.request("GET", "/mall/nope")
        r = c.getresponse()
        assert r.status == 404
        r.read()
    finally:
        s.shutdown()
        s.server_close()
