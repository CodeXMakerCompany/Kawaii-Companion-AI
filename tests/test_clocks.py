"""Customer clocks: the time where the people you work with are, easy to read at a glance,
with a sun or moon and their working hours, under the Focus switch."""

import datetime
from zoneinfo import ZoneInfo

from kawaii.clocks import DEFAULT_CLOCKS, Clocks
from kawaii.settings import StateStore

UTC = datetime.timezone.utc
COSTA_RICA = ZoneInfo("America/Costa_Rica")


def make(tmp_path, when, local=COSTA_RICA):
    return Clocks(StateStore(tmp_path / "s.json"), now=lambda: when, local=local)


def wed(hour, minute=0):
    return datetime.datetime(2026, 11, 25, hour, minute, tzinfo=UTC)  # a Wednesday


def test_costa_rica_argentina_and_colombia_come_first():
    assert [c["name"] for c in DEFAULT_CLOCKS[:3]] == ["Costa Rica", "Argentina", "Colombia"]


def people(rows):
    return [r for r in rows if not r["group"]]


def test_times_are_easy_to_read(tmp_path):
    rows = people(make(tmp_path, wed(15)).rows())
    assert [(r["name"], r["time"]) for r in rows] == [("Costa Rica", "9:00 am"), ("Argentina", "12:00 pm"),
                                                      ("Colombia", "10:00 am")]


def test_hours_ahead_or_behind_you(tmp_path):
    rows = people(make(tmp_path, wed(15)).rows())
    assert [r["diff"] for r in rows] == ["", "+3h", "+1h"]
    rows = people(make(tmp_path, wed(15), local=ZoneInfo("America/Argentina/Buenos_Aires")).rows())
    assert [r["diff"] for r in rows] == ["−3h", "", "−2h"]


def test_working_hours_and_daylight(tmp_path):
    rows = make(tmp_path, wed(23, 30)).rows()  # 5:30 pm in Costa Rica, 8:30 pm in Argentina
    assert rows[0]["working"] and rows[0]["day"]
    assert not rows[1]["working"] and not rows[1]["day"]


def test_nobody_works_on_weekends(tmp_path):
    saturday = datetime.datetime(2026, 11, 28, 16, 0, tzinfo=UTC)
    assert not any(r["working"] for r in people(make(tmp_path, saturday).rows()))


def test_your_own_list_from_state(tmp_path):
    store = StateStore(tmp_path / "s.json")
    store.set("clocks", [{"name": "Mexico", "tz": "America/Mexico_City"}, {"name": "Nowhere", "tz": "Mars/Base"}])
    rows = Clocks(store, now=lambda: wed(15), local=COSTA_RICA).rows()
    assert [r["name"] for r in rows] == ["Mexico"]  # an unknown time zone is skipped


def test_repaints_once_a_minute(tmp_path):
    t = [wed(15)]
    clocks = Clocks(StateStore(tmp_path / "s.json"), now=lambda: t[0], local=COSTA_RICA)
    first = clocks.rows()
    t[0] = wed(15) + datetime.timedelta(seconds=40)
    assert clocks.rows() == first
    t[0] = wed(15, 1)
    assert clocks.rows() != first


def test_the_cloud_zones_developers_watch(tmp_path):
    rows = {r["name"]: r for r in make(tmp_path, wed(15)).rows() if r["group"]}
    assert list(rows)[:3] == ["UTC", "us-east-1", "us-east-2"]
    assert {"us-west-2", "eu-west-1", "eu-central-1", "ap-south-1", "ap-southeast-1", "sa-east-1"} <= set(rows)
    assert rows["us-east-1"]["place"] == "Virginia" and rows["us-east-2"]["place"] == "Ohio"
    assert rows["UTC"]["time"] == "3:00 pm" and rows["UTC"]["diff"] == "+6h"
    assert rows["us-east-1"]["time"] == "10:00 am"
    assert rows["ap-south-1"]["diff"] == "+11.5h"


def test_servers_never_look_asleep(tmp_path):
    rows = [r for r in make(tmp_path, wed(4)).rows() if r["group"]]  # 4 am UTC
    assert all(r["working"] is None for r in rows)


def test_the_cloud_zones_fold_away_and_stay_folded(tmp_path):
    store = StateStore(tmp_path / "s.json")
    clocks = Clocks(store, now=lambda: wed(15), local=COSTA_RICA)
    shown = clocks.payload()
    assert shown["expanded"] and shown["hidden"] == 0 and any(r["group"] for r in shown["rows"])
    clocks.toggle()
    folded = Clocks(store, now=lambda: wed(15), local=COSTA_RICA).payload()
    assert not folded["expanded"] and folded["hidden"] == len(shown["rows"]) - 3
    assert [r["name"] for r in folded["rows"]] == ["Costa Rica", "Argentina", "Colombia"]
