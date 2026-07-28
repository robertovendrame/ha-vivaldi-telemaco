"""Binary sensors for Vivaldi Telemaco."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .c4io import C4IOClient, C4IOEntity
from .coordinator import TelemacoCoordinator
from .entity import TelemacoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: TelemacoCoordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                TelemacoProblemSensor(coordinator, index)
                for index in range(1, coordinator.zone_count + 1)
            ),
            *(
                TelemacoSignalSensor(coordinator, index)
                for index in range(1, coordinator.zone_count + 1)
            ),
            *(C4IOConnectivitySensor(client) for client in coordinator.c4io_manager.clients),
        ]
    )


class C4IOConnectivitySensor(C4IOEntity, BinarySensorEntity):
    """Local WebSocket connectivity for one C4IO."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Connessione"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: C4IOClient) -> None:
        super().__init__(client)
        self._attr_unique_id = f"c4io_{client.spec.host.replace('.', '_')}_connectivity"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.client.state.connected


class TelemacoProblemSensor(TelemacoEntity, BinarySensorEntity):
    """Amplifier error for one zone."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "amplifier_error"

    def __init__(self, coordinator: TelemacoCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.unique_id}_zone_{index}_error"

    @property
    def name(self) -> str:
        return f"{self.coordinator.data.zones[self.index].name} errore amplificatore"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.zones[self.index].amplifier_error


class TelemacoSignalSensor(TelemacoEntity, BinarySensorEntity):
    """Analog signal detector."""

    _attr_icon = "mdi:sine-wave"

    def __init__(self, coordinator: TelemacoCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.unique_id}_signal_{index}"

    @property
    def name(self) -> str:
        return f"Segnale ingresso {self.index}"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.signals.get(self.index, False)
