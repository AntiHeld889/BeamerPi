from __future__ import annotations

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
        self._loop_process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # Public API ---------------------------------------------------------------
    def set_loop_video(self, filename: Optional[str]) -> None:
        self._loop_video = self._resolve_video(filename) if filename else None
        self._restart_loop_if_needed()

    def enqueue_video(self, filename: str) -> None:
        video_path = self._resolve_video(filename)
        self._queue.put(video_path)
        self._stop_loop()

    def stop(self) -> None:
        self._stop_event.set()
        self._stop_loop()
        self._worker.join(timeout=2)

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
            try:
                video = self._queue.get(timeout=0.5)
            except Empty:
                self._ensure_loop_running()
                continue

            self._stop_loop()
            self._play_video(video)
            self._queue.task_done()

    def _ensure_loop_running(self) -> None:
        if self._loop_video is None:
            return
        if self._loop_process is not None and self._loop_process.poll() is None:
            return
        self._loop_process = self._launch_process(self._loop_video, loop=True)

    def _restart_loop_if_needed(self) -> None:
        self._stop_loop()
        self._ensure_loop_running()

    def _stop_loop(self) -> None:
        if self._loop_process is not None and self._loop_process.poll() is None:
            self._loop_process.terminate()
            try:
                self._loop_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._loop_process.kill()
        self._loop_process = None

    def _play_video(self, path: Path) -> None:
        process = self._launch_process(path, loop=False)
        if process is None:
            return
        try:
            process.wait()
        except subprocess.TimeoutExpired:
            process.kill()

    def _launch_process(self, path: Path, *, loop: bool) -> Optional[subprocess.Popen]:
        command = [
            "mpv",
            "--quiet",
            "--fs",
            "--no-osd",
        ]
        if loop:
            command.append("--loop-file=inf")
        audio_device = self._audio_device_provider()
        if audio_device and audio_device != "auto":
            command.append(f"--audio-device={audio_device}")
        command.append(str(path))
        try:
            return subprocess.Popen(command)
        except FileNotFoundError:
            print("mpv player not found. Please install mpv.")
            time.sleep(5)
        except Exception as exc:
            print(f"Could not start mpv for {path}: {exc}")
            time.sleep(2)
        return None
