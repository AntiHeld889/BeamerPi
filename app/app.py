from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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
from werkzeug.utils import secure_filename

from .settings import SettingsManager
from .storage import Playlist, StorageManager
from .video_player import VideoPlayer

DATA_DIRECTORY = Path(__file__).resolve().parent / "data"

app = Flask(__name__)
app.config["SECRET_KEY"] = "beamerpi-secret-key"

_storage = StorageManager(DATA_DIRECTORY)
_settings_manager = SettingsManager(_storage)
_playlists: Dict[str, Playlist] = _storage.load_playlists()
_active_playlist: Optional[str] = None
_active_index: int = 0
_state_lock = threading.Lock()
_auto_start_playlist_name = _settings_manager.get_auto_start_playlist()

ALLOWED_VIDEO_EXTENSIONS: Set[str] = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".mpg",
    ".mpeg",
    ".webm",
    ".m4v",
    ".wmv",
}

_video_cache_lock = threading.Lock()
_video_cache: Dict[str, Any] = {"directory": None, "videos": None}

_player = VideoPlayer(
    _settings_manager.get_video_directory(),
    _settings_manager.get_audio_output,
    _settings_manager.get_trigger_start_webhook,
    _settings_manager.get_trigger_end_webhook,
)


# Helpers ---------------------------------------------------------------------
def _get_video_directory() -> Path:
    return _settings_manager.get_video_directory()


def _get_videos() -> Dict[str, Path]:
    base = _get_video_directory()
    resolved_base = base.resolve(strict=False)

    with _video_cache_lock:
        cached_directory = _video_cache.get("directory")
        cached_videos = _video_cache.get("videos")
        if cached_directory == resolved_base and cached_videos is not None:
            return dict(cached_videos)

    videos: Dict[str, Path] = {}
    if resolved_base.exists():
        for entry in sorted(resolved_base.rglob("*")):
            if entry.is_file() and entry.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                relative_name = entry.relative_to(resolved_base).as_posix()
                videos[relative_name] = entry

    with _video_cache_lock:
        _video_cache["directory"] = resolved_base
        _video_cache["videos"] = dict(videos)

    return videos


def _invalidate_video_cache() -> None:
    with _video_cache_lock:
        _video_cache["directory"] = None
        _video_cache["videos"] = None


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


def _delete_playlist(name: str) -> bool:
    global _active_playlist, _active_index
    playlist = _playlists.pop(name, None)
    if playlist is None:
        return False

    should_reset_loop = False
    with _state_lock:
        if _active_playlist == name:
            _active_playlist = None
            _active_index = 0
            should_reset_loop = True

    if should_reset_loop:
        _player.set_loop_video(None)

    if _settings_manager.get_auto_start_playlist() == name:
        _settings_manager.set_auto_start_playlist(None)

    _save_playlists()
    return True


def _duplicate_playlist(name: str, new_name: Optional[str] = None) -> Playlist:
    original = _get_playlist(name)
    if original is None:
        raise KeyError(name)

    if new_name:
        candidate = new_name.strip()
        if not candidate:
            raise ValueError("Der neue Playlist-Name darf nicht leer sein.")
        if candidate in _playlists:
            raise ValueError("Eine Playlist mit diesem Namen existiert bereits.")
    else:
        base_name = f"{original.name} Kopie"
        candidate = base_name
        suffix = 2
        while candidate in _playlists:
            candidate = f"{base_name} {suffix}"
            suffix += 1

    playlist = Playlist(
        name=candidate,
        loop_video=original.loop_video,
        videos=list(original.videos),
    )
    _playlists[playlist.name] = playlist
    _save_playlists()
    return playlist


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


def _serialize_playlists() -> List[Dict[str, Any]]:
    progress = _get_active_progress()
    serialized: List[Dict[str, Any]] = []
    for name, playlist in sorted(_playlists.items()):
        playlist_data = {
            "name": playlist.name,
            "loop_video": playlist.loop_video,
            "videos": playlist.videos,
            "is_active": False,
            "progress": None,
        }
        if progress and progress["playlist_name"] == name:
            playlist_data["is_active"] = True
            playlist_data["progress"] = progress
        serialized.append(playlist_data)
    return serialized


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
    except ValueError as e:
        flash(f"Ungültiger Pfad für Loop-Video: {e}", "error")
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
    except ValueError as e:
        flash(f"Ungültiger Videopfad: {e}", "error")
        return False
    return True


