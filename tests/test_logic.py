"""Tests of the pure logic (custom_components/energietracker/logic.py).

Standard library only, no Home Assistant needed:

    python3 -I -m unittest discover -s tests

logic.py is loaded by its path: the package itself (``__init__.py``) imports
Home Assistant.
"""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import unittest

_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "energietracker" / "logic.py"
_SPEC = importlib.util.spec_from_file_location("energietracker_logic", _PATH)
logic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(logic)

# A meter as /api/summary returns it (invented values).
STROM = {
    "key": "strom.m_strom_main", "utility": "strom", "meter_id": "m_strom_main", "name": "Hauptzähler",
    "unit": "kWh", "consumption_unit": "kWh", "days_since_reading": 7,
    "year_to_date": {"value": 2318.7, "estimated": True},
    "contract": {"balance": -41.3, "provider": "Stadtwerke Musterstadt",
                 # Energietracker 3.10.0: expected and measured balance
                 "projected_end_balance": -12.5, "projected_end_balance_total": -30.25,
                 "projected_end_range_total": [-80.0, 15.0], "measured_balance": -38.9,
                 "measured_until": "2026-10-27", "verdict": "refund"},
    "forecast_12m": {"value": 3120.4, "cost": 1080.55}, "tank": None, "capture": "counter",
    "utility_label": "Strom",
}
WASSER = {"key": "wasser.m_w", "utility": "wasser", "name": "Garten", "consumption_unit": "m³",
          "contract": None, "forecast_12m": None, "tank": None, "year_to_date": None, "days_since_reading": None}
HEIZOEL = {"key": "heizoel.m_t", "utility": "heizoel", "name": "Tank", "consumption_unit": "kWh",
           "contract": {"balance": None}, "forecast_12m": None, "tank": {"stock": 1200}}
# Energietracker 3.13.0: tank as /api/summary returns it (invented values)
OELTANK = {"key": "heizoel.m_oel", "utility": "heizoel", "utility_label": "Heizöl", "name": "Keller",
           "consumption_unit": "kWh", "contract": None, "forecast_12m": None, "days_since_reading": None,
           "year_to_date": {"value": 4120.0, "estimated": True},
           "tank": {"stock": 2631.8, "capacity": 3000.0, "unit": "L", "percent": 87.7, "estimated_from": "2025-09-17"}}
PELLETS = {"key": "pellets.m_lager", "utility": "pellets", "name": "Lager", "consumption_unit": "kWh",
           "contract": None, "forecast_12m": None,
           "tank": {"stock": 4635.4, "capacity": 5000.0, "unit": "kg", "percent": 92.7, "estimated_from": None}}
# Energietracker 3.13.0: feed-in with payouts in the billing year (invented values)
EINSPEISUNG = {"key": "pv_einspeisung.m_pv", "utility": "pv_einspeisung", "utility_label": "PV-Einspeisung",
               "name": "Netz", "consumption_unit": "kWh", "days_since_reading": 3, "tank": None,
               "year_to_date": {"value": 5210.4, "estimated": False}, "forecast_12m": {"value": 6542.6, "cost": 536.48},
               "contract": {"balance": 522.14, "projected_end_balance": 539.9,
                            "payouts_received": 60.0, "payouts_open": 462.14, "payouts_open_at_settle": 479.9}}


class UrlTest(unittest.TestCase):
    def test_what_people_paste(self):
        for raw, want in [
            ("http://nas.local:8080", "http://nas.local:8080"),
            ("  http://nas.local:8080/  ", "http://nas.local:8080"),
            ("http://nas.local/energietracker/api.php", "http://nas.local/energietracker"),
            ("http://nas.local/energietracker/api.php/api", "http://nas.local/energietracker"),
            ("https://192.168.178.20/energietracker/index.php", "https://192.168.178.20/energietracker"),
            ("http://1a2b3c4d-energietracker", "http://1a2b3c4d-energietracker"),
        ]:
            self.assertEqual(want, logic.normalize_url(raw), raw)

    def test_refused(self):
        for raw in ["", "nas.local:8080", "ftp://nas.local", "http://", "http://nas.local/?x=1",
                    "http://user:pw@nas.local", "http://nas.local/#a"]:
            with self.assertRaises(ValueError, msg=raw):
                logic.normalize_url(raw)

    def test_label_keeps_installations_apart(self):
        self.assertEqual("nas.local:8080", logic.url_label("http://nas.local:8080"))
        self.assertEqual("nas.local/energietracker", logic.url_label("https://nas.local/energietracker"))

    def test_endpoint(self):
        self.assertEqual("http://nas.local:8080/api.php/api/todo", logic.endpoint("http://nas.local:8080", "todo"))
        self.assertEqual("http://nas.local/et/api.php/api/summary", logic.endpoint("http://nas.local/et", "summary"))


