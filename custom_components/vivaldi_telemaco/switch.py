"""DND and matrix switches for Vivaldi Telemaco."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    if coordinator.api is None:
        return
    async_add_entities(
        [
            *(
                TelemacoDndSwitch(coordinator, zone)
                for zone in range(1, coordinator.zone_count + 1)
            ),
            *(
                TelemacoMatrixSwitch(coordinator, source, zone)
                for source in [
                    *(f"in{index}" for index in range(1, 7)),
                    *(
                        f"player{index}"
                        for index in range(1, coordinator.player_count + 1)
                    ),
                ]
                for zone in range(1, coordinator.zone_count + 1)
            ),
        ]
    )


class TelemacoDndSwitch(TelemacoEntity, SwitchEntity):
    """Doorbell do-not-disturb for an output."""

    _attr_icon = "mdi:bell-off"

    def __init__(self, coordinator: TelemacoCoordinator, zone: int) -> None:
        super().__init__(coordinator)
        self.zone = zone
        self._attr_unique_id = f"{coordinator.entry.unique_id}_zone_{zone}_dnd"

    @property
    def name(self) -> str:
        return f"{self.coordinator.data.zones[self.zone].name} escludi campanello"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.zones[self.zone].dnd

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("zone_dnd", zone=self.zone, dnd=True)
        self.coordinator.data.zones[self.zone].dnd = True
        self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("zone_dnd", zone=self.zone, dnd=False)
        self.coordinator.data.zones[self.zone].dnd = False
        self.coordinator.async_set_updated_data(self.coordinator.data)


class TelemacoMatrixSwitch(TelemacoEntity, SwitchEntity):
    """Route one physical input or player to one output."""

    _attr_icon = "mdi:transit-connection-variant"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: TelemacoCoordinator,
        source: str,
        zone: int,
    ) -> None:
        super().__init__(coordinator)
        self.source = source
        self.zone = zone
        self._attr_unique_id = (
            f"{coordinator.entry.unique_id}_matrix_{source}_out_{zone}"
        )

    @property
    def _source_name(self) -> str:
        if self.source.startswith("player"):
            index = int(self.source.removeprefix("player"))
            return self.coordinator.data.players[index].name
        index = int(self.source.removeprefix("in"))
        return self.coordinator.data.input_names.get(
            f"aux{index}",
            f"Ingresso {index}",
        )

    @property
    def name(self) -> str:
        zone_name = self.coordinator.data.zones[self.zone].name
        return f"Matrice {self._source_name} → {zone_name}"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.matrix.get(self.source, {}).get(
            self.zone,
            False,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            "matrix_route",
            source=self.source,
            zone=self.zone,
            active=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            "matrix_route",
            source=self.source,
            zone=self.zone,
            active=False,
        )
