from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Playlist:
    """Represents a playlist definition."""

    name: str
    loop_video: Optional[str]
    videos: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "loop_video": self.loop_video,
            "videos": self.videos,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Playlist":
        return cls(
            name=str(payload.get("name", "")),
            loop_video=payload.get("loop_video") or None,
            videos=list(payload.get("videos", []) or []),
        )


class StorageManager:
    """Thread-safe JSON storage for playlists and settings."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.playlists_path = self.base_path / "playlists.json"
        self.settings_path = self.base_path / "settings.json"
        self._lock = threading.Lock()

    # Playlists -----------------------------------------------------------------
    def load_playlists(self) -> Dict[str, Playlist]:
        data = self._read_json(self.playlists_path, default={})
        playlists: Dict[str, Playlist] = {}
        for name, payload in data.items():
            playlists[name] = Playlist.from_dict(payload)
        return playlists

    def save_playlists(self, playlists: Dict[str, Playlist]) -> None:
        payload = {name: playlist.to_dict() for name, playlist in playlists.items()}
        self._write_json(self.playlists_path, payload)

    # Settings ------------------------------------------------------------------
    def load_settings(self) -> Dict[str, object]:
        return self._read_json(self.settings_path, default={})

    def save_settings(self, settings: Dict[str, object]) -> None:
        self._write_json(self.settings_path, settings)

    # Internal helpers ----------------------------------------------------------
    def _read_json(self, path: Path, default):
        with self._lock:
            if not path.exists():
                return default
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return default

    def _write_json(self, path: Path, payload) -> None:
        with self._lock:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