class TokenTest(unittest.TestCase):
    def test_bearer_once(self):
        self.assertEqual({"Authorization": "Bearer etk_abc"}, logic.auth_headers("etk_abc"))
        self.assertEqual({"Authorization": "Bearer etk_abc"}, logic.auth_headers(" Bearer etk_abc "))
        self.assertEqual({}, logic.auth_headers(""))
        self.assertEqual({}, logic.auth_headers(None))


class ResponseTest(unittest.TestCase):
    def test_unwrap(self):
        self.assertEqual({"count": 0}, logic.unwrap({"success": True, "data": {"count": 0}}))
        for bad in [None, [], {"success": False, "error": "x"}, {"success": True, "data": []}, {"data": {}}]:
            with self.assertRaises(ValueError):
                logic.unwrap(bad)


class MeterTest(unittest.TestCase):
    def test_which_sensors(self):
        self.assertEqual(["balance", "year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(STROM))
        self.assertEqual(["year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(WASSER),
                         "without a contract no balance")
        self.assertEqual(["balance", "year_to_date", "days_since_reading", "tank_stock", "tank_level"],
                         logic.meter_sensor_keys(HEIZOEL), "deliveries have no forecast, but stock and fill level")

    def test_values_and_missing_values(self):
        self.assertEqual(-41.3, logic.meter_value(STROM, "balance"))
        self.assertEqual(2318.7, logic.meter_value(STROM, "year_to_date"))
        self.assertEqual(3120.4, logic.meter_value(STROM, "forecast_12m"))
        self.assertEqual(7, logic.meter_value(STROM, "days_since_reading"))
        for key in ("year_to_date", "forecast_12m", "days_since_reading"):
            self.assertIsNone(logic.meter_value(WASSER, key), key)
        self.assertIsNone(logic.meter_value(HEIZOEL, "balance"))
        with self.assertRaises(KeyError):
            logic.meter_value(STROM, "unknown")

    def test_device_class_and_unit(self):
        self.assertEqual(("energy", "kWh"), logic.meter_kind(STROM, "year_to_date"))
        self.assertEqual(("water", "m³"), logic.meter_kind(WASSER, "forecast_12m"))
        self.assertEqual(("monetary", None), logic.meter_kind(STROM, "balance"))
        self.assertEqual(("duration", "d"), logic.meter_kind(STROM, "days_since_reading"))
        self.assertEqual((None, "m³"), logic.meter_kind({"utility": "gas", "consumption_unit": "m³"}, "year_to_date"))

    def test_device_name(self):
        self.assertEqual("Strom Hauptzähler", logic.device_name(STROM))
        self.assertEqual("wasser Garten", logic.device_name(WASSER), "before 3.9.0 without utility_label")

    def test_group_contract_once_per_group(self):
        gc = {"group_id": "g_wp", "name": "Wärmepumpe", "contract": {"balance": -23.6, "projected_end_balance": -10.0}}
        ht = {"key": "strom.m_ht", "utility": "strom", "utility_label": "Strom", "name": "WP HT", "contract": None,
              "group_contract": gc, "consumption_unit": "kWh", "tank": None}
        nt = dict(ht, key="strom.m_nt", name="WP NT")
        summary = {"meters": [STROM, ht, nt, WASSER, {"no": "key"}]}
        groups = logic.group_meters(summary)
        self.assertEqual(1, len(groups), "two members, one group")
        group = groups[0]
        self.assertEqual("strom.group.g_wp", group["key"])
        self.assertEqual(["balance"], logic.meter_sensor_keys(group), "consumption stays with the members")
        self.assertEqual(-23.6, logic.meter_value(group, "balance"))
        self.assertEqual(-10.0, logic.balance_attributes(group)["projected_end_balance"])
        self.assertEqual("Strom Wärmepumpe", logic.device_name(group))
        self.assertEqual(["year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(ht),
                         "members: no balance of their own")
        self.assertEqual(["strom.m_strom_main", "strom.m_ht", "strom.m_nt", "wasser.m_w", "strom.group.g_wp"],
                         [m["key"] for m in logic.all_meters(summary)])
        self.assertEqual([], logic.group_meters({"meters": [dict(ht, group_contract=None)]}))
        self.assertEqual([], logic.group_meters({"meters": [dict(ht, group_contract={"group_id": "g", "contract": None})]}))

    def test_summary_of_3_12_keeps_its_sensors(self):
        """Without the fields of 3.13.0 every meter keeps the sensors of integration 1.0."""
        self.assertEqual(["balance", "year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(STROM))
        feed_in_312 = dict(EINSPEISUNG, contract={"balance": 522.14, "projected_end_balance": 539.9})
        self.assertEqual(["balance", "year_to_date", "forecast_12m", "days_since_reading"],
                         logic.meter_sensor_keys(feed_in_312), "no payout keys, no payout sensors")
        tank_without_data = dict(OELTANK, tank=None)
        self.assertEqual(["year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(tank_without_data),
                         "a tank without stock (tank: null) stays as in 1.0")
        self.assertTrue(set(logic.METER_SENSORS) <= set(logic.ALL_METER_SENSORS))
        self.assertEqual(len(set(logic.ALL_METER_SENSORS)), len(logic.ALL_METER_SENSORS))

    def test_balance_attributes(self):
        self.assertEqual({
            "projected_end_balance": -12.5, "projected_end_balance_total": -30.25,
            "projected_end_range_total": [-80.0, 15.0], "measured_balance": -38.9, "measured_until": "2026-10-27",
        }, logic.balance_attributes(STROM), "only the five attributes, not provider or verdict")
        before_310 = {"contract": {"balance": 12.0, "projected_end_balance": 20.0}}
        attrs = logic.balance_attributes(before_310)
        self.assertEqual(20.0, attrs["projected_end_balance"])
        self.assertIsNone(attrs["projected_end_balance_total"], "Energietracker 3.9: key missing, attribute empty")
        self.assertEqual(set(logic.BALANCE_ATTRIBUTES), set(logic.balance_attributes(WASSER)))
        self.assertTrue(all(v is None for v in logic.balance_attributes(WASSER).values()))


class TankTest(unittest.TestCase):
    """Heating oil and pellets: stock and fill level from ``tank`` (Energietracker 3.13.0)."""

    def test_which_sensors(self):
        self.assertEqual(["year_to_date", "days_since_reading", "tank_stock", "tank_level"], logic.meter_sensor_keys(OELTANK))
        self.assertEqual(["year_to_date", "days_since_reading", "tank_stock", "tank_level"], logic.meter_sensor_keys(PELLETS))
        for meter in (STROM, WASSER, EINSPEISUNG):
            self.assertNotIn("tank_stock", logic.meter_sensor_keys(meter), meter["key"])

    def test_values(self):
        self.assertEqual(2631.8, logic.meter_value(OELTANK, "tank_stock"))
        self.assertEqual(87.7, logic.meter_value(OELTANK, "tank_level"))
        self.assertEqual(4635.4, logic.meter_value(PELLETS, "tank_stock"))
        self.assertEqual(92.7, logic.meter_value(PELLETS, "tank_level"))
        self.assertIsNone(logic.meter_value(dict(OELTANK, tank=None), "tank_stock"))
        self.assertIsNone(logic.meter_value(dict(OELTANK, tank={"stock": 10.0, "percent": None}), "tank_level"))

    def test_unit_as_in_the_app(self):
        self.assertEqual(("volume_storage", "L"), logic.meter_kind(OELTANK, "tank_stock"))
        self.assertEqual(("weight", "kg"), logic.meter_kind(PELLETS, "tank_stock"))
        self.assertEqual((None, "%"), logic.meter_kind(OELTANK, "tank_level"))
        other = dict(PELLETS, tank=dict(PELLETS["tank"], unit="Sack"))
        self.assertEqual((None, "Sack"), logic.meter_kind(other, "tank_stock"), "any other unit without a device class")
        self.assertEqual((None, None), logic.meter_kind(dict(PELLETS, tank=dict(PELLETS["tank"], unit="")), "tank_stock"))

    def test_attributes(self):
        self.assertEqual({"capacity": 3000.0, "estimated_from": "2025-09-17"}, logic.tank_attributes(OELTANK))
        self.assertEqual({"capacity": 5000.0, "estimated_from": None}, logic.tank_attributes(PELLETS))
        self.assertEqual({"capacity": None, "estimated_from": None}, logic.tank_attributes(dict(OELTANK, tank=None)))


class GroupForecastTest(unittest.TestCase):
    """``group_forecast_12m`` of a group with a group contract (Energietracker 3.13.0)."""

    GC = {"group_id": "g_wp", "name": "Wärmepumpe", "contract": {"balance": -23.6}}
    GF = {"group_id": "g_wp", "value": 773.1, "cost": 311.81, "low": 739.7, "high": 806.5}
    HT = {"key": "strom.m_ht", "utility": "strom", "utility_label": "Strom", "name": "WP HT", "contract": None,
          "group_contract": GC, "group_forecast_12m": GF, "consumption_unit": "kWh", "tank": None,
          "forecast_12m": {"value": 448.3, "cost": 122.86}}
    NT = dict(HT, key="strom.m_nt", name="WP NT", forecast_12m={"value": 324.8, "cost": 70.15})

    def group(self, *members):
        groups = logic.group_meters({"meters": list(members)})
        self.assertEqual(1, len(groups))
        return groups[0]

    def test_group_gets_forecast_and_costs(self):
        group = self.group(self.HT, self.NT)
        self.assertEqual(["balance", "forecast_12m", "forecast_12m_cost"], logic.meter_sensor_keys(group))
        self.assertEqual(773.1, logic.meter_value(group, "forecast_12m"), "HT + NT, from the group")
        self.assertEqual(311.81, logic.meter_value(group, "forecast_12m_cost"), "with standing charge")
        self.assertEqual(("energy", "kWh"), logic.meter_kind(group, "forecast_12m"), "unit of the members")
        self.assertEqual(("monetary", None), logic.meter_kind(group, "forecast_12m_cost"))

    def test_members_keep_their_sensors(self):
        self.assertEqual(["year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(self.HT))
        self.assertEqual(448.3, logic.meter_value(self.HT, "forecast_12m"), "the register's own forecast")

    def test_forecast_without_value(self):
        group = self.group(dict(self.HT, group_forecast_12m=None))
        self.assertEqual(["balance", "forecast_12m", "forecast_12m_cost"], logic.meter_sensor_keys(group),
                         "the app sends the key: the sensors exist, unknown until there is a forecast")
        self.assertIsNone(logic.meter_value(group, "forecast_12m"))
        self.assertIsNone(logic.meter_value(group, "forecast_12m_cost"))

    def test_app_before_3_13(self):
        member = {k: v for k, v in self.HT.items() if k != "group_forecast_12m"}
        group = self.group(member)
        self.assertEqual(["balance"], logic.meter_sensor_keys(group))
        self.assertNotIn("forecast_12m", group)


class PayoutTest(unittest.TestCase):
    """Payouts of the feed-in (Energietracker 3.13.0, ``contract.payouts_*``)."""

    def test_which_sensors(self):
        self.assertEqual(["balance", "year_to_date", "forecast_12m", "days_since_reading",
                          "payouts_received", "payouts_open", "payouts_open_at_settle"], logic.meter_sensor_keys(EINSPEISUNG))
        none_yet = dict(EINSPEISUNG, contract=dict(EINSPEISUNG["contract"], payouts_received=0.0,
                                                   payouts_open=522.14, payouts_open_at_settle=539.9))
        self.assertEqual(logic.meter_sensor_keys(EINSPEISUNG), logic.meter_sensor_keys(none_yet),
                         "0 received is a value: the sensors exist before the first payout")
        other = dict(STROM, contract=dict(STROM["contract"], payouts_received=None, payouts_open=None,
                                          payouts_open_at_settle=None))
        self.assertEqual(["balance", "year_to_date", "forecast_12m", "days_since_reading"], logic.meter_sensor_keys(other),
                         "other contracts carry the keys as null")

    def test_values_and_kind(self):
        self.assertEqual(60.0, logic.meter_value(EINSPEISUNG, "payouts_received"))
        self.assertEqual(462.14, logic.meter_value(EINSPEISUNG, "payouts_open"))
        self.assertEqual(479.9, logic.meter_value(EINSPEISUNG, "payouts_open_at_settle"))
        self.assertEqual(522.14, logic.meter_value(EINSPEISUNG, "balance"), "the balance stays the claim")
        for key in logic.PAYOUT_SENSORS:
            self.assertEqual(("monetary", None), logic.meter_kind(EINSPEISUNG, key), key)
            self.assertIsNone(logic.meter_value(dict(EINSPEISUNG, contract=None), key), key)

    def test_every_key_has_a_value_and_a_kind(self):
        for key in logic.ALL_METER_SENSORS:
            for meter in (STROM, OELTANK, EINSPEISUNG):
                logic.meter_value(meter, key)
                logic.meter_kind(meter, key)


class TodoTest(unittest.TestCase):
    TODO = {"count": 25, "overdue": 1,
            "next": {"uid": "reminder-r1", "kind": "reminder", "title": "Rauchmelder prüfen", "date": "2026-11-01", "severity": "overdue"},
            "items": [{"uid": f"u{i}", "kind": "reading_due", "title": f"Zähler {i}", "date": "2026-11-03", "severity": "due", "href": "#/"}
                      for i in range(25)]}

    def test_next_and_items(self):
        self.assertEqual("Rauchmelder prüfen", logic.todo_next(self.TODO)["title"])
        self.assertIsNone(logic.todo_next({"count": 0, "next": None, "items": []}))
        items = logic.todo_items(self.TODO)
        self.assertEqual(logic.MAX_ITEMS, len(items), "attributes stay small")
        self.assertEqual({"title", "date", "kind", "severity"}, set(items[0]))

    def test_dates(self):
        self.assertEqual(date(2026, 11, 1), logic.parse_date("2026-11-01"))
        self.assertEqual(date(2026, 11, 1), logic.parse_date("2026-11-01T08:00:00+01:00"))
        for bad in (None, "", "morgen", "2026-13-01", 20261101):
            self.assertIsNone(logic.parse_date(bad), bad)

    def test_upcoming_and_soon(self):
        todo = dict(self.TODO, soon=2, next_upcoming={
            "uid": "reminder-r9", "kind": "reminder", "title": "Heizung Wartung", "date": "2026-11-05",
            "severity": "upcoming", "href": "#/reminders"})
        self.assertEqual("Heizung Wartung", logic.todo_upcoming(todo)["title"])
        attrs = logic.todo_attributes(todo)
        self.assertEqual(["overdue", "soon", "next_upcoming", "items"], list(attrs))
        self.assertEqual(1, attrs["overdue"])
        self.assertEqual(2, attrs["soon"])
        self.assertEqual({"title": "Heizung Wartung", "date": "2026-11-05", "kind": "reminder", "severity": "upcoming"},
                         attrs["next_upcoming"], "without uid and href")
        self.assertEqual(logic.MAX_ITEMS, len(attrs["items"]))

    def test_upcoming_before_310(self):
        attrs = logic.todo_attributes(self.TODO)
        self.assertIsNone(attrs["soon"])
        self.assertIsNone(attrs["next_upcoming"])
        self.assertIsNone(logic.todo_upcoming({"next_upcoming": None}))
        self.assertIsNone(logic.todo_upcoming({"next_upcoming": "x"}))


class VersionTest(unittest.TestCase):
    def test_parse(self):
        for raw, want in [("3.10.0", (3, 10, 0)), (" 3.9.0\n", (3, 9, 0)), ("v3.12.1", (3, 12, 1)),
                          ("3.10.0-dev", (3, 10, 0)), ("10.0.0rc1", (10, 0, 0))]:
            self.assertEqual(want, logic.parse_version(raw), raw)
        for bad in (None, "", "3.10", "drei", "3.x.0", 3100):
            self.assertIsNone(logic.parse_version(bad), bad)

    def test_too_old(self):
        self.assertEqual("3.8.2", logic.app_too_old({"app_version": "3.8.2"}))
        self.assertEqual("2.16.0", logic.app_too_old({"app_version": "2.16.0\n"}))
        for ok in ("3.9.0", "3.10.0", "3.12.0", "4.0.0"):
            self.assertIsNone(logic.app_too_old({"app_version": ok}), ok)
        self.assertIsNone(logic.app_too_old({}), "unreadable counts as new enough")
        self.assertIsNone(logic.app_too_old({"app_version": ""}))
        self.assertEqual("3.9.0", logic.min_app_version())


if __name__ == "__main__":
    unittest.main()
