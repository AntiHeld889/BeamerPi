#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Einfaches Web-Interface zur Konfiguration des Videoplayers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List
from urllib import error as urlerror
from urllib import request as urlrequest

from flask import Flask, flash, redirect, render_template_string, request, url_for


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TRIGGER_ENDPOINT = "http://127.0.0.1:8090/trigger"

DEFAULT_CONFIG: Dict[str, object] = {
    "trigger_gpio_input": 27,
    "trigger_gpio_output": 26,
    "trigger_active_high": False,
    "button_pull_up": False,
    "audio_output": None,
    "audio_volume": 100,
}


def load_config() -> Dict[str, object]:
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


def save_config(data: Dict[str, object]) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_config_exists() -> None:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)


def list_audio_outputs() -> List[Dict[str, str]]:
    """Liest verfügbare PulseAudio-Sinks ein."""

    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    sinks: List[Dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            name = parts[1]
            description = parts[-1] if len(parts) > 4 else name
            sinks.append({"name": name, "description": description})
    return sinks


def clamp_volume(value: object) -> int:
    try:
        vol = int(value)
    except (TypeError, ValueError):
        vol = DEFAULT_CONFIG["audio_volume"]
    return max(0, min(100, vol))


def trigger_via_http() -> bool:
    try:
        req = urlrequest.Request(TRIGGER_ENDPOINT, data=b"", method="POST")
        with urlrequest.urlopen(req, timeout=2):
            return True
    except (OSError, urlerror.URLError, urlerror.HTTPError):
        return False


ensure_config_exists()

app = Flask(__name__)
app.secret_key = "beamerpi-config-secret"


@app.route("/", methods=["GET", "POST"])
def index():
    config = load_config()
    audio_outputs = list_audio_outputs()
    known_audio_ids = {sink["name"] for sink in audio_outputs}
    custom_audio_value = (
        config["audio_output"]
        if config.get("audio_output") and config["audio_output"] not in known_audio_ids
        else ""
    )

    if request.method == "POST":
        try:
            trig_in = int(request.form.get("trigger_gpio_input", config["trigger_gpio_input"]))
            trig_out = int(request.form.get("trigger_gpio_output", config["trigger_gpio_output"]))
        except (TypeError, ValueError):
            flash("Ungültige GPIO-Nummer.", "error")
            return redirect(url_for("index"))

        audio_output = request.form.get("audio_output") or None
        if audio_output == "__other__":
            audio_output = request.form.get("audio_output_custom") or None

        new_config = {
            "trigger_gpio_input": max(0, trig_in),
            "trigger_gpio_output": max(0, trig_out),
            "trigger_active_high": request.form.get("trigger_active_high") == "on",
            "button_pull_up": bool(config.get("button_pull_up", False)),
            "audio_output": audio_output or None,
            "audio_volume": clamp_volume(request.form.get("audio_volume")),
        }

        save_config({**DEFAULT_CONFIG, **new_config})
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for("index"))

    return render_template_string(
        TEMPLATE,
        config=config,
        audio_outputs=audio_outputs,
        custom_audio_value=custom_audio_value,
    )


@app.post("/trigger")
def trigger():
    if trigger_via_http():
        flash("Trigger ausgelöst.", "success")
    else:
        flash("Trigger konnte nicht ausgelöst werden.", "error")
    return redirect(url_for("index"))


TEMPLATE = """
<!DOCTYPE html>
<html lang=\"de\">
  <head>
    <meta charset=\"utf-8\" />
    <title>BeamerPi Einstellungen</title>
    <style>
      body { font-family: system-ui, sans-serif; background: #f5f5f5; margin: 0; }
      header { background: #222; color: #fff; padding: 1.5rem; }
      main { max-width: 640px; margin: 2rem auto; background: #fff; padding: 2rem; box-shadow: 0 10px 40px rgba(0,0,0,0.1); border-radius: 12px; }
      h1 { margin-top: 0; }
      label { display: block; font-weight: 600; margin-bottom: 0.4rem; }
      input[type=number], select, input[type=text] { width: 100%; padding: 0.6rem; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
      .field { margin-bottom: 1.4rem; }
      .actions { text-align: right; }
      button { background: #007bff; color: white; border: none; border-radius: 6px; padding: 0.8rem 1.4rem; font-size: 1rem; cursor: pointer; }
      button:hover { background: #0064d4; }
      .flash { padding: 0.8rem 1rem; border-radius: 6px; margin-bottom: 1rem; }
      .flash.success { background: #d1e7dd; color: #0f5132; border: 1px solid #badbcc; }
      .flash.error { background: #f8d7da; color: #842029; border: 1px solid #f5c2c7; }
      .checkbox { display: flex; align-items: center; gap: 0.6rem; }
    </style>
  </head>
  <body>
    <header>
      <h1>BeamerPi Einstellungen</h1>
    </header>
    <main>
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class=\"flash {{ category }}\">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method=\"post\" action=\"{{ url_for('trigger') }}\" style=\"margin-bottom:1.5rem;\">
        <div class=\"actions\">
          <button type=\"submit\">Trigger jetzt auslösen</button>
        </div>
      </form>

      <form method=\"post\" action=\"{{ url_for('index') }}\">
        <section class=\"field\">
          <label for=\"trigger_gpio_input\">Trigger GPIO (Eingang)</label>
          <input type=\"number\" id=\"trigger_gpio_input\" name=\"trigger_gpio_input\" min=\"0\" value=\"{{ config['trigger_gpio_input'] }}\" required />
        </section>

        <section class=\"field\">
          <label for=\"trigger_gpio_output\">Ausgabe GPIO</label>
          <input type=\"number\" id=\"trigger_gpio_output\" name=\"trigger_gpio_output\" min=\"0\" value=\"{{ config['trigger_gpio_output'] }}\" required />
        </section>

        <section class=\"field checkbox\">
          <input type=\"checkbox\" id=\"trigger_active_high\" name=\"trigger_active_high\" {% if config['trigger_active_high'] %}checked{% endif %} />
          <label for=\"trigger_active_high\">Ausgang ist HIGH-aktiv</label>
        </section>

        <section class=\"field\">
          <label for=\"audio_output\">Audioausgabe</label>
          <select id=\"audio_output\" name=\"audio_output\">
            <option value=\"\" {% if not config['audio_output'] %}selected{% endif %}>Standard (Systemvorgabe)</option>
            {% for sink in audio_outputs %}
              <option value=\"{{ sink.name }}\" {% if sink.name == config['audio_output'] %}selected{% endif %}>{{ sink.description }}</option>
            {% endfor %}
            <option value=\"__other__\" {% if custom_audio_value %}selected{% endif %}>Andere PulseAudio-Senke...</option>
          </select>
          <input type=\"text\" id=\"audio_output_custom\" name=\"audio_output_custom\" placeholder=\"pulse/alsa_device\" style=\"margin-top:0.5rem;\" value=\"{{ custom_audio_value }}\" />
        </section>

        <section class=\"field\">
          <label for=\"audio_volume\">Lautstärke (%)</label>
          <input type=\"number\" id=\"audio_volume\" name=\"audio_volume\" min=\"0\" max=\"100\" value=\"{{ config['audio_volume'] }}\" required />
        </section>

        <div class=\"actions\">
          <button type=\"submit\">Speichern</button>
        </div>
      </form>
    </main>
  </body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)


