# -*- coding: utf-8 -*-
# [⑤b 2026-09-28 · 발행자 승인 "제안 순서대로"] 장기 전망 입력 폼 — JSON 손 편집의 오류를 없앤다. 계약: 쓰기는 덮개(git 밖)에만 · 검증이 먼저(틀리면 400 · 아무것도
# 안 쓴다) · 같은 항목은 한 번만(더블탭) · 지우기는 덮개만 · 등재 직후 날씨 물음의 「장기」 줄에 나온다 · /me 에서 이어진다.
from __future__ import annotations

import http.client
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from frontend import chat_pages
from ingest import chat, media, outlook
from judge import run as judge_run
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 28)
FORM = {"period_type": "1개월", "issued_on": "2026-09-24", "target_from": "2026-10-05", "target_to": "2026-10-11", "region": "충북",
        "temp_above": "50", "temp_normal": "30", "temp_below": "20", "precip_above": "30", "precip_normal": "40", "precip_below": "30",
        "source_title": "기상청 1개월 전망(2026.10.5.~11.1.) 발표", "source_url": "https://www.weather.go.kr/w/climate/prediction/month1.do", "note": ""}


def _post(port, path, data):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", path, body=urlencode(data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def test_the_form_maps_to_the_same_columns_as_the_file():
    e = chat_pages.outlook_form_entry(FORM)
    assert set(e) <= outlook.ENTRY_KEYS and e["temp"] == {"above": 50.0, "normal": 30.0, "below": 20.0} and "note" not in e
    r = outlook.entry_to_record(e)
    assert r["region"] == "충북" and r["citation"]["url"] == FORM["source_url"]
    e2 = chat_pages.outlook_form_entry(dict(FORM, precip_above="", precip_normal="", precip_below=""))
    assert "precip" not in e2                                                              # 셋 다 비면 그 축은 없음(0 으로 지어내지 않는다)
    e3 = chat_pages.outlook_form_entry(dict(FORM, temp_above="많이"))
    assert e3["temp"]["above"] == "많이"                                                      # 숫자 아닌 것은 그대로 — 검증이 이유를 말한다


def test_a_valid_entry_is_written_to_the_overlay_only_and_shows_in_the_weather_answer(srv):
    local = Path(os.environ["AGRODSS_OUTLOOK_LOCAL_PATH"])
    seed = Path(os.environ["AGRODSS_OUTLOOK_PATH"])
    assert not local.exists()
    status, body = _post(srv, "/me/outlook", FORM)
    assert status == 200 and "등재 — 1개월 전망 2026-10-05 ~ 2026-10-11 · 충북" in body
    doc = json.loads(local.read_text(encoding="utf-8"))
    assert len(doc["entries"]) == 1 and doc["entries"][0]["region"] == "충북" and doc["entries"][0]["temp"] == {"above": 50.0, "normal": 30.0, "below": 20.0}
    assert not seed.exists()                                                               # 씨앗에는 아무것도 안 쓴다
    assert "2026-10-05 ~ 2026-10-11" in body and 'href="https://www.weather.go.kr' in body and "이 항목 지우기" in body
    s = media.load_subjects()[0]
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert e.kind == "사실 인용" and [p["from"] for p in e.result["long"]["periods"]] == ["2026-10-05"]   # 등재 직후 날씨 답에
    assert "10-05~10-11 충북 기온 높음 50%" in chat.answer(s, "다음 달 날씨 어때", TODAY)
    status, body = _post(srv, "/me/outlook", FORM)                                          # 더블탭 — 한 번만 남는다
    assert status == 200 and len(json.loads(local.read_text(encoding="utf-8"))["entries"]) == 1


def test_a_wrong_entry_is_refused_with_the_reason_and_nothing_is_written(srv):
    local = Path(os.environ["AGRODSS_OUTLOOK_LOCAL_PATH"])
    for patch, word in ((dict(temp_above="60"), "확률 합 110"), (dict(source_url=""), "source_url"), (dict(target_from="2026-10-12"), "뒤다"), (dict(temp_above="많이"), "숫자가 아니다")):
        status, body = _post(srv, "/me/outlook", dict(FORM, **patch))
        assert status == 400 and "저장하지 않았다" in body and word in body, (patch, body[:200])
        assert 'value="충북"' in body                                                          # 친 값은 폼에 남는다(다시 안 친다)
    assert not local.exists()


def test_delete_removes_only_the_overlay_entry_and_a_bad_line_is_shown_not_hidden(srv):
    local = Path(os.environ["AGRODSS_OUTLOOK_LOCAL_PATH"])
    _post(srv, "/me/outlook", FORM)
    _post(srv, "/me/outlook", dict(FORM, target_from="2026-10-12", target_to="2026-10-18"))
    doc = json.loads(local.read_text(encoding="utf-8"))
    doc["entries"].append({"period_type": "1개월", "issued_on": "2026-09-24", "target_from": "2026-10-19", "target_to": "2026-10-25", "region": "충북",
                           "temp": {"above": 90, "normal": 30, "below": 20}, "source_title": "x y", "source_url": "https://example.invalid/"})   # 손으로 넣은 틀린 줄
    local.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    status, body = _get(srv, "/me/outlook")
    assert status == 200 and "못 읽음 — 덮개 3번째" in body and "확률 합 140" in body and body.count("이 항목 지우기") == 3
    status, body = _get(srv, "/changes")                                                    # 버린 줄이 /changes 에도 — 그때만 보이는 문단이 안쪽 말을 하면 안 된다
    assert status == 200 and "climate_outlook_local.json#2" in body and "정본 미도착" not in body and "장기 전망 등재분" in body
    status, body = _post(srv, "/me/outlook/delete", {"index": "2"})
    assert status == 200 and "지움 — 1개월 2026-10-19 ~ 2026-10-25 충북" in body and len(json.loads(local.read_text(encoding="utf-8"))["entries"]) == 2
    status, body = _post(srv, "/me/outlook/delete", {"index": "7"})
    assert status == 400 and "지울 항목이 없다: 7" in body
    seed = Path(os.environ["AGRODSS_OUTLOOK_PATH"])
    seed.write_text(json.dumps({"entries": [dict(chat_pages.outlook_form_entry(FORM), target_from="2026-11-02", target_to="2026-11-08")]}, ensure_ascii=False), encoding="utf-8")
    status, body = _get(srv, "/me/outlook")
    assert "씨앗(저장소 · 세션 커밋)에도 1건 — 화면에서는 못 지운다" in body and body.count("이 항목 지우기") == 2


def test_me_links_to_the_form_and_the_form_has_no_pii_fields(srv):
    status, body = _get(srv, "/me")
    assert status == 200 and 'href="/me/outlook"' in body
    status, body = _get(srv, "/me/outlook")
    assert status == 200 and 'action="/me/outlook"' in body and "합 100(±5)" in body
    for pii in ("address", "pnu", "lat", "lon", "주소", "지번"):
        assert f'name="{pii}"' not in body


def test_the_overlay_writer_is_classified_as_a_runtime_write_outside_git():
    from tests import test_runtime_state_files as rs
    assert rs.WRITE_ACCESSORS.get("ingest.outlook") == ("local_path",) and rs.READ_ONLY.get("ingest.outlook") == ("path",)
    src = (Path(__file__).resolve().parent.parent / "ingest" / "outlook.py").read_text(encoding="utf-8")
    assert 'p.open("w", encoding="utf-8")' in src and "def append_local(" in src and "def remove_local(" in src
