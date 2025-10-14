from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from .settings import SettingsManager
from .storage import Playlist, StorageManager
from .video_player import VideoPlayer

VIDEO_DIRECTORY = Path("/opt/videoplayer/videos")
DATA_DIRECTORY = Path(__file__).resolve().parent / "data"

app = Flask(__name__)
app.config["SECRET_KEY"] = "beamerpi-secret-key"

_storage = StorageManager(DATA_DIRECTORY)
_settings_manager = SettingsManager(_storage)
_playlists: Dict[str, Playlist] = _storage.load_playlists()
_active_playlist: Optional[str] = None
_active_index: int = 0
_state_lock = threading.Lock()

_player = VideoPlayer(VIDEO_DIRECTORY, _settings_manager.get_audio_output)


# Helpers ---------------------------------------------------------------------
def _get_videos() -> Dict[str, Path]:
    videos: Dict[str, Path] = {}
    if VIDEO_DIRECTORY.exists():
        base = VIDEO_DIRECTORY.resolve()
        for entry in sorted(base.rglob("*")):
            if entry.is_file():
                relative_name = entry.relative_to(base).as_posix()
                videos[relative_name] = entry
    return videos


def _build_video_tree(videos: Dict[str, Path]) -> List[Dict[str, Any]]:
    tree: Dict[str, Any] = {}

    def _insert(parts: List[str], full_path: str, node: Dict[str, Any]) -> None:
        if len(parts) == 1:
            node.setdefault("__files__", []).append({"name": parts[0], "path": full_path})
            return
        head, *tail = parts
        child = node.setdefault(head, {})
        _insert(tail, full_path, child)

    for relative_name in sorted(videos):
        _insert(relative_name.split("/"), relative_name, tree)

    def _to_nodes(node: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
        directories: List[Dict[str, Any]] = []
        for name in sorted(key for key in node.keys() if key != "__files__"):
            child_prefix = f"{prefix}{name}/"
            directories.append(
                {
                    "name": name,
                    "path": child_prefix.rstrip("/"),
                    "is_file": False,
                    "children": _to_nodes(node[name], child_prefix),
                }
            )

        files: List[Dict[str, Any]] = [
            {
                "name": file_entry["name"],
                "path": file_entry["path"],
                "is_file": True,
                "children": [],
            }
            for file_entry in sorted(node.get("__files__", []), key=lambda item: item["name"])
        ]
        return directories + files

    return _to_nodes(tree)


def _get_playlist(name: str) -> Optional[Playlist]:
    return _playlists.get(name)


def _save_playlists() -> None:
    _storage.save_playlists(_playlists)


def _get_active_progress() -> Optional[Dict[str, Any]]:
    with _state_lock:
        active_name = _active_playlist
        next_index = _active_index

    if not active_name:
        return None

    playlist = _get_playlist(active_name)
    if playlist is None or not playlist.videos:
        return None

    total_videos = len(playlist.videos)
    next_index %= total_videos

    return {
        "playlist_name": active_name,
        "next_video_index": next_index + 1,
        "total_videos": total_videos,
        "next_video": playlist.videos[next_index],
        "remaining_videos": total_videos - next_index,
    }


def _start_playlist(name: str) -> bool:
    global _active_playlist, _active_index
    playlist = _get_playlist(name)
    if playlist is None:
        return False
    with _state_lock:
        _active_playlist = name
        _active_index = 0
    try:
        _player.set_loop_video(playlist.loop_video)
    except FileNotFoundError:
        flash("Loop-Video wurde nicht gefunden.", "error")
        _player.set_loop_video(None)
    return True


def _trigger_next() -> bool:
    global _active_index
    with _state_lock:
        if _active_playlist is None:
            return False
        playlist = _get_playlist(_active_playlist)
        if playlist is None or not playlist.videos:
            return False
        video = playlist.videos[_active_index % len(playlist.videos)]
        _active_index = (_active_index + 1) % len(playlist.videos)
    try:
        _player.enqueue_video(video)
    except FileNotFoundError:
        flash(f"Video {video} konnte nicht gefunden werden.", "error")
        return False
    return True


# Routes ----------------------------------------------------------------------
@app.route("/")
def index() -> str:
    videos = _get_videos()
    return render_template(
        "index.html",
        playlists=_playlists,
        active_playlist=_active_playlist,
        active_progress=_get_active_progress(),
        videos=videos,
        video_tree=_build_video_tree(videos),
        settings=_settings_manager.settings,
    )


@app.route("/playlist/new", methods=["GET", "POST"])
def create_playlist() -> Response:
    videos = _get_videos()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        loop_video = request.form.get("loop_video") or None
        selected_videos = request.form.getlist("videos")
        if not name:
            flash("Bitte einen Namen für die Playlist eingeben.", "error")
        else:
            playlist = Playlist(name=name, loop_video=loop_video, videos=selected_videos)
            _playlists[name] = playlist
            _save_playlists()
            flash("Playlist gespeichert.", "success")
            return redirect(url_for("index"))
    return render_template(
        "playlist_form.html",
        videos=videos,
        video_tree=_build_video_tree(videos),
        playlist=None,
    )


@app.route("/playlist/<name>/edit", methods=["GET", "POST"])
def edit_playlist(name: str) -> Response:
    playlist = _get_playlist(name)
    if playlist is None:
        flash("Playlist nicht gefunden.", "error")
        return redirect(url_for("index"))
    videos = _get_videos()
    if request.method == "POST":
        loop_video = request.form.get("loop_video") or None
        selected_videos = request.form.getlist("videos")
        playlist.loop_video = loop_video
        playlist.videos = selected_videos
        _save_playlists()
        flash("Playlist aktualisiert.", "success")
        return redirect(url_for("index"))
    return render_template(
        "playlist_form.html",
        videos=videos,
        video_tree=_build_video_tree(videos),
        playlist=playlist,
    )


@app.route("/playlist/<name>/start", methods=["POST"])
def start_playlist(name: str) -> Response:
    if _start_playlist(name):
        flash(f"Playlist {name} gestartet.", "success")
    else:
        flash("Playlist konnte nicht gestartet werden.", "error")
    return redirect(url_for("index"))


@app.route("/trigger", methods=["POST"])
def trigger() -> Response:
    if _trigger_next():
        flash("Nächstes Video gestartet.", "success")
    else:
        flash("Kein Video konnte gestartet werden.", "error")
    return redirect(url_for("index"))


@app.route("/api/trigger", methods=["POST"])
def api_trigger() -> Response:
    payload = request.get_json(silent=True) or {}
    playlist_name = payload.get("playlist") if payload else request.form.get("playlist")
    if playlist_name:
        if not _start_playlist(playlist_name):
            return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    if not _trigger_next():
        return jsonify({"status": "error", "message": "Kein Video verfügbar"}), 400
    return jsonify({"status": "ok"})


@app.route("/webhook/<name>", methods=["POST"])
def webhook(name: str) -> Response:
    if not _start_playlist(name):
        return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    if not _trigger_next():
        return jsonify({"status": "error", "message": "Kein Video verfügbar"}), 400
    return jsonify({"status": "ok"})


@app.route("/videos/<path:filename>")
def serve_video(filename: str):
    return send_from_directory(VIDEO_DIRECTORY, filename, as_attachment=False)


@app.route("/preview/<path:filename>")
def preview(filename: str) -> str:
    return render_template("preview.html", filename=filename)


@app.route("/settings", methods=["GET", "POST"])
def settings() -> Response:
    if request.method == "POST":
        audio_output = request.form.get("audio_output", "auto")
        _settings_manager.set_audio_output(audio_output)
        if _active_playlist:
            playlist = _playlists.get(_active_playlist)
            if playlist:
                try:
                    _player.set_loop_video(playlist.loop_video)
                except FileNotFoundError:
                    flash("Loop-Video wurde nicht gefunden.", "error")
                    _player.set_loop_video(None)
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", settings=_settings_manager.settings)


@app.context_processor
def inject_globals():
    return {
        "video_directory": VIDEO_DIRECTORY,
    }


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
