# Erklärung der Berechnungsgrundlagen
Damit du das Skript sicher anwenden kannst, sind hier die physikalischen Hintergründe, die im Code verwendet werden.
## Der Soll-Volumenstrom (Thermisch)
Die Basis bildet der Wärmebedarf des Raumes.$$\dot{V} = \frac{\dot{Q}}{c \cdot \Delta T}$$
Legende:
* $\dot{Q}$: Heizlast in Watt.
* $c$: Spezifische Wärmekapazität (ca. $1,163 \, \text{Wh/(kg}\cdot\text{K)}$).
* $\Delta T$: Spreizung (Differenz Vorlauf/Rücklauf).

## Der Ist-Volumenstrom (Hydraulisch)
Hier prüfen wir deine Planung. Wir nutzen die $K_v$-Wert-Formel für Ventile. Das Ventil ist im abgeglichenen Zustand oft der größte Widerstand im Strang und bestimmt den Fluss maßgeblich.$$\dot{V} \, [\text{m}^3/\text{h}] = K_v \cdot \sqrt{\Delta p \, [\text{bar}]}$$Wichtig: Du musst in deiner Planung den $K_v$-Wert der Einstellung (z. B. Stufe 3) nehmen, nicht den $K_{vs}$-Wert (Ventil komplett offen), es sei denn, du planst das Ventil offen zu lassen.
## Fließgeschwindigkeit
Besonders bei der Planung der Rohrdurchmesser relevant.$$w = \frac{\dot{V}}{A}$$Hier ist es wichtig, dass du bei Heizkörperanbindungen unter 0,5 m/s bleibst, um keine störenden Geräusche im Schlaf- oder Wohnzimmer zu verursachen.Vorgehensweise für dich

1. Datenblatt zur Hand nehmen: Du brauchst das Datenblatt deiner Thermostatventile (z. B. Heimeier, Danfoss), um die Voreinstellungszahlen (1-6 oder N) in echte $K_v$-Werte zu übersetzen.
2. Pumpendruck: Du musst wissen, welcher Differenzdruck ($\Delta p$) an diesem spezifischen Strang zur Verfügung steht. Bei weit entfernten Heizkörpern ist dieser durch die Rohrreibungsverluste geringer als direkt hinter der Pumpe.
3. Skript füttern: Trage deine Werte oben im Bereich simulation_starten() ein oder erweitere das Skript, um eine CSV-Liste deiner Planung einzulesen.