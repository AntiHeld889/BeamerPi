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
   flask --app app.app:create_app run --host=0.0.0.0 --port=5000
   ```

## Betrieb als systemd-Service

Um den Videoplayer dauerhaft im Hintergrund laufen zu lassen, kann ein systemd-Dienst
eingesetzt werden. Dadurch wird der Server beim Systemstart automatisch geladen und bei
Fehlern neu gestartet.

1. **Service-Datei erstellen**

   Erstelle z. B. `/etc/systemd/system/beamerpi.service` (Root-Rechte erforderlich) mit folgendem Inhalt:

   ```ini
   [Unit]
   Description=BeamerPi Videoplayer
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=pi
   Group=pi
   WorkingDirectory=/opt/videoplayer/app
   ExecStart=/usr/bin/python3 -m flask --app app.app:create_app run --host=0.0.0.0 --port=5000
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

   Passe `User`, `Group`, `WorkingDirectory` und den Pfad zur Python-Installation an deine
   Umgebung an. In einer virtuellen Umgebung ersetzt du `/usr/bin/python3` durch den Pfad
   zum Python-Interpreter aus dem venv (z. B. `/opt/videoplayer/.venv/bin/python`).

2. **Dienst aktivieren und starten**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now beamerpi.service
   ```

   Den Status des Dienstes kannst du jederzeit mit `sudo systemctl status beamerpi.service`
   prüfen. Log-Ausgaben erscheinen über `journalctl -u beamerpi.service`.

## Nutzung

- Öffne die Weboberfläche unter `http://<RaspberryPi-IP>:5000`.
- Erstelle Playlisten, wähle ein Loop-Video und füge weitere Videos hinzu.
- Starte eine Playlist, damit das Loop-Video abgespielt wird.
- Betätige den Button „Nächstes Video triggern“ oder rufe den Webhook `POST /webhook/<playlistname>` auf, um Videos in Reihenfolge abzuspielen. Alternativ kann `POST /api/trigger` mit JSON `{ "playlist": "Name" }` verwendet werden.
- In den Einstellungen kann das `mpv` Audio-Gerät festgelegt werden (z. B. `alsa/plughw:0,0`, `alsa/hdmi`, etc.).

Die Videodateien müssen im Ordner `/opt/videoplayer/videos` liegen.
