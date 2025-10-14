from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Optional


class VideoPlayer:
    """Controls background playback using mpv."""

    def __init__(self, video_dir: Path, audio_device_provider) -> None:
        self.video_dir = video_dir
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self._audio_device_provider = audio_device_provider
        self._queue: "Queue[Path]" = Queue()
        self._loop_video: Optional[Path] = None
        self._mpv_process: Optional[subprocess.Popen] = None
        self._socket: Optional[socket.socket] = None
        self._recv_buffer = b""
        self._ipc_socket_path = Path("/tmp/beamerpi-mpv.sock")
        self._playing_trigger = False
        self._current_video: Optional[Path] = None
        self._current_is_loop = False
        self._loop_dirty = False
        self._stop_event = threading.Event()
        self._wakeup_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # Public API ---------------------------------------------------------------
    def set_loop_video(self, filename: Optional[str]) -> None:
        self._loop_video = self._resolve_video(filename) if filename else None
        self._loop_dirty = True
        self._wakeup_event.set()

    def enqueue_video(self, filename: str) -> None:
        video_path = self._resolve_video(filename)
        self._queue.put(video_path)
        self._wakeup_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wakeup_event.set()
        self._worker.join(timeout=2)
        self._stop_mpv()

    # Internal helpers ---------------------------------------------------------
    def _resolve_video(self, filename: str) -> Path:
        path = (self.video_dir / filename).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Video {filename} not found in {self.video_dir}")
        if self.video_dir.resolve() not in path.parents and self.video_dir.resolve() != path.parent:
            raise ValueError("Video path must remain inside the video directory")
        return path

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._ensure_mpv_running()
            self._poll_events()

            if self._loop_dirty and not self._playing_trigger:
                if self._ensure_loop_state():
                    self._loop_dirty = False

            if self._playing_trigger:
                self._wait_for_events(timeout=0.1)
                continue

            try:
                video = self._queue.get_nowait()
            except Empty:
                self._wait_for_events(timeout=0.1)
                continue

            self._start_trigger(video)

    def _wait_for_events(self, timeout: float) -> None:
        self._wakeup_event.wait(timeout)
        self._wakeup_event.clear()

    def _start_trigger(self, path: Path) -> None:
        if not self._ensure_mpv_running():
            return
        self._playing_trigger = True
        self._current_video = path
        self._current_is_loop = False
        self._load_file(path, loop=False)

    def _ensure_loop_state(self) -> bool:
        if not self._ensure_mpv_running():
            return False
        if self._loop_video is None:
            if self._current_video is not None:
                self._send_command(["stop"])
            self._current_video = None
            self._current_is_loop = False
            return True
        if self._playing_trigger:
            return False
        if self._current_is_loop and self._current_video == self._loop_video:
            return True
        self._current_video = self._loop_video
        self._current_is_loop = True
        self._load_file(self._loop_video, loop=True)
        return True

    def _ensure_mpv_running(self) -> bool:
        if self._mpv_process is not None and self._mpv_process.poll() is None and self._socket:
            return True
        self._start_mpv()
        return self._mpv_process is not None and self._mpv_process.poll() is None and self._socket is not None

    def _start_mpv(self) -> None:
        self._stop_mpv()
        if self._ipc_socket_path.exists():
            try:
                self._ipc_socket_path.unlink()
            except OSError:
                pass

        command = [
            "mpv",
            "--idle=yes",
            "--force-window=immediate",
            "--background=0/0/0",
            "--fs",
            "--no-osc",
            "--no-osd-bar",
            "--keep-open=no",
            f"--input-ipc-server={self._ipc_socket_path}",
            "--quiet",
            "--no-terminal",
        ]
        audio_device = self._audio_device_provider()
        if audio_device and audio_device != "auto":
            command.append(f"--audio-device={audio_device}")

        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")

        try:
            self._mpv_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except FileNotFoundError:
            print("mpv player not found. Please install mpv.")
            time.sleep(5)
            self._mpv_process = None
            return
        except Exception as exc:
            print(f"Could not start mpv: {exc}")
            time.sleep(2)
            self._mpv_process = None
            return

        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self._mpv_process.poll() is not None:
                break
            if self._ipc_socket_path.exists():
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect(str(self._ipc_socket_path))
                    sock.setblocking(False)
                    self._socket = sock
                    self._recv_buffer = b""
                    self._loop_dirty = True
                    self._wakeup_event.set()
                    return
                except OSError:
                    pass
            time.sleep(0.05)

        print("mpv could not be started or IPC connection failed.")
        self._stop_mpv()

    def _stop_mpv(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        if self._mpv_process is not None and self._mpv_process.poll() is None:
            self._mpv_process.terminate()
            try:
                self._mpv_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._mpv_process.kill()
        self._mpv_process = None
        self._current_video = None
        self._current_is_loop = False
        self._playing_trigger = False

    def _load_file(self, path: Path, *, loop: bool) -> None:
        self._send_command(["loadfile", str(path), "replace"])
        self._send_command(["set", "loop-file", "inf" if loop else "no"])

    def _send_command(self, command: list) -> None:
        if not self._socket:
            return
        try:
            message = json.dumps({"command": command}).encode("utf-8") + b"\n"
            self._socket.sendall(message)
        except OSError:
            self._handle_mpv_disconnect()

    def _poll_events(self) -> None:
        if not self._socket:
            return
        while True:
            try:
                chunk = self._socket.recv(4096)
            except BlockingIOError:
                break
            except OSError:
                self._handle_mpv_disconnect()
                break
            if not chunk:
                self._handle_mpv_disconnect()
                break
            self._recv_buffer += chunk
            while b"\n" in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                self._handle_event(event)

    def _handle_event(self, event: dict) -> None:
        name = event.get("event")
        if name == "end-file":
            reason = event.get("reason")
            if isinstance(reason, str):
                reason = {
                    "eof": 0,
                    "stop": 1,
                    "quit": 2,
                    "restart": 3,
                    "replace": 4,
                    "error": 5,
                }.get(reason, reason)

            if reason in (None, 0):
                self._playing_trigger = False
                self._current_video = None
                self._current_is_loop = False
                self._loop_dirty = True
                self._wakeup_event.set()
        elif name == "property-change":
            pass

    def _handle_mpv_disconnect(self) -> None:
        self._stop_mpv()
        self._loop_dirty = True
        self._wakeup_event.set()
