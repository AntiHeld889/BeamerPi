from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .storage import StorageManager


DEFAULT_VIDEO_DIRECTORY = Path("/opt/videoplayer/videos")


@dataclass
class Settings:
    audio_output: str = "auto"
    trigger_start_webhook_url: str = ""
    trigger_end_webhook_url: str = ""
    video_directory: str = str(DEFAULT_VIDEO_DIRECTORY)

    def to_dict(self) -> Dict[str, str]:
        return {
            "audio_output": self.audio_output,
            "trigger_start_webhook_url": self.trigger_start_webhook_url,
            "trigger_end_webhook_url": self.trigger_end_webhook_url,
            "video_directory": self.video_directory,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, str]) -> "Settings":
        return cls(
            audio_output=payload.get("audio_output", "auto"),
            trigger_start_webhook_url=payload.get("trigger_start_webhook_url", ""),
            trigger_end_webhook_url=payload.get("trigger_end_webhook_url", ""),
            video_directory=payload.get("video_directory", str(DEFAULT_VIDEO_DIRECTORY)),
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

    def set_trigger_start_webhook(self, url: str) -> None:
        self._settings.trigger_start_webhook_url = url.strip()
        self.save()

    def get_trigger_start_webhook(self) -> str:
        return self._settings.trigger_start_webhook_url

    def set_trigger_end_webhook(self, url: str) -> None:
        self._settings.trigger_end_webhook_url = url.strip()
        self.save()

    def get_trigger_end_webhook(self) -> str:
        return self._settings.trigger_end_webhook_url

    def set_video_directory(self, directory: str) -> Path:
        directory = directory.strip()
        if not directory:
            directory = str(DEFAULT_VIDEO_DIRECTORY)

        path = Path(directory).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"Ordner konnte nicht erstellt werden: {exc}") from exc

        resolved = path.resolve()
        self._settings.video_directory = str(resolved)
        self.save()
        return resolved

    def get_video_directory(self) -> Path:
        directory = Path(self._settings.video_directory).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        return directory
