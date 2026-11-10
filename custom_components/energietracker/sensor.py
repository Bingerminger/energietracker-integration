"""Sensors: "To do" for the installation, balance, consumption and forecast per meter."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN
from .coordinator import EnergietrackerConfigEntry, EnergietrackerCoordinator, instance_id
from .logic import (
    all_meters,
    balance_attributes,
    device_name,
    item_fields,
    meter_kind,
    meter_sensor_keys,
    meter_value,
    parse_date,
    todo_attributes,
    todo_next,
    todo_upcoming,
)

PARALLEL_UPDATES = 0   # the coordinator fetches, the entities only read

DEVICE_CLASSES = {
    "energy": SensorDeviceClass.ENERGY,
    "water": SensorDeviceClass.WATER,
    "monetary": SensorDeviceClass.MONETARY,
    "duration": SensorDeviceClass.DURATION,
}
UNITS = {"kWh": UnitOfEnergy.KILO_WATT_HOUR, "m³": UnitOfVolume.CUBIC_METERS, "d": UnitOfTime.DAYS}

#: Home Assistant 2026.8 links a device to its hub by the registry id
#: (``via_device_id``); the identifier pair (``via_device``) is deprecated and
#: goes away in 2027.8. Older versions only know the pair.
VIA_DEVICE_ID = "via_device_id" in (DeviceInfo.__optional_keys__ | DeviceInfo.__required_keys__)


def installation_device(coordinator: EnergietrackerCoordinator, instance: str) -> DeviceInfo:
    """The device "Energietracker" (one per installation)."""
    return DeviceInfo(
        identifiers={(DOMAIN, instance)},
        name="Energietracker",
        manufacturer="Energietracker",
        sw_version=str(coordinator.data.summary.get("app_version") or "") or None,
        configuration_url=coordinator.config_entry.data.get(CONF_URL),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergietrackerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    instance = instance_id(entry)
    # The installation first, so the meters can name it as their hub.
    hub = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, **installation_device(coordinator, instance))
    via: dict[str, Any] = {"via_device_id": hub.id} if VIA_DEVICE_ID else {"via_device": (DOMAIN, instance)}
    entities: list[SensorEntity] = [
        TodoCountSensor(coordinator, instance),
        TodoNextSensor(coordinator, instance),
        TodoNextDateSensor(coordinator, instance),
        TodoUpcomingSensor(coordinator, instance),
        TodoUpcomingDateSensor(coordinator, instance),
    ]
    # Meters (and groups with a group contract) as they are now; a new meter in
    # Energietracker appears after reloading the integration.
    for meter in all_meters(coordinator.data.summary):
        entities.extend(MeterSensor(coordinator, instance, meter, key, via) for key in meter_sensor_keys(meter))
    async_add_entities(entities)


class EnergietrackerEntity(CoordinatorEntity[EnergietrackerCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator)
        self._instance = instance

    def _installation(self) -> DeviceInfo:
        return installation_device(self.coordinator, self._instance)


# ── "To do" ────────────────────────────────────────────────────────────────


class TodoCountSensor(EnergietrackerEntity, SensorEntity):
    """Number of due items; overdue, due soon, next appointment and the items as attributes."""

    _attr_translation_key = "todo_count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clipboard-check-outline"
    # The list changes with every title; the recorder keeps only the numbers.
    _unrecorded_attributes = frozenset({"items", "next_upcoming"})

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator, instance)
        self._attr_unique_id = f"{instance}_todo_count"
        self._attr_device_info = self._installation()

    @property
    def native_value(self) -> int | None:
        count = self.coordinator.data.todo.get("count")
        return int(count) if isinstance(count, int) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return todo_attributes(self.coordinator.data.todo)


class TodoNextSensor(EnergietrackerEntity, SensorEntity):
    """Title of the next item (overdue first, then urgent, then by date)."""

    _attr_translation_key = "todo_next"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator, instance)
        self._attr_unique_id = f"{instance}_todo_next"
        self._attr_device_info = self._installation()

    @property
    def native_value(self) -> str | None:
        nxt = todo_next(self.coordinator.data.todo)
        return str(nxt.get("title"))[:255] if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = todo_next(self.coordinator.data.todo) or {}
        return {k: nxt.get(k) for k in ("date", "kind", "severity")}


class TodoNextDateSensor(EnergietrackerEntity, SensorEntity):
    """When the next item is due."""

    _attr_translation_key = "todo_next_date"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator, instance)
        self._attr_unique_id = f"{instance}_todo_next_date"
        self._attr_device_info = self._installation()

    @property
    def native_value(self) -> date | None:
        nxt = todo_next(self.coordinator.data.todo)
        return parse_date(nxt.get("date")) if nxt else None


class TodoUpcomingSensor(EnergietrackerEntity, SensorEntity):
    """Title of the next appointment that is not due yet (Energietracker 3.10.0)."""

    _attr_translation_key = "todo_upcoming"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator, instance)
        self._attr_unique_id = f"{instance}_todo_upcoming"
        self._attr_device_info = self._installation()

    @property
    def native_value(self) -> str | None:
        nxt = todo_upcoming(self.coordinator.data.todo)
        return str(nxt.get("title"))[:255] if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = item_fields(todo_upcoming(self.coordinator.data.todo)) or {}
        return {k: nxt.get(k) for k in ("date", "kind", "severity")}


class TodoUpcomingDateSensor(EnergietrackerEntity, SensorEntity):
    """When the next appointment is."""

    _attr_translation_key = "todo_upcoming_date"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: EnergietrackerCoordinator, instance: str) -> None:
        super().__init__(coordinator, instance)
        self._attr_unique_id = f"{instance}_todo_upcoming_date"
        self._attr_device_info = self._installation()

    @property
    def native_value(self) -> date | None:
        nxt = todo_upcoming(self.coordinator.data.todo)
        return parse_date(nxt.get("date")) if nxt else None


# ── per meter ──────────────────────────────────────────────────────────────


class MeterSensor(EnergietrackerEntity, SensorEntity):
    """Balance, consumption since 1 January, forecast of the next 12 months, days since the last reading.

    A group with a group contract gets its own device with the balance only.

    Balance with Energietracker's sign: positive = back-payment (feed-in:
    payout), negative = refund; the state is the balance up to today, the
    attributes add the balance expected at settlement and the measured balance
    up to the last reading. No state class: these are evaluations, not meter
    readings; for the energy dashboard use the meters of Home Assistant.
    """

    def __init__(
        self, coordinator: EnergietrackerCoordinator, instance: str, meter: dict[str, Any], key: str, via: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, instance)
        self._meter_key = str(meter["key"])
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{instance}_{self._meter_key}_{key}"
        device_class, unit = meter_kind(meter, key)
        self._attr_device_class = DEVICE_CLASSES.get(device_class or "")
        if key == "balance":
            unit = str(coordinator.data.summary.get("currency") or "EUR")
            self._attr_suggested_display_precision = 2
        elif key != "days_since_reading":
            self._attr_suggested_display_precision = 1
        self._attr_native_unit_of_measurement = UNITS.get(unit or "", unit)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{instance}_{self._meter_key}")},
            name=device_name(meter),
            manufacturer="Energietracker",
            model=str(meter.get("utility_label") or meter.get("utility") or "") or None,
            **via,
        )

    def _meter(self) -> dict[str, Any] | None:
        for m in all_meters(self.coordinator.data.summary):
            if m.get("key") == self._meter_key:
                return m
        return None

    @property
    def available(self) -> bool:
        return super().available and self._meter() is not None

    @property
    def native_value(self) -> float | int | None:
        meter = self._meter()
        return meter_value(meter, self._key) if meter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The balance carries the expected and the measured balance (Energietracker 3.10.0)."""
        if self._key != "balance":
            return None
        meter = self._meter()
        return balance_attributes(meter) if meter else None