if _auto_start_playlist_name:
    if not _start_playlist(_auto_start_playlist_name):
        _settings_manager.set_auto_start_playlist(None)


# Routes ----------------------------------------------------------------------
@app.route("/")
def index() -> str:
    return render_template(
        "index.html",
        playlists=_playlists,
        active_playlist=_active_playlist,
        active_progress=_get_active_progress(),
        player_status=_player.get_status(),
        settings=_settings_manager.settings,
    )


@app.route("/playlist/new", methods=["GET", "POST"])
def create_playlist() -> Response:
    videos = _get_videos()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        loop_video = request.form.get("loop_video") or None
        selected_videos = request.form.getlist("ordered_videos")
        if not selected_videos:
            selected_videos = request.form.getlist("videos")
        if not name:
            flash("Bitte einen Namen für die Playlist eingeben.", "error")
        elif name in _playlists:
            flash("Eine Playlist mit diesem Namen existiert bereits.", "error")
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
        selected_videos = request.form.getlist("ordered_videos")
        if not selected_videos:
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


@app.route("/playlist/<name>/delete", methods=["POST"])
def delete_playlist(name: str) -> Response:
    if _delete_playlist(name):
        flash(f"Playlist {name} wurde gelöscht.", "success")
    else:
        flash("Playlist wurde nicht gefunden.", "error")
    return redirect(url_for("index"))


@app.route("/playlist/<name>/duplicate", methods=["POST"])
def duplicate_playlist(name: str) -> Response:
    new_name = request.form.get("new_name")
    try:
        playlist = _duplicate_playlist(name, new_name)
    except KeyError:
        flash("Playlist wurde nicht gefunden.", "error")
        return redirect(url_for("index"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    flash(f"Playlist {playlist.name} wurde dupliziert.", "success")
    return redirect(url_for("edit_playlist", name=playlist.name))


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


@app.route("/api/trigger", methods=["POST", "GET"])
def api_trigger() -> Response:
    playlist_name: Optional[str]
    if request.method == "GET":
        playlist_name = request.args.get("playlist")
    else:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            playlist_name = payload.get("playlist")
        else:
            playlist_name = request.form.get("playlist")
    if playlist_name:
        if not _start_playlist(playlist_name):
            return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    if not _trigger_next():
        return jsonify({"status": "error", "message": "Kein Video verfügbar"}), 400
    return jsonify({"status": "ok"})


@app.route("/api/status", methods=["GET"])
def api_status() -> Response:
    with _state_lock:
        active_name = _active_playlist
    return jsonify(
        {
            "status": _player.get_status(),
            "active_playlist": active_name,
            "active_progress": _get_active_progress(),
        }
    )


@app.route("/api/playlists", methods=["GET"])
def api_playlists() -> Response:
    return jsonify({"playlists": _serialize_playlists()})


@app.route("/api/playlists/<name>", methods=["DELETE"])
def api_delete_playlist(name: str) -> Response:
    if not _delete_playlist(name):
        return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    return jsonify({"status": "ok"})


@app.route("/api/playlists/<name>/duplicate", methods=["POST"])
def api_duplicate_playlist(name: str) -> Response:
    payload = request.get_json(silent=True)
    new_name: Optional[str] = None
    if isinstance(payload, dict):
        new_name = payload.get("name") or payload.get("new_name")
    if new_name is None:
        new_name = request.form.get("name") or request.form.get("new_name")
    try:
        playlist = _duplicate_playlist(name, new_name)
    except KeyError:
        return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "playlist": playlist.to_dict()})


@app.route("/api/videos", methods=["GET"])
def api_videos() -> Response:
    videos = _get_videos()
    return jsonify(
        {
            "videos": sorted(videos.keys()),
            "tree": _build_video_tree(videos),
        }
    )


@app.route("/webhook/<name>", methods=["POST"])
def webhook(name: str) -> Response:
    if not _start_playlist(name):
        return jsonify({"status": "error", "message": "Playlist nicht gefunden"}), 404
    if not _trigger_next():
        return jsonify({"status": "error", "message": "Kein Video verfügbar"}), 400
    return jsonify({"status": "ok"})


@app.route("/videos/<path:filename>")
def serve_video(filename: str):
    video_directory = _get_video_directory()
    return send_from_directory(video_directory, filename, as_attachment=False)


@app.route("/preview/<path:filename>")
def preview(filename: str) -> str:
    return render_template("preview.html", filename=filename)


