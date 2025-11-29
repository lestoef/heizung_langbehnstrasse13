import numpy as np
from scipy.optimize import fsolve
import json
import csv
import sys 

# --- 1. Hilfsklassen ---

class HydraulicComponent:
    """Basisklasse für hydraulische Komponenten."""
    def __init__(self, name):
        self.name = name

class Pipe(HydraulicComponent):
    """Rohrstück, berechnet den K-Wert basierend auf geschätzter Länge und Durchmesser."""
    def __init__(self, name, length_m, od_mm, thickness_mm=1.5, lam=0.02):
        super().__init__(name)
        self.length = length_m
        self.diameter = (od_mm - 2 * thickness_mm) / 1000.0  # Innendurchmesser in m
        self.lambda_factor = lam  # Reibungsbeiwert (angenommen für Kupfer/Stahl)

    def get_resistance_k(self):
        """
        Berechnet den hydraulischen Widerstandsbeiwert K, sodass dP = K * Q^2.
        K_SI = (8 * lambda * L * rho) / (pi^2 * D^5). (rho=980 kg/m³)
        """
        rho = 980.0 
        # K-Wert (Hydraulische Impedanz)
        k_value = (8 * self.lambda_factor * self.length * rho) / (np.pi**2 * self.diameter**5)
        return k_value

class Valve:
    """Regelventil, berechnet den Widerstand K aus dem eingestellten kV-Wert."""
    def __init__(self, kv_value):
        self.kv_current = kv_value
        
    def get_resistance_k(self):
        """Berechnet K für dP = K * Q^2 (in SI Einheiten) basierend auf kv_current."""
        kv_current = self.kv_current
        
        if kv_current < 1e-6: 
            return 1e12 # Ventil praktisch zu (sehr hoher Widerstand)
            
        # K_si = 100000 Pa / (kv_current m³/h / 3600 s/h)^2
        k_si = 100000.0 / ((kv_current / 3600.0)**2)
        return k_si

# --- 2. Netzwerkdefinition und Berechnung ---

class ComplexNetworkSimulation:
    def __init__(self, config_data):
        # Pumpenförderhöhe aus Konfigurationsdatei
        pump_head_mws = config_data.get("pump_head_mWS", 6.5)
        self.pump_pressure = pump_head_mws * 10000.0 # mWS * 10.000 Pa/mWS
        
        # Daten aus Benutzerangaben (kv_max, Q_nominal (l/h), Außendurchmesser (mm), Name)
        self.branches_data = [
            (0, 0, 28, "Strang 1 (V: 0)"),      
            (0, 0, 28, "Strang 2 (V: 0)"),      
            (100.0, 92, 15, "Strang 3 (Ohne SRV)"),     
            (0.720, 325, 22, "Strang 4 (V: 0.72)"),      
            (0.840, 359, 22, "Strang 5 (V: 0.84)"),      
            (0.970, 359, 22, "Strang 6 (V: 0.97)"),      
            (100.0, 92, 15, "Strang 7 (Ohne SRV)"),     
            (1.100, 390, 22, "Strang 8 (V: 1.10)"),      
            (1.100, 392, 22, "Strang 9 (V: 1.10)"), 
            (1.100, 336, 22, "Strang 11 (V: 1.10)"),      
            (0.970, 363, 22, "Strang 10 (V: 0.97)"), 
            (1.100, 336, 22, "Strang 11 (V: 1.10)"),   
        ]
        
        # Main Segmente (Von Pumpe bis zum nächsten Abzweig-Knoten)
        self.main_pipes = [
            Pipe("P_M1", length_m=2, od_mm=42),       
            Pipe("P_M2", length_m=5, od_mm=42),       
            Pipe("P_M3_Long", length_m=20, od_mm=42), 
            Pipe("P_M4", length_m=8, od_mm=42),       
            Pipe("P_M5", length_m=5, od_mm=42),       
            Pipe("P_M6", length_m=15, od_mm=42),      
            Pipe("P_M7", length_m=2, od_mm=42),       
            Pipe("P_M8", length_m=15, od_mm=35),      
            Pipe("P_M9", length_m=10, od_mm=35),      
            Pipe("P_M10", length_m=5, od_mm=28),      
            Pipe("P_M11", length_m=2, od_mm=22),      
        ]
        
        self.valve_settings = config_data['valve_settings']
        self.valves = []
        self.pipe_branches = []
        self.K_load = [] 
        
        # --- KALIBRIERUNG: Bestimmung des Lastwiderstands (K_load) ---
        # Stellt sicher, dass bei kv_max die nominalen Flüsse erreicht werden.
        
        Q_nom_lh = np.array([b[1] for b in self.branches_data])
        Q_nom_si = Q_nom_lh / (3600.0 * 1000.0) # m³/s
        N = len(self.branches_data)

        print("Starte Kalibrierung des Lastwiderstands (K_load)...")
        
        for i in range(N):
            Q_i = Q_nom_si[i]
            kv_max = self.branches_data[i][0]
            
            # 1. Hauptleitungs-Druckverlust bis Knoten i berechnen (mit nominalen Gesamtflüssen)
            dP_main_sum = 0
            for k in range(i + 1):
                # Fluss im Hauptstrang-Segment k: Summe aller nominalen Ströme (Q_nom_si[k:]) 
                Q_main_k = np.sum(Q_nom_si[k:]) 
                
                if k < len(self.main_pipes):
                    K_main_k = self.main_pipes[k].get_resistance_k()
                    dP_main_sum += K_main_k * Q_main_k**2
                    
            # 2. Erforderlicher Druckverlust im Abzweig i
            dP_branch_i_required = self.pump_pressure - dP_main_sum
            
            # Initialisiere Abzweigrohr (angenommene Länge 5m)
            self.pipe_branches.append(Pipe(f"P_B_{i+1}", length_m=5, od_mm=self.branches_data[i][2]))
            
            # Abzweig-Widerstände ohne Last
            K_pipe_branch = self.pipe_branches[i].get_resistance_k()
            K_valve_max_open = Valve(kv_max).get_resistance_k() 
            
            if dP_branch_i_required <= 0 or Q_i <= 1e-6:
                 # Kann nicht kalibriert werden, da Druck nicht ausreicht oder Q=0
                 K_load_calculated = 1e12
            else:
                 # Erforderlicher Gesamtwiderstand des Abzweigs i
                 K_total_required = dP_branch_i_required / Q_i**2
                 
                 # K_Load = K_required - K_valve_max - K_pipe
                 K_load_calculated = K_total_required - K_valve_max_open - K_pipe_branch

            # K_Load kann nicht negativ sein
            self.K_load.append(max(0, K_load_calculated))
            print(f"Strang {i+1}: Q_nom={Q_nom_lh[i]:.2f} l/h, dP_req={dP_branch_i_required:.0f} Pa, K_load={self.K_load[-1]:.0f} SI")
        
        print("Kalibrierung abgeschlossen. Starte Simulation.")

    def calculate_flows(self):
        """
        Löst das hydraulische Netzwerk für die aktuellen Ventilstellungen 
        (aus der Konfiguration geladen).
        """
        
        N = len(self.branches_data)
        
        # Initialisiere Ventile mit den Werten aus config.json
        for i in range(N):
            kv_setting = self.valve_settings[i]['kv_setting']
            self.valves.append(Valve(kv_setting))

        
        def equations(Q):
            """Q ist der Vektor der 12 unbekannten Abzweigströme Q1...Q12 in m3/s."""
            
            eq = np.zeros(N)
            
            # Gesamt-Rohrwiderstände der Abzweige berechnen (mit aktueller Ventileinstellung)
            K_branches_total = np.zeros(N)
            for i in range(N):
                K_valve = self.valves[i].get_resistance_k()
                K_pipe_branch = self.pipe_branches[i].get_resistance_k()
                K_branches_total[i] = K_valve + K_pipe_branch + self.K_load[i]

            # Maschengleichungen aufstellen (12 Gleichungen)
            for i in range(N):
                # i ist der Index des aktuellen Abzweigs (0 bis 11)
                
                # 1. Druckverlust Hauptleitung bis Knoten i
                dP_main_sum = 0
                for k in range(i + 1):
                    # Fluss im Hauptstrang-Segment k: Summe aller nachfolgenden Ströme (Q[k:])
                    Q_main_k = np.sum(Q[k:]) 
                    
                    if k < len(self.main_pipes):
                        K_main_k = self.main_pipes[k].get_resistance_k()
                        dP_main_sum += K_main_k * Q_main_k**2
                        
                # 2. Druckverlust Abzweig i
                dP_branch_i = K_branches_total[i] * Q[i]**2
                
                # Maschenregel: P_Pumpe - dP_Hauptleitung - dP_Abzweig = 0
                eq[i] = self.pump_pressure - dP_main_sum - dP_branch_i
                
            return eq

        # Startwerte raten (Nominalflüsse)
        q_nom_lh = [b[1] for b in self.branches_data]
        initial_guess = np.array(q_nom_lh) / (3600.0 * 1000.0) 
        
        # Lösen des nicht-linearen Gleichungssystems
        solution, info, ier, mesg = fsolve(equations, initial_guess, full_output=True)
        
        if ier != 1:
            print(f"WARNUNG: fsolve konvergierte nicht: {mesg}")
        
        # Konvertieren in l/h für Lesbarkeit
        results_lh = solution * 3600 * 1000
        
        # Filtern von negativen Strömen (physikalisch nicht möglich)
        results_lh[results_lh < 0] = 0 
        
        return results_lh 

def load_config(filepath):
    """Lädt die Konfiguration aus einer JSON-Datei."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FEHLER: Konfigurationsdatei '{filepath}' nicht gefunden.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"FEHLER: '{filepath}' ist keine gültige JSON-Datei.")
        sys.exit(1)

def write_results_to_csv(filepath, branch_data, flows_lh, config_data, valve_settings):
    """Schreibt die Ergebnisse in eine CSV-Datei."""
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            
            # Header schreiben
            writer.writerow(["Parameter: Volumenstrom-Simulation"])
            writer.writerow([f"Pumpenfoerderhoehe (mWS): {config_data['pump_head_mWS']}"])
            writer.writerow([])
            
            header = [
                "Strang ID", 
                "Strang Name", 
                "Q Nominal (l/h)", 
                "SRV kV max (m3/h)", 
                "SRV Einstellung (kV)",
                "Volumenstrom (l/h) ERREICHT"
            ]
            writer.writerow(header)

            # Datenzeilen schreiben
            total_q_nominal = 0.0
            for i, (kv_max, q_nom_lh, od_mm, name) in enumerate(branch_data):
                total_q_nominal += q_nom_lh
                kv_setting = valve_settings[i]['kv_setting']
                
                row = [
                    f"Strang {i+1}",
                    name.split('(')[0].strip(), # Nur den Namen ohne Klammern
                    f"{q_nom_lh:.2f}",
                    f"{kv_max:.2f}",
                    f"{kv_setting:.4f}",
                    f"{flows_lh[i]:.2f}"
                ]
                writer.writerow(row)
                
            # Gesamtvolumenstrom
            writer.writerow([])
            writer.writerow(["GESAMTVOLUMENSTROM NOMINAL:", "", f"{total_q_nominal:.2f}", "", "", ""])
            writer.writerow(["GESAMTVOLUMENSTROM ERREICHT:", "", "", "", "", f"{np.sum(flows_lh):.2f}"])


        print(f"\nERFOLG: Die simulierten Volumenströme wurden in die Datei '{filepath}' geschrieben.")

    except Exception as e:
        print(f"FEHLER beim Schreiben der CSV-Datei: {e}")

# --- Hauptprogramm ---

if __name__ == "__main__":
    # 1. Konfiguration laden
    config_file = 'config.json'
    config = load_config(config_file)

    # 2. Simulation initialisieren und Lastwiderstände kalibrieren
    sim = ComplexNetworkSimulation(config)
    
    # 3. Flüsse berechnen (Simulation der eingestellten kv-Werte)
    flows = sim.calculate_flows()

    # 4. Ergebnisse in CSV speichern
    csv_file = 'ergebnisse.csv'
    write_results_to_csv(csv_file, sim.branches_data, flows, config, sim.valve_settings)
    
    print("\nSimulation abgeschlossen.")
    print("Bitte die Datei 'ergebnisse.csv' öffnen, um die Resultate der aktuellen kv-Einstellungen zu sehen.")