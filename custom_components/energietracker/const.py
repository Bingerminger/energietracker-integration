"""Constants of the Energietracker integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "energietracker"

CONF_URL: Final = "url"
CONF_TOKEN: Final = "token"
CONF_VERIFY_SSL: Final = "verify_ssl"

#: Values change with a new reading at the most; Energietracker allows the
#: summary to be cached for five minutes.
UPDATE_INTERVAL: Final = timedelta(minutes=15)
REQUEST_TIMEOUT: Final = 30