@app.route("/settings", methods=["GET", "POST"])
def settings() -> Response:
    video_directory = _get_video_directory()
    if request.method == "POST":
        action = request.form.get("action", "update_settings")
        if action == "update_settings":
            audio_output = request.form.get("audio_output", "auto")
            trigger_start_webhook = request.form.get("trigger_start_webhook", "")
            trigger_end_webhook = request.form.get("trigger_end_webhook", "")
            video_directory_input = request.form.get("video_directory", "")
            auto_start_playlist = request.form.get("auto_start_playlist", "").strip()

            _settings_manager.set_audio_output(audio_output)
            _settings_manager.set_trigger_start_webhook(trigger_start_webhook)
            _settings_manager.set_trigger_end_webhook(trigger_end_webhook)

            save_success = True
            if auto_start_playlist and auto_start_playlist not in _playlists:
                flash("Die ausgewählte Playlist wurde nicht gefunden.", "error")
                save_success = False
            else:
                _settings_manager.set_auto_start_playlist(auto_start_playlist or None)
                if auto_start_playlist and not _start_playlist(auto_start_playlist):
                    flash("Automatische Playlist konnte nicht gestartet werden.", "error")
                    save_success = False
            try:
                updated_directory = _settings_manager.set_video_directory(video_directory_input)
            except ValueError as exc:
                flash(str(exc), "error")
                save_success = False
                updated_directory = None
            else:
                _player.set_video_directory(updated_directory)
                video_directory = updated_directory
                _invalidate_video_cache()

            if _active_playlist:
                playlist = _playlists.get(_active_playlist)
                if playlist:
                    try:
                        _player.set_loop_video(playlist.loop_video)
                    except FileNotFoundError:
                        flash("Loop-Video wurde nicht gefunden.", "error")
                        _player.set_loop_video(None)
                    except ValueError as e:
                        flash(f"Ungültiger Pfad für Loop-Video: {e}", "error")
                        _player.set_loop_video(None)

            if save_success:
                flash("Einstellungen gespeichert.", "success")
            return redirect(url_for("settings"))

        if action == "create_folder":
            folder_path = request.form.get("folder_path", "").strip()
            if not folder_path:
                flash("Bitte einen Ordnernamen angeben.", "error")
            else:
                target_directory = (video_directory / folder_path).resolve(strict=False)
                base_directory = video_directory.resolve(strict=False)
                if base_directory == target_directory or base_directory in target_directory.parents:
                    try:
                        target_directory.mkdir(parents=True, exist_ok=True)
                    except OSError as exc:
                        flash(f"Ordner konnte nicht erstellt werden: {exc}", "error")
                    else:
                        flash("Ordner wurde erstellt.", "success")
                        _invalidate_video_cache()
                else:
                    flash("Der Ordnerpfad muss innerhalb des Videoverzeichnisses liegen.", "error")
            return redirect(url_for("settings"))

        if action == "upload_videos":
            upload_subdirectory = request.form.get("upload_subdirectory", "").strip()
            files = request.files.getlist("video_files")

            target_directory = video_directory
            if upload_subdirectory:
                target_directory = (video_directory / upload_subdirectory).resolve(strict=False)
            else:
                target_directory = target_directory.resolve(strict=False)

            base_directory = video_directory.resolve(strict=False)
            if base_directory == target_directory or base_directory in target_directory.parents:
                try:
                    target_directory.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    flash(f"Zielordner konnte nicht erstellt werden: {exc}", "error")
                else:
                    saved_files = 0
                    for file in files:
                        if not file or not file.filename:
                            continue
                        filename = secure_filename(file.filename)
                        if not filename:
                            continue
                        file_ext = Path(filename).suffix.lower()
                        if file_ext not in ALLOWED_VIDEO_EXTENSIONS:
                            continue
                        file.save(target_directory / filename)
                        saved_files += 1
                    if saved_files:
                        flash(f"{saved_files} Datei(en) hochgeladen.", "success")
                        _invalidate_video_cache()
                    else:
                        flash("Keine gültigen Videodateien ausgewählt.", "error")
            else:
                flash("Der Zielordner muss innerhalb des Videoverzeichnisses liegen.", "error")
            return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        settings=_settings_manager.settings,
        video_directory=video_directory,
        available_playlists=sorted(_playlists.keys()),
    )


@app.context_processor
def inject_globals():
    return {
        "video_directory": _get_video_directory(),
    }


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
