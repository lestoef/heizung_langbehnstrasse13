Heizung: Simulation & Hydraulischer Abgleich — Bedienungsanleitung

Dieses Repository enthält zwei Werkzeuge zur hydraulischen Überprüfung und zum hydraulischen Abgleich einer Heizungsanlage:

- `heizung_simulation.py` — Core-Simulationslauf: lädt `heizung_config.json`, berechnet Druckverluste (Darcy–Weisbach), löst das Rohrnetz iterativ (Vorwärts-/Rückwärts-Relaxation) und exportiert Ergebnisse (CSV, PNG).
- `heizung_simulation_auto_optimierer.py` — Auto-Balancer: benutzt das selbe Modell, führt adaptiv-dämpfende Anpassungen an Strangventil-kV-Werten durch, um simulierte Masseströme an die Zielwerte (Heizlast / Design-Flow) anzunähern.

Das Verzeichnis `scenarios/` enthält Beispiel-Szenarien, generierte Vergleichsdateien und eine interaktive Infografik (`infographic.html`) zum lokalen Feintuning.

---

## Ziel dieser README

Diese Anleitung erklärt:

- Wie Du das Skript einsetzt, um Massenströme zu optimieren.
- Wie Du die Situation "zwei Pumpen geplant — nur eine gebaut" analysierst.
- Die physikalischen Grundlagen (Rohrverluste, Ventile, Reynolds‑Zahl) kurz und praxisorientiert.

---

## Quickstart — praktische Schritte

1) Voraussetzungen

```bash
python3 --version           # Python 3
python3 -m pip install --user matplotlib
```

2) Basissimulation (prüft, ob die vorhandene Pumpe die Design-Massenströme erreichen kann)

```bash
python3 heizung_simulation.py
```

3) Automatischen Abgleich ausführen (nutzt Ergebnisse des Basislaufs als Targets)

```bash
python3 heizung_simulation_auto_optimierer.py
```

4) Ergebnisdateien

- CSV: `heizung_vergleich_*.csv` (Vergleich Urspr. vs Sim. Q, P, kV)
- Diagramme / Topologie: PNG-Dateien (z. B. `heizung_diagramm.png`, `topology_optimized.png`)
- Interaktive Visualisierung: `scenarios/infographic.html` (lokal im Browser öffnen)

---

## Besondere Projekt‑Situation: Geplant mit zwei Pumpen — gebaut nur eine

In manchen Projekten sind zwei Pumpen vorgesehen (z. B. je eine Pumpe pro Heizkreis). Wurde das System jedoch nur mit einer Pumpe realisiert oder die Kreise in Serie geschaltet, ändert sich die Druckverteilung fundamental:

- Die verbliebene Pumpe muss nun sowohl die Druckhöhe für alle Stränge liefern als auch gegen erhöhte Summenwiderstände anarbeiten.
- Folge: einige Stränge können unterversorgt werden, insbesondere die weiter entfernten oder durch enge Rohre/mehr Formstücke belasteten.

Mit den Skripten hier kannst Du diese Abweichung einfach prüfen:

1. Simuliere die ursprüngliche (geplante) Konfiguration (zwei Pumpen, falls konfiguriert) und notiere Soll‑Ströme.
2. Simuliere die tatsächlich gebaute Konfiguration (eine Pumpe / serielle Verschaltung) — vergleiche resultierende Strömungen.
3. Starte den Auto‑Optimierer, um zu sehen, ob Ventil‑Feinjustage (kV‑Anpassung) die Zielwerte wiederherstellen kann.

Beurteilung:

- Wenn Optimierung viele kV bis zum Max-Limit setzt und Ströme trotzdem zu niedrig bleiben → Pumpen- oder Topologieproblem (Hardware-Lösung nötig).
- Wenn Optimierung kleine/mittele Anpassungen findet (und Abweichungen < 2–3%) → hydraulischer Abgleich per Ventile kann genügen.

---

## Wissenschaftliche Hintergründe (kompakt, aber fundiert)

1) Darcy–Weisbach — Druckverlust in Rohren

Die Grundgleichung für Rohrreibungsverluste lautet:

	Δp = λ · (L/D) · (ρ/2) · v²

Wobei Δp der Druckverlust (Pa), λ die Reibungszahl, L die Leitungslänge, D der Innendurchmesser, ρ die Dichte und v die Strömungsgeschwindigkeit ist.

Die Reibungszahl λ hängt von der Reynolds‑Zahl ab:

- Laminar (Re < ca. 2300): λ = 64 / Re
- Turbulent: λ wird z. B. durch Colebrook‑Formeln beschrieben; in der Implementierung verwenden wir eine numerisch robuste Näherung (logarithmische Näherung / Blasius‑ähnliche Formeln) unter Berücksichtigung der Rohrrauheit.

Hinweis: Korrekter Innendurchmesser ist wesentlich — bei Kupferrohren wird dieser aus dem Namen (z. B. CU15x1.0) abgeschätzt (Innen = Außen – 2×Wandstärke).

2) Ventile (kV‑Charakteristik)

Ventilöffnung wird durch den kV‑Wert beschrieben. Die typische Gleichung für Ventile ist:

	q [m³/h] = kV × sqrt(Δp [bar])

In unseren Skripts wird zur Benutzer‑Wahrnehmung oft q in l/h verwendet, daher q[l/h] ≈ kV × sqrt(p[bar]) × 1000.

3) Reynolds‑Zahl und Strömungsregimes

Re = ρ·v·D / μ

- Kleinere Rohre + geringe Geschwindigkeit → laminar → anderes λ-Verhalten.
- Größere Re → Übergangs-/turbulente Strömung → komplexere λ‑Abhängigkeit.

4) Netz‑Kopplung und iterative Lösung

Da Δp ∝ v^2 und v ∝ q/A, ist Δp quadratisch in q. Änderungen bei Ventilstellungen oder Pumpen beeinflussen sowohl lokalen als auch globalen Druck → das Ergebnis ist ein gekoppelte nichtlineares System. Die Skripte lösen dies mit einem iterativen Vorwärts–Rückwärts‑Relaxationsverfahren:

- Rückwärts: Aggregiere benötigte Strangflüsse von Ende zu Pumpen.
- Vorwärts: Aktualisiere Drücke vom Pumpenausgang ausgehend; berechne neue Verbraucherströme bei gegebenem Druck.
- Wiederhole, bis Fluss/ Druck stabil sind.

---

## Praktische Hinweise — Interpretation & Troubleshooting

- CSV‑Spalten prüfen: `Urspr. Q [l/h]` (Design), `Sim. Q [l/h]` (Simuliert), `Sim. kV`. Nutze diese für Abweichungsanalysen.
- Druckwerte (`Pressure_Bar`) anschauen: Starke Druckeinbrüche über kurzem Abschnitt → Engpass.
- Optimierer‑Warnings: Wenn viele Ventile voll geöffnet sind, aber Ströme weiterhin zu niedrig → Pump- oder Topologie‑Problem.
- Pipe surcharge: Stelle `pipe_surcharge_factor` höher ein, wenn viele Bögen/Armaturen vorhanden sind — simuliert höhere Formverluste.

---

## Beispiel-Workflow

1) Basissimulation → `heizung_simulation.py`
2) Szenario: setze `scenarios.json` mit `merge_circuits` oder `set_valve_kv` 
3) Führe Auto‑Optimierer → `heizung_simulation_auto_optimierer.py`
4) Kontrolliere `scenarios/heizung_vergleich_optimiert.csv` und `scenarios/infographic.html`.
