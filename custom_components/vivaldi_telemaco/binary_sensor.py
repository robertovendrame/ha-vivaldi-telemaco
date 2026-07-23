"""Binary sensors for Vivaldi Telemaco."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
        ]
    )


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
