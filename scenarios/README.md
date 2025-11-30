# Szenarios / Ergebnisse (automatischer Optimierer)

Dieses Verzeichnis enthält die Ergebnisdateien des Skripts `heizung_simulation_auto_optimierer.py`.

Hier finden Sie sowohl die Rohdaten (CSV) als auch die Szenario-Definitionen (JSON) und eine interaktive Infografik, mit der Sie ausprobieren können, wie sich Änderungen an den Ventil-kV-Werten auf die Massenströme auswirken.

---

## Inhalt

- `heizung_vergleich_aktuelle_ventileinstellungen.csv` – Vergleich von Zielwerten und simulierten Werten nach dem Seriellen Umbau mit den *aktuellen* Ventileinstellungen.
- `heizung_vergleich_optimiert.csv` – Ergebnis nach automatischem hydraulischem Abgleich (optimierte kV-Werte).
- `heizung_vergleich_ventile_wie_geplant.csv` – Ergebnis wenn die Ventile unverändert bleiben („wie geplant“).
- `scenarios_aktuelle_ventileinstellungen.json` – Szenario-Definition: serieller Umbau + set_valve_kv (aktuelle Einstellungen)
- `scenarios_optimiert.json` – Szenario-Definition mit den automatisch ermittelten kV-Zielen
- `scenarios_ventile_wie_geplant.json` – Szenario mit Ventilen unverändert
- `infographic.html` – Interaktive Infografik (lokal öffnen, siehe unten)

---

## Kurze Erklärung der Dateien (Spalten in den CSVs)

- `Strangname` — Name des Strangs / Verbrauchers
- `Urspr. Q [l/h]` — Gewünschter Massenstrom (Ausgang aus Heizlast- / Rohrnetzberechnung)
- `Sim. Q [l/h]` — Simulierter Massenstrom nach Anwendung des Szenarios
- `Urspr. P [W]` / `Sim. P [W]` — Heizleistung (Original / simuliert)
- `Urspr. kV` / `Sim. kV` — Ventil kV (Original / simuliert)

---

## Ziel dieser Dokumentation

Das Ziel ist, die geforderten Massenströme ("Urspr. Q") durch Anpassung der Strangventile (kV) zu erreichen. Die interaktive Infografik zeigt für jeden Strang: Zielstrom, aktuellen simulierten Strom und erlaubt, per Schieberegler die kV-Werte zu verändern und die resultierenden Massenströme (vereinfachtes Modell) zu sehen.

> Hinweis: Die Infografik verwendet zur Berechnung eine vereinfachte, aber typische Beziehung:
>
> q [l/h] = kV * sqrt(p [bar]) * 1000
>
> Wir schätzen für jede Zeile ein lokales Referenzdruck-Element p anhand der in den CSVs vorliegenden simulierten Werte und kV. Damit lässt sich interaktiv demonstrieren, wie kV-Änderungen den Massenstrom lokal beeinflussen. Diese Vereinfachung zeigt die Wirkung der Ventil-Einstellung gut, ersetzt aber nicht eine vollständige, gekoppelten Netzsimulation.

---

## Interaktive Infografik

Datei: `infographic.html` — einfach lokal im Browser öffnen (kein Server erforderlich). Die Seite enthält Daten der CSV-Dateien und bietet drei Buttons, um die aktuell simulierten Einstellungen, die automatisch optimierten Einstellungen, oder die "wie geplant"-Einstellungen zu laden.

### Anleitung

1. Öffnen Sie die Datei `scenarios/infographic.html` im Browser (Doppelklick / "Open File").
2. Sie sehen pro Strang einen Schieberegler (kV), die Ziel- bzw. simulierten Massenströme und eine Live-Visualisierung (Balkendiagramm).
3. Ziehen Sie den Regler: die Massenström neu berechnet und zeigt Abweichung von der Zielströmstärke.
4. Mit "Load optimized" setzen Sie die kV-Werte auf die automatisch ermittelten Werte (aus `scenarios_optimiert.json`).

---

## Weiteres / Wie die Ergebnisse erzeugt wurden

Die CSVs wurden vom Python-Skript `heizung_simulation_auto_optimierer.py` erzeugt. Dieses macht:

- hydraulische Berechnung der Kreise
- iterative automatische Anpassung der kV-Werte (adaptive Robustheits-Logik)
- Erzeugung der Vergleichs-CSV- und Diagramm-Dateien

Zur erneuten Berechnung mit anderen Konfigurationen: Skript anpassen bzw. `scenarios.json` (obere Ebene) ändern, dann lokal `python3 heizung_simulation_auto_optimierer.py` ausführen.

## Quick Start — Ergebnis neu erzeugen & Infografik öffnen

Kurzanleitung um die CSVs / Grafiken neu zu erzeugen und die Infografik zu öffnen:

1. Sicherstellen, dass Python 3 sowie matplotlib installiert sind (oder ein vorhandenes venv aktivieren).

2. Skript starten (im Projekt-Root):

```bash
python3 heizung_simulation_auto_optimierer.py
```

3. Nach Ausführung liegen die neuen CSV-Dateien und Diagramme im Projekt-Root bzw. im `scenarios/` Verzeichnis.

4. Öffne die Infografik lokal (kein Server nötig):

```text
xdg-open scenarios/infographic.html  # Linux
open scenarios/infographic.html      # macOS
# oder einfach im Dateiexplorer den File öffnen
```
