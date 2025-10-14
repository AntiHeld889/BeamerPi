#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Raspberry Pi 5 – HDMI1 Vollbild Video Player mit GPIO-Trigger
# - Loop-Video läuft dauerhaft (schwarzer Hintergrund zwischen Clips)
# - Button an GPIO27→GND startet nacheinander alle Trigger-Videos
# - Während eines Trigger-Videos: GPIO22 aktiviert (LOW aktiv)
# - Nach Ende: zurück zum Loop, GPIO22 wieder inaktiv
# - Nach letztem Video: Reihenfolge beginnt erneut bei Video1

import os, time, json, socket, subprocess, threading, queue
from pathlib import Path
from gpiozero import Button, OutputDevice
from http.server import BaseHTTPRequestHandler, HTTPServer


CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_CONFIG = {
    "trigger_gpio_input": 27,
    "button_pull_up": False,
    "trigger_gpio_output": 26,
    "trigger_active_high": False,
    "audio_output": None,
    "audio_volume": 100,
}


def load_config():
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                config.update({k: loaded.get(k, config[k]) for k in config})
        except (OSError, json.JSONDecodeError):
            pass
    return config


def ensure_config_exists():
    if not CONFIG_PATH.exists():
        try:
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        except OSError:
            pass


ensure_config_exists()
CONFIG = load_config()

# ===================== KONFIG =====================
GPIO_BUTTON = int(CONFIG.get("trigger_gpio_input", DEFAULT_CONFIG["trigger_gpio_input"]))
BUTTON_PULL_UP = bool(CONFIG.get("button_pull_up", DEFAULT_CONFIG["button_pull_up"]))

GPIO_TRIGGER_OUT = int(CONFIG.get("trigger_gpio_output", DEFAULT_CONFIG["trigger_gpio_output"]))
TRIGGER_ACTIVE_HIGH = bool(CONFIG.get("trigger_active_high", DEFAULT_CONFIG["trigger_active_high"]))

def _clamp_volume(value):
    try:
        vol = int(value)
    except (TypeError, ValueError):
        vol = DEFAULT_CONFIG["audio_volume"]
    return max(0, min(100, vol))


AUDIO_OUTPUT = CONFIG.get("audio_output")
AUDIO_VOLUME = _clamp_volume(CONFIG.get("audio_volume", DEFAULT_CONFIG["audio_volume"]))

LOOP_VIDEO = "/opt/videoplayer/videos/loop.mp4"
TRIGGER_VIDEOS = [
    "/opt/videoplayer/videos/Bone Chillers 2/Horizontal/Skeleton Band/Hollusion - Horizontal/Bone2-Friendly-Orgelspiel.mp4",
    "/opt/videoplayer/videos/Bone Chillers/Scary Scenes/Window - Hologram/Bone Chillers - Scary Scenes - Window - Hologram - Fear the Reaper.mp4",
    "/opt/videoplayer/videos/Bone Chillers/Scary Scenes/Window - Hologram/Bone Chillers - Scary Scenes - Window - Hologram - Gathering Ghouls.mp4",
    "/opt/videoplayer/videos/Bone Chillers/Scary Scenes/Window - Hologram/Bone Chillers - Scary Scenes - Window - Hologram - Pop-Up Panic.mp4",
    "/opt/videoplayer/videos/Bone Chillers/Scary Scenes/Window - Hologram/Bone Chillers - Scary Scenes - Window - Hologram - Skeleton Surprise.mp4",
    "/opt/videoplayer/videos/Bone Chillers 2/Horizontal/Spooky Skeletons/Hollusion - Horizontal/BC2_Shackled Skeleton_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Grim Reaper - Hollusion - Horizontal/Grim Reaper_Startle Scare1_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Grim Reaper - Hollusion - Horizontal/Grim Reaper_Startle Scare2_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Grim Reaper - Hollusion - Horizontal/Grim Reaper_Startle Scare3_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Pumpkin King - Hollusion - Horizontal/Pumpkin King_Startle Scare1_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Pumpkin King - Hollusion - Horizontal/Pumpkin King_Startle Scare2_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends of Halloween/Horizontal/LOH - Pumpkin King - Hollusion - Horizontal/Pumpkin King_Startle Scare3_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Beware the Scarecrow - Hollusion and Disc - Horizontal/Scarecrow_Fit To Be Tied_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Beware the Scarecrow - Hollusion and Disc - Horizontal/Scarecrow_If I Only Had A Brain_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Fire and Lightning - Hollusion and Disc - Horizontal/Scarecrow_Fiery Fiend_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Fire and Lightning - Hollusion and Disc - Horizontal/Scarecrow_Storm Crow_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Scared Crows - Hollusion and Disc - Horizontal/Scarecrow_Eating Crow_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Scared Crows - Hollusion and Disc - Horizontal/Scarecrow_Scarecrow-Go-Round_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Startle Scarescrow - Hollusion and Disc - Horizontal/Scarecrow_Startle Scare2_Holl_H.mp4",
    "/opt/videoplayer/videos/Legends Of Halloween - Scarecrow 2024/Startle Scarescrow - Hollusion and Disc - Horizontal/Scarecrow_Startle Scare3_Holl_H.mp4"
]

