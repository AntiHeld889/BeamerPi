# BeamerPi

Dieses Projekt stellt einen einfachen Video-Player zur Verfügung, der über eine Weboberfläche oder eine HTTP-API gesteuert werden kann. Die folgenden Beispiele zeigen, wie die wichtigsten Endpunkte angesprochen werden können.

## API bedienen

Die Anwendung lauscht standardmäßig auf Port `5000`. Ersetze in den Beispielen `localhost:5000` durch die Adresse deines BeamerPi-Servers.

### Nächstes Video starten

Das nächste Video der aktuell aktiven Playlist kann entweder über einen `POST`- oder einen `GET`-Request ausgelöst werden. Optional kann dabei eine Playlist angegeben werden, die zuvor gestartet werden soll.

```bash
# Nächstes Video aus der bereits aktiven Playlist starten (POST)
curl -X POST http://localhost:5000/api/trigger

# Gleiches Beispiel als GET-Aufruf
curl "http://localhost:5000/api/trigger"

# Playlist "Intro" starten (falls noch nicht aktiv) und danach das nächste Video triggern
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"playlist": "Intro"}' \
  http://localhost:5000/api/trigger

# Playlist per GET-Parameter setzen und triggern
curl "http://localhost:5000/api/trigger?playlist=Intro"
```

Der Endpunkt antwortet mit `{"status": "ok"}` wenn ein Video erfolgreich in die Wiedergabe übernommen wurde. Ist keine Playlist aktiv oder enthält sie keine Videos, wird ein Fehlercode (`400` bzw. `404`) zurückgegeben.

### Status abfragen

Über einen `GET`-Request auf `/api/status` lässt sich der aktuelle Zustand abrufen, inklusive Name der aktiven Playlist und Informationen zum nächsten Video.

```bash
curl http://localhost:5000/api/status
```

### Playlists als JSON abrufen

Mit einem `GET`-Request auf `/api/playlists` erhältst du eine Übersicht aller gespeicherten Playlists samt Status, Loop-Video und Trackliste. Die aktuell aktive Playlist ist im Feld `is_active` markiert und enthält unter `progress` zusätzliche Informationen zum nächsten Track.

```bash
curl http://localhost:5000/api/playlists
```

### Verfügbare Videos auflisten

Über `/api/videos` liefert der Player eine flache Liste aller gefundenen Videodateien und zusätzlich eine hierarchische Struktur (`tree`), die Unterordner widerspiegelt. Das erleichtert das Bauen eigener Verwaltungs-Frontends.

```bash
curl http://localhost:5000/api/videos
```

### Playlist per Webhook starten

Soll eine bestimmte Playlist ohne zusätzlichen Payload gestartet werden, kann der Webhook-Endpunkt genutzt werden:

```bash
curl -X POST http://localhost:5000/webhook/Intro
```

Der Platzhalter `Intro` wird dabei durch den Namen der gewünschten Playlist ersetzt.

## Weitere Hinweise

* Stelle sicher, dass die Videodateien im Verzeichnis `/opt/videoplayer/videos` liegen, damit sie vom Player gefunden werden.
* Einstellungen wie Audio-Ausgabe oder optionale Webhooks für Start/Ende können in der Weboberfläche unter `/settings` angepasst werden.
