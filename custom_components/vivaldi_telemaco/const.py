"""Constants for Vivaldi Telemaco."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "vivaldi_telemaco"
PLATFORMS: Final = ["binary_sensor", "button", "media_player", "number", "sensor", "switch"]

CONF_TRANSPORT: Final = "transport"
CONF_API_TOKEN: Final = "api_token"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_MQTT_PREFIX: Final = "mqtt_prefix"
CONF_ZONE_COUNT: Final = "zone_count"
CONF_PLAYER_COUNT: Final = "player_count"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_API_PROFILE: Final = "api_profile"

TRANSPORT_API: Final = "api"
TRANSPORT_MQTT: Final = "mqtt"
TRANSPORT_HYBRID: Final = "hybrid"

DEFAULT_NAME: Final = "Vivaldi Telemaco"
DEFAULT_PORT: Final = 80
DEFAULT_MQTT_PREFIX: Final = "vivaldi/telemaco_000000"
DEFAULT_ZONE_COUNT: Final = 6
DEFAULT_PLAYER_COUNT: Final = 4
DEFAULT_SCAN_INTERVAL: Final = 10
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300
UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

API_PROFILE_AUTO: Final = "auto"
API_PROFILE_V1: Final = "vivaldi_v1"

SOURCE_NAMES: Final = {
    0: "Nessuna",
    1: "Webradio",
    3: "Spotify",
    4: "AirPlay",
    5: "Locale",
    6: "YouTube",
    7: "Spreaker",
    8: "SD-CARD",
    9: "NAS",
    10: "Relax",
    11: "Worldwide FM",
    12: "AUX 1",
    13: "AUX 2",
    14: "AUX 3",
    15: "AUX 4",
    16: "AUX 5",
    17: "AUX 6",
}

SERVICE_SEND_COMMAND: Final = "send_command"
SERVICE_PLAY_PRESET: Final = "play_preset"
SERVICE_DOORBELL: Final = "doorbell"

ATTR_COMMAND: Final = "command"
ATTR_PAYLOAD: Final = "payload"
ATTR_PLAYER: Final = "player"
ATTR_PRESET: Final = "preset"
ATTR_ZONES: Final = "zones"
ATTR_SOUND: Final = "sound"