MPV_SOCKET = "/tmp/mpv-video.sock"
MPV_LOG    = "/home/pi/mpv.log"
DEBOUNCE_MS = 0.08
WEB_TRIGGER_PORT = 8090
# ==================================================


trigger_requests = queue.Queue()


class TriggerHTTPServer(HTTPServer):
    allow_reuse_address = True


class TriggerRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/trigger":
            trigger_requests.put(time.time())
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_trigger_server():
    server = TriggerHTTPServer(("127.0.0.1", WEB_TRIGGER_PORT), TriggerRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Web-Trigger-Server läuft auf http://127.0.0.1:{WEB_TRIGGER_PORT}/trigger")
    return server


def build_mpv_variants():
    base = [
        "mpv",
        "--idle=yes",
        "--force-window=immediate",
        "--background=0/0/0",
        "--fs",
        "--no-osc", "--no-osd-bar",
        "--really-quiet",
        "--keep-open=no",
        f"--input-ipc-server={MPV_SOCKET}",
        "--no-terminal",
    ]
    if AUDIO_OUTPUT:
        device = AUDIO_OUTPUT if "/" in AUDIO_OUTPUT else f"pulse/{AUDIO_OUTPUT}"
        base += ["--ao=pulse", f"--audio-device={device}"]
    base += [f"--volume={AUDIO_VOLUME}"]
    return [
        base + ["--fs-screen=1"],
        base + ["--fs-screen=0"],
        base,
    ]


mpv_proc = None
sock = None
current_index = 0
playing_trigger = False
awaiting_trigger_loaded = False
press_armed = True


def ensure_videos_exist():
    paths = [LOOP_VIDEO] + TRIGGER_VIDEOS
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        raise FileNotFoundError("Fehlende Dateien: " + ", ".join(missing))


def try_start_mpv():
    global mpv_proc, sock
    try:
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)
    except OSError:
        pass

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")

    logf = open(MPV_LOG, "w")
    for args in build_mpv_variants():
        print("Starte mpv mit:", " ".join(args))
        mpv_proc = subprocess.Popen(args, env=env, stdout=logf, stderr=logf, close_fds=True)
        deadline = time.time() + 8.0
        while time.time() < deadline:
            if mpv_proc.poll() is not None:
                break
            if os.path.exists(MPV_SOCKET):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(MPV_SOCKET)
                sock.settimeout(0.1)
                print("mpv läuft, IPC verbunden.")
                return
            time.sleep(0.05)
        # nächster Versuch
        try:
            if mpv_proc and mpv_proc.poll() is None:
                mpv_proc.terminate()
                mpv_proc.wait(timeout=1)
        except Exception:
            pass
    raise RuntimeError("mpv konnte nicht starten. Siehe Log: " + MPV_LOG)


def mpv_cmd(cmd_list):
    msg = json.dumps({"command": cmd_list}) + "\n"
    sock.sendall(msg.encode("utf-8"))


def mpv_loadfile(path, loop=False):
    print(f"mpv: lade {'Loop' if loop else 'Clip'} → {path}")
    mpv_cmd(["loadfile", path, "replace"])
    mpv_cmd(["set", "loop-file", "inf" if loop else "no"])


