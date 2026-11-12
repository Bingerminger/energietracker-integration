"""Pure helpers of the Energietracker integration.

No Home Assistant imports here, so the logic can be tested with the standard
library alone (tests/test_logic.py).

Energietracker answers every API call as ``{"success": true, "data": ...}``.
The integration reads two endpoints:

* ``GET /api/summary``: key figures per meter (stability class A,
  ``summary_version``),
* ``GET /api/todo``: the "To do" list (stability class A, ``todo_version``).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlsplit

API_PREFIX = "/api.php/api"

#: Oldest Energietracker the integration works with: ``GET /api/todo`` came
#: with 3.9.0. Older installations get a repair issue instead of empty sensors.
MIN_APP_VERSION = (3, 9, 0)

#: Sensors per meter, in this order.
METER_SENSORS = ("balance", "year_to_date", "forecast_12m", "days_since_reading")

#: Heating oil and pellets (Energietracker ``tank``): stock in the unit of the
#: tank (L or kg) and fill level in per cent.
TANK_SENSORS = ("tank_stock", "tank_level")

#: Feed-in (Energietracker 3.13.0, ``contract.payouts_*``): paid out in the
#: billing year, still outstanding up to today and at settlement.
PAYOUT_SENSORS = ("payouts_received", "payouts_open", "payouts_open_at_settle")

#: A group with a group contract (Energietracker 3.13.0,
#: ``group_forecast_12m``): forecast of the next 12 months and its costs with
#: standing charge.
GROUP_FORECAST_SENSORS = ("forecast_12m", "forecast_12m_cost")

#: Every sensor key a meter or a group can get.
ALL_METER_SENSORS = tuple(dict.fromkeys(METER_SENSORS + TANK_SENSORS + PAYOUT_SENSORS + GROUP_FORECAST_SENSORS))

#: Attributes of the balance sensor, taken from the meter's ``contract``
#: (Energietracker 3.10.0; older versions leave them empty).
BALANCE_ATTRIBUTES = (
    "projected_end_balance",
    "projected_end_balance_total",
    "projected_end_range_total",
    "measured_balance",
    "measured_until",
)

#: Attributes of the stock sensor, taken from the meter's ``tank``.
TANK_ATTRIBUTES = ("capacity", "estimated_from")

#: Units of a tank that get a device class; any other unit stays as it is.
TANK_UNIT_CLASSES = {"L": "volume_storage", "kg": "weight"}

#: Fields of a "To do" item that go into state attributes.
ITEM_FIELDS = ("title", "date", "kind", "severity")

#: How many "To do" items go into the attribute ``items`` (state attributes
#: are stored in the recorder; keep them small).
MAX_ITEMS = 20


def normalize_url(raw: str) -> str:
    """Base address of the app, without a trailing slash and without ``/api.php``.

    Accepts what people paste: ``http://nas.local:8080/``,
    ``http://nas.local:8080/energietracker/api.php`` or the address of the
    app in Home Assistant (``http://1a2b3c4d-energietracker``).
    """
    url = (raw or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("invalid_url")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError("invalid_url")
    path = parts.path.rstrip("/")
    for tail in ("/api.php/api", "/api.php", "/index.php"):
        if path.endswith(tail):
            path = path[: -len(tail)]
    netloc = parts.netloc
    return f"{parts.scheme}://{netloc}{path}"


def url_label(base: str) -> str:
    """Host, port and folder of a base address, for the title of the entry.

    ``http://nas.local:8080`` and ``http://nas.local/energietracker`` stay
    apart, where the host name alone would read the same twice.
    """
    parts = urlsplit(base)
    return f"{parts.netloc}{parts.path}"


def endpoint(base: str, name: str) -> str:
    """Full address of an endpoint (``summary``, ``todo``)."""
    return f"{base}{API_PREFIX}/{name}"


def clean_token(raw: str | None) -> str:
    """A read key as pasted, without a copied ``Bearer``."""
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def auth_headers(token: str | None) -> dict[str, str]:
    """Headers for a request; without a key none (sign-in switched off)."""
    token = clean_token(token)
    return {"Authorization": f"Bearer {token}"} if token else {}


def unwrap(payload: Any) -> dict[str, Any]:
    """The ``data`` of an answer; anything else is an invalid response."""
    if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("data"), dict):
        raise ValueError("invalid_response")
    return payload["data"]


def meter_sensor_keys(meter: dict[str, Any]) -> list[str]:
    """Which sensors a meter gets.

    The balance only with a current contract, the forecast not for heating
    oil and pellets (deliveries, ``tank``); consumption since 1 January and
    days since the last reading always. A tank adds stock and fill level, a
    feed-in contract with ``payouts_received`` (Energietracker 3.13.0) the
    three payout sensors.

    A group gets the balance and, from Energietracker 3.13.0 on, the forecast
    of the group contract.
    """
    if meter.get("group"):
        return ["balance"] + (list(GROUP_FORECAST_SENSORS) if "forecast_12m" in meter else [])
    keys = []
    for key in METER_SENSORS:
        if key == "balance" and meter.get("contract") is None:
            continue
        if key == "forecast_12m" and meter.get("tank") is not None:
            continue
        keys.append(key)
    if isinstance(meter.get("tank"), dict):
        keys.extend(TANK_SENSORS)
    contract = meter.get("contract")
    if isinstance(contract, dict) and contract.get("payouts_received") is not None:
        keys.extend(PAYOUT_SENSORS)
    return keys


def group_meters(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """One stand-in meter per group with a current group contract.

    The balance of a group contract (Energietracker 3.9.0, ``group_contract``
    at each member) belongs to the group; the members carry ``contract:
    null``. One balance sensor per group, so a sum over the balance sensors
    counts it once. Consumption stays with the members.

    Energietracker 3.13.0 adds ``group_forecast_12m`` at each member: the
    forecast of the group with standing charge and advance payment. The
    stand-in carries it as its ``forecast_12m`` (the key only when the app
    sends it, so an older app gets no forecast sensor for the group).
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for meter in summary.get("meters") or []:
        gc = meter.get("group_contract") if isinstance(meter, dict) else None
        if not isinstance(gc, dict) or not gc.get("group_id") or not isinstance(gc.get("contract"), dict):
            continue
        key = f"{meter.get('utility')}.group.{gc['group_id']}"
        if key in seen:
            continue
        seen.add(key)
        group = {
            "key": key,
            "utility": meter.get("utility"),
            "utility_label": meter.get("utility_label"),
            "name": gc.get("name") or gc["group_id"],
            "consumption_unit": meter.get("consumption_unit"),
            "contract": gc["contract"],
            "group": True,
        }
        if "group_forecast_12m" in meter:
            group["forecast_12m"] = meter.get("group_forecast_12m")
        out.append(group)
    return out


def all_meters(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The meters of the summary and one stand-in per group contract."""
    meters = [m for m in summary.get("meters") or [] if isinstance(m, dict) and m.get("key")]
    return meters + group_meters(summary)


def meter_value(meter: dict[str, Any], key: str) -> float | int | None:
    """Value of one meter sensor, ``None`` when Energietracker has none."""
    if key == "balance":
        return (meter.get("contract") or {}).get("balance")
    if key == "year_to_date":
        return (meter.get("year_to_date") or {}).get("value")
    if key == "forecast_12m":
        return (meter.get("forecast_12m") or {}).get("value")
    if key == "days_since_reading":
        return meter.get("days_since_reading")
    if key == "forecast_12m_cost":
        return (meter.get("forecast_12m") or {}).get("cost")
    if key == "tank_stock":
        return (meter.get("tank") or {}).get("stock")
    if key == "tank_level":
        return (meter.get("tank") or {}).get("percent")
    if key in PAYOUT_SENSORS:
        return (meter.get("contract") or {}).get(key)
    raise KeyError(key)


def balance_attributes(meter: dict[str, Any]) -> dict[str, Any]:
    """Expected and measured balance next to the balance up to today.

    ``projected_end_balance_total`` is what Energietracker's balance card shows
    as "expected at settlement" (the sum when one bill settles several
    contracts); ``projected_end_range_total`` is ``[low, high]`` when the
    estimate is uncertain, otherwise ``None``; ``measured_balance`` is the
    balance up to the last reading on ``measured_until``.
    """
    contract = meter.get("contract") or {}
    return {key: contract.get(key) for key in BALANCE_ATTRIBUTES}


def tank_attributes(meter: dict[str, Any]) -> dict[str, Any]:
    """Capacity of the tank (in the unit of the stock) and the day from which the stock is estimated.

    ``estimated_from`` is the last day with a known stock (initial stock, a
    delivery "filled up" or a tank reading); from then on Energietracker
    estimates the stock.
    """
    tank = meter.get("tank") or {}
    return {key: tank.get(key) for key in TANK_ATTRIBUTES}


def meter_kind(meter: dict[str, Any], key: str) -> tuple[str | None, str | None]:
    """(device class, unit) of a meter sensor as plain strings.

    ``energy`` for kWh, ``water`` for m³ of the utility ``wasser``,
    ``monetary`` in the currency of the installation, ``duration`` in days.
    The stock of a tank in its own unit: ``volume_storage`` for L,
    ``weight`` for kg, any other unit without a device class.
    """
    if key in ("balance", "forecast_12m_cost") or key in PAYOUT_SENSORS:
        return "monetary", None   # unit: the currency, from the summary
    if key == "days_since_reading":
        return "duration", "d"
    if key == "tank_level":
        return None, "%"
    if key == "tank_stock":
        unit = (meter.get("tank") or {}).get("unit") or None
        return TANK_UNIT_CLASSES.get(unit or ""), unit
    unit = meter.get("consumption_unit") or None
    if unit == "kWh":
        return "energy", "kWh"
    if unit == "m³":
        return ("water" if meter.get("utility") == "wasser" else None), "m³"
    return None, unit


def device_name(meter: dict[str, Any]) -> str:
    """``Strom Hauptzähler`` — name of the utility and of the meter.

    ``utility_label`` comes with Energietracker 3.9.0; before that the key of
    the utility stands in.
    """
    label = meter.get("utility_label") or meter.get("utility") or ""
    name = meter.get("name") or meter.get("meter_id") or ""
    return f"{label} {name}".strip()


def todo_next(todo: dict[str, Any]) -> dict[str, Any] | None:
    """The next due item (overdue first, then urgent, then by date)."""
    nxt = todo.get("next")
    return nxt if isinstance(nxt, dict) else None


def todo_upcoming(todo: dict[str, Any]) -> dict[str, Any] | None:
    """The next appointment that is not due yet (Energietracker 3.10.0)."""
    nxt = todo.get("next_upcoming")
    return nxt if isinstance(nxt, dict) else None


def item_fields(item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Only the fields a card needs."""
    return {k: item.get(k) for k in ITEM_FIELDS} if isinstance(item, dict) else None


def todo_items(todo: dict[str, Any]) -> list[dict[str, Any]]:
    """The first MAX_ITEMS items, only the fields a card needs."""
    return [item_fields(item) for item in (todo.get("items") or [])[:MAX_ITEMS] if isinstance(item, dict)]


def todo_attributes(todo: dict[str, Any]) -> dict[str, Any]:
    """Attributes of the sensor "To do".

    ``soon`` counts the appointments that fall due within the lead time of
    "due soon" in Energietracker, ``next_upcoming`` is the next of them (both
    3.10.0; ``None`` before).
    """
    return {
        "overdue": todo.get("overdue"),
        "soon": todo.get("soon"),
        "next_upcoming": item_fields(todo_upcoming(todo)),
        "items": todo_items(todo),
    }


def parse_version(value: Any) -> tuple[int, int, int] | None:
    """``"3.10.0"`` to ``(3, 10, 0)``; a suffix such as ``-dev`` is ignored."""
    if not isinstance(value, str):
        return None
    parts = []
    for part in value.strip().lstrip("vV").split(".")[:3]:
        digits = ""
        for ch in part:
            if not ch.isdigit():
                break
            digits += ch
        if digits == "":
            return None
        parts.append(int(digits))
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]


def app_too_old(summary: dict[str, Any]) -> str | None:
    """The app version when it is older than MIN_APP_VERSION, otherwise ``None``.

    An unreadable version counts as new enough: the integration then tries
    and reports a missing endpoint as an invalid response.
    """
    version = parse_version(summary.get("app_version"))
    if version is None or version >= MIN_APP_VERSION:
        return None
    return str(summary.get("app_version")).strip()


def min_app_version() -> str:
    return ".".join(str(n) for n in MIN_APP_VERSION)


def parse_date(value: Any) -> date | None:
    """``YYYY-MM-DD`` to a date; anything else ``None``."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
