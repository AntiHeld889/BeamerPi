from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .storage import StorageManager


AVAILABLE_INPUT_GPIO_PINS = (
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
)


@dataclass
class Settings:
    audio_output: str = "auto"
    input_gpio: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "audio_output": self.audio_output,
            "input_gpio": self.input_gpio,
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
        return cls(
            audio_output=payload.get("audio_output", "auto"),
            input_gpio=input_gpio,
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
        if not gpio:
            self._settings.input_gpio = None
        else:
            try:
                pin = int(gpio)
            except (TypeError, ValueError):
                pin = None
            if pin in AVAILABLE_INPUT_GPIO_PINS:
                self._settings.input_gpio = pin
            else:
                self._settings.input_gpio = None
        self.save()

    def get_input_gpio(self) -> Optional[int]:
        return self._settings.input_gpio