def mpv_read_events():
    events = []
    while True:
        try:
            data = sock.recv(8192)
            if not data:
                break
            for line in data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line.decode("utf-8")))
                except Exception:
                    pass
        except (socket.timeout, BlockingIOError):
            break
    return events


def main():
    global current_index, playing_trigger, awaiting_trigger_loaded, press_armed

    ensure_videos_exist()
    try_start_mpv()

    btn = Button(GPIO_BUTTON, pull_up=BUTTON_PULL_UP, bounce_time=0.05)
    trigger_out = OutputDevice(GPIO_TRIGGER_OUT, active_high=TRIGGER_ACTIVE_HIGH, initial_value=False)
    trigger_out.off()

    trigger_server = None
    try:
        trigger_server = start_trigger_server()
    except OSError as exc:
        trigger_server = None
        print(f"Warnung: Web-Trigger-Server konnte nicht gestartet werden: {exc}")

    print(f"Button GPIO{GPIO_BUTTON}, pull_up={BUTTON_PULL_UP}")
    print(f"Trigger-Ausgang GPIO{GPIO_TRIGGER_OUT}, active_high={TRIGGER_ACTIVE_HIGH}")
    if AUDIO_OUTPUT:
        print(f"Audio-Ausgabe über PulseAudio-Senke '{AUDIO_OUTPUT}', Lautstärke {AUDIO_VOLUME}%")
    else:
        print(f"Audio-Ausgabe: Standardgerät, Lautstärke {AUDIO_VOLUME}%")

    mpv_loadfile(LOOP_VIDEO, loop=True)

    last_edge_time = 0.0

    try:
        while True:
            now = time.time()

            web_trigger = False
            while True:
                try:
                    trigger_requests.get_nowait()
                    web_trigger = True
                except queue.Empty:
                    break

            # Button- und Web-Handling
            if not playing_trigger:
                if web_trigger:
                    if current_index >= len(TRIGGER_VIDEOS):
                        current_index = 0
                    print(f"Web-Oberfläche → starte Trigger-Video {current_index+1}/{len(TRIGGER_VIDEOS)}")
                    playing_trigger = True
                    awaiting_trigger_loaded = True
                    mpv_loadfile(TRIGGER_VIDEOS[current_index], loop=False)
                    last_edge_time = now
                elif btn.is_pressed and press_armed:
                    if now - last_edge_time >= DEBOUNCE_MS:
                        if current_index >= len(TRIGGER_VIDEOS):
                            current_index = 0
                        print(f"Taster → starte Trigger-Video {current_index+1}/{len(TRIGGER_VIDEOS)}")
                        playing_trigger = True
                        awaiting_trigger_loaded = True
                        mpv_loadfile(TRIGGER_VIDEOS[current_index], loop=False)
                        press_armed = False
                        last_edge_time = now

            if not btn.is_pressed and not press_armed:
                if now - last_edge_time >= DEBOUNCE_MS:
                    press_armed = True
                    last_edge_time = now

            # mpv-Events
            for ev in mpv_read_events():
                evname = ev.get("event")

                if evname == "file-loaded":
                    if playing_trigger and awaiting_trigger_loaded:
                        awaiting_trigger_loaded = False
                        trigger_out.on()   # Trigger EIN (LOW bei active_high=False)
                        print("Trigger läuft → Ausgang EIN")

                elif evname == "end-file":
                    if playing_trigger and not awaiting_trigger_loaded:
                        trigger_out.off()  # Trigger AUS
                        current_index += 1
                        playing_trigger = False
                        print("Trigger fertig → zurück zum Loop (Ausgang AUS)")
                        mpv_loadfile(LOOP_VIDEO, loop=True)

            if mpv_proc and mpv_proc.poll() is not None:
                trigger_out.off()
                raise RuntimeError(f"mpv beendet. Log: {MPV_LOG}")

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        trigger_out.off()
        try:
            trigger_out.close()
            btn.close()
        except Exception:
            pass
        try:
            if trigger_server:
                trigger_server.shutdown()
                trigger_server.server_close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass
        if mpv_proc and mpv_proc.poll() is None:
            mpv_proc.terminate()
            try:
                mpv_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                mpv_proc.kill()


if __name__ == "__main__":
    main()
