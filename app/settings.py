from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .storage import StorageManager


@dataclass
class Settings:
    audio_output: str = "auto"

    def to_dict(self) -> Dict[str, str]:
        return {"audio_output": self.audio_output}

    @classmethod
    def from_dict(cls, payload: Dict[str, str]) -> "Settings":
        return cls(audio_output=payload.get("audio_output", "auto"))


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
