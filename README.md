# BeamerPi Videoplayer

Dieses Projekt stellt einen einfachen Videoplayer für den Raspberry Pi (Debian Bookworm) bereit. Ein dauerhaft laufendes Loop-Video wird im Vollbild mit `mpv` abgespielt. Über eine Weboberfläche können Playlisten verwaltet werden. Beim Auslösen eines Triggers wird das nächste Video aus der aktiven Playlist abgespielt, danach wechselt der Player automatisch zurück zum Loop-Video.

## Installation

1. **Systempakete installieren**

   ```bash
   sudo apt update
   sudo apt install mpv python3-flask python3-gevent python3-venv
   ```

   Optional kann zusätzlich ein virtuelles Python-Umfeld erstellt werden:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install flask gevent
   ```

2. **Projektdateien platzieren**

   Kopiere dieses Repository auf den Raspberry Pi, z. B. nach `/opt/videoplayer/app`.

3. **Verzeichnisse vorbereiten**

   Lege den Video-Ordner an, falls er noch nicht existiert:

   ```bash
   sudo mkdir -p /opt/videoplayer/videos
   sudo chown -R $USER:$USER /opt/videoplayer
   ```

4. **Anwendung starten**

   ```bash
   export FLASK_APP=app.app:create_app
   flask run --host=0.0.0.0 --port=5000
   ```

   Für einen Dienst im Hintergrund kann ein Systemd-Service eingerichtet werden.

## Nutzung

- Öffne die Weboberfläche unter `http://<RaspberryPi-IP>:5000`.
- Erstelle Playlisten, wähle ein Loop-Video und füge weitere Videos hinzu.
- Starte eine Playlist, damit das Loop-Video abgespielt wird.
- Betätige den Button „Nächstes Video triggern“ oder rufe den Webhook `POST /webhook/<playlistname>` auf, um Videos in Reihenfolge abzuspielen. Alternativ kann `POST /api/trigger` mit JSON `{ "playlist": "Name" }` verwendet werden.
- In den Einstellungen kann das `mpv` Audio-Gerät festgelegt werden (z. B. `alsa/plughw:0,0`, `alsa/hdmi`, etc.).

Die Videodateien müssen im Ordner `/opt/videoplayer/videos` liegen.
