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

	Δp = λ · (L/D) · (ρ/2) · v^2

Wobei Δp der Druckverlust (Pa), λ die Reibungszahl, L die Leitungslänge, D der Innendurchmesser, ρ die Dichte und v die Strömungsgeschwindigkeit ist.

Die Reibungszahl λ hängt von der Reynolds‑Zahl ab:

- Laminar (Re < ca. 2300): λ = 64 / Re
- Turbulent: λ wird z. B. durch Colebrook‑Formeln beschrieben; in der Implementierung verwenden wir eine numerisch robuste Näherung (logarithmische Näherung / Blasius‑ähnliche Formeln) unter Berücksichtigung der Rohrrauheit.

Hinweis: Korrekter Innendurchmesser ist wesentlich — bei Kupferrohren wird dieser aus dem Namen (z. B. CU15x1.0) abgeschätzt (Innen = Außen – 2×Wandstärke).

2) Ventile (kV‑Charakteristik)

Ventilöffnung wird durch den kV‑Wert beschrieben. Die typische Gleichung für Ventile ist:

	q [m^3/h] = kV × sqrt(Δp [bar])

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

---

Wenn Du möchtest, ergänze ich:

- eine kleine Test‑/Validierungssuite (Unit‑Tests + analytische Fälle)
- Beispiel‑Konfigurationen für "2 Pumpen geplant / 1 gebaut"
- eine erweiterte Infografik, die CSV/JSON direkt vom lokalen Server lädt (dynamisch)

— Ende —

2. Basissimulation ausführenStartet einen einzelnen Berechnungslauf basierend auf der aktuellen heizung_config.json. Prüft, ob die Pumpenleistung für die gewünschten Durchflüsse ausreicht.python3 heizung_simulation.py
3. Automatischen Abgleich startenStartet den Optimierer, der versucht, die Ventileinstellungen ($k_v$) so anzupassen, dass alle Räume optimal versorgt werden.python3 heizung_simulation_auto_optimierer.py
4. Ergebnisse visualisierenÖffnen Sie die generierte Infografik im Browser, um die Auswirkungen interaktiv zu sehen:# Linux
xdg-open scenarios/infographic.html

# macOS
open scenarios/infographic.html
⚙️ Physikalische Grundlagen & ModellDas Tool nutzt iterative numerische Verfahren zur Lösung des hydraulischen Netzwerks.1. Druckverlust in RohrenBerechnet nach der Darcy-Weisbach-Gleichung.Rohrinnendurchmesser: Wird automatisch aus Bezeichnungen wie CU15x1.0 berechnet ($d_{innen} = d_{außen} - 2 \cdot s$).Reibungsbeiwert ($\lambda$):Laminar ($Re < 2300$): $\lambda = 64 / Re$Turbulent: Näherungsformel (ähnlich Colebrook) für raue Rohre.Formstücke: Ein pipe_surcharge_factor (z.B. 0.2-0.5) kann in der Config gesetzt werden, um Druckverluste durch Bögen und Fittings pauschal zu simulieren.2. Ventil- und VerbrauchermodellMit Ventil: Das Modell nutzt die klassische $k_v$-Wert Formel:$$ \dot{V} [l/h] = k_v \cdot \sqrt{\Delta p [bar]} \cdot 1000 $$Ohne Ventil (Direktanschluss): Wird als fester hydraulischer Widerstand modelliert, der rein durch die Rohrgeometrie und den Heizkörper bestimmt wird.3. Iterativer LöserDa Druckverluste quadratisch vom Durchfluss abhängen ($\Delta p \propto \dot{V}^2$) und Netze rückgekoppelt sind, wird ein Relaxationsverfahren verwendet. Das System iteriert (Vorwärts-/Rückwärtsrechnung), bis sich Druck und Massenstrom im gesamten Netz stabilisiert haben.🛠 Workflow zur RohrnetzprüfungWie helfen diese Skripte bei der Fehleranalyse in realen Anlagen?SchrittSkript / AktionZiel1. Basis-Checkheizung_simulation.pyVergleich Simulierter Fluss vs. Soll-Fluss. Wenn Sim << Soll, ist die Pumpe zu schwach oder das Rohrnetz zu restriktiv.2. SzenarienJSON bearbeitenWas passiert, wenn ich Heizkreise zusammenlege oder die Pumpe höher stelle?3. Optimierung..._auto_optimierer.pyKann ich das Problem überhaupt durch Ventileinstellung lösen? Wenn der Optimierer Ventile voll öffnet und trotzdem Unterversorgung herrscht, liegt ein Hardware-Problem vor.4. AnalyseCSV AuswertungPrüfen der heizung_vergleich_*.csv. Relative Abweichungen berechnen.✅ Praktische Prüfliste (Verifikation)Nutzen Sie diese Schritte, um die Plausibilität der Simulation zu testen:[ ] Einzelstrang-Test: Reduzieren Sie die JSON auf einen Strang und vergleichen Sie das Ergebnis mit einer manuellen Rechnung.[ ] Pumpen-Test: Ändern Sie pump_head_m. Die Durchflüsse müssen physikalisch korrekt steigen/fallen.[ ] Zuschlagsfaktoren: Setzen Sie pipe_surcharge_factor auf realistische Werte (0.3 für viele Bögen), um reale Verluste besser abzubilden.[ ] Druckverlauf: Prüfen Sie die Spalte Pressure_Bar in der CSV, um Engstellen (hoher Druckabfall auf kurzem Stück) zu finden.🔮 Ausblick & Roadmap[ ] Unit-Tests für kritische Hydraulik-Funktionen.[ ] Import von CSV-Daten direkt in die infographic.html.[ ] GUI für interaktives Tuning der $k_v$-Werte.[ ] Support für hydraulische Weichen im Modell.Erstellt für die Analyse und Optimierung privater und gewerblicher Heizungsanlagen.