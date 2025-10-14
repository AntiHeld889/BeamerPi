from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .storage import StorageManager


@dataclass(frozen=True)
class GPIOPinOption:
    bcm: int
    header_pin: int

    @property
    def label(self) -> str:
        return f"GPIO {self.bcm} (Pin {self.header_pin})"


AVAILABLE_INPUT_GPIO_OPTIONS: Tuple[GPIOPinOption, ...] = (
    GPIOPinOption(2, 3),
    GPIOPinOption(3, 5),
    GPIOPinOption(4, 7),
    GPIOPinOption(5, 29),
    GPIOPinOption(6, 31),
    GPIOPinOption(7, 26),
    GPIOPinOption(8, 24),
    GPIOPinOption(9, 21),
    GPIOPinOption(10, 19),
    GPIOPinOption(11, 23),
    GPIOPinOption(12, 32),
    GPIOPinOption(13, 33),
    GPIOPinOption(16, 36),
    GPIOPinOption(17, 11),
    GPIOPinOption(18, 12),
    GPIOPinOption(19, 35),
    GPIOPinOption(20, 38),
    GPIOPinOption(21, 40),
    GPIOPinOption(22, 15),
    GPIOPinOption(23, 16),
    GPIOPinOption(24, 18),
    GPIOPinOption(25, 22),
    GPIOPinOption(26, 37),
    GPIOPinOption(27, 13),
)

AVAILABLE_INPUT_GPIO_PINS = tuple(option.bcm for option in AVAILABLE_INPUT_GPIO_OPTIONS)


@dataclass
class Settings:
    audio_output: str = "auto"
    input_gpio: Optional[int] = None
    input_gpio_active_high: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "audio_output": self.audio_output,
            "input_gpio": self.input_gpio,
            "input_gpio_active_high": self.input_gpio_active_high,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Settings":
        raw_gpio = payload.get("input_gpio")
        input_gpio: Optional[int]
        if raw_gpio in (None, ""):
            input_gpio = None
        else:
            try:
                input_gpio = int(raw_gpio)
            except (TypeError, ValueError):
                input_gpio = None
        active_high = payload.get("input_gpio_active_high")
        if isinstance(active_high, str):
            active_high_value = active_high.lower() != "low"
        elif active_high is None:
            active_high_value = True
        else:
            active_high_value = bool(active_high)
        return cls(
            audio_output=payload.get("audio_output", "auto"),
            input_gpio=input_gpio,
            input_gpio_active_high=active_high_value,
        )


class SettingsManager:
    def __init__(self, storage: StorageManager) -> None:
        self._storage = storage
        self._settings = Settings.from_dict(storage.load_settings())

    @property
    def settings(self) -> Settings:
        return self._settings

    def save(self) -> None:
        self._storage.save_settings(self._settings.to_dict())

    def set_audio_output(self, output: str) -> None:
        self._settings.audio_output = output or "auto"
        self.save()

    def get_audio_output(self) -> str:
        return self._settings.audio_output

    def set_input_gpio(self, gpio: Optional[str]) -> None:
        previous = self._settings.input_gpio
        new_value: Optional[int]
        if not gpio:
            new_value = None
        else:
            try:
                pin = int(gpio)
            except (TypeError, ValueError):
                pin = None
            if pin in AVAILABLE_INPUT_GPIO_PINS:
                new_value = pin
            else:
                new_value = None
        if previous != new_value:
            self._settings.input_gpio = new_value
            self.save()

    def get_input_gpio(self) -> Optional[int]:
        return self._settings.input_gpio

    def set_input_gpio_active_high(self, mode: Optional[str]) -> None:
        previous = self._settings.input_gpio_active_high
        if isinstance(mode, str):
            new_value = mode.lower() != "low"
        elif mode is None:
            new_value = True
        else:
            new_value = bool(mode)
        if previous != new_value:
            self._settings.input_gpio_active_high = new_value
            self.save()

    def get_input_gpio_active_high(self) -> bool:
        return self._settings.input_gpio_active_high
