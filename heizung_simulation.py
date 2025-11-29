import json
import math
import csv
import matplotlib.pyplot as plt
import copy
import os

# --- PHYSIK & HYDRAULIK KLASSEN ---

class Fluid:
    def __init__(self, density=983.2, viscosity=0.00047):
        self.rho = density  # kg/m^3 (Wasser bei ~60°C)
        self.mu = viscosity # Pa*s

class Pipe:
    def __init__(self, dimension_str, length_m, surcharge_factor=0.0):
        self.length = length_m
        self.name = dimension_str
        self.surcharge_factor = surcharge_factor 
        self.inner_diameter_mm = self._parse_dim(dimension_str)
        self.inner_diameter_m = self.inner_diameter_mm / 1000.0
        self.roughness = 0.0015e-3 

    def _parse_dim(self, dim_str):
        try:
            clean = dim_str.upper().replace("CU", "").replace(" ", "")
            parts = clean.split("X")
            outer = float(parts[0])
            wall = float(parts[1]) if len(parts) > 1 else 1.0
            return outer - 2 * wall
        except:
            return 20.0 

    def calculate_pressure_drop(self, flow_lh, fluid):
        if flow_lh <= 0: return 0
        flow_m3s = flow_lh / 3600000.0
        area = math.pi * (self.inner_diameter_m / 2)**2
        velocity = flow_m3s / area
        
        re = (fluid.rho * velocity * self.inner_diameter_m) / fluid.mu
        
        if re < 2300:
            lambda_f = 64 / re if re > 0 else 0
        else:
            if self.roughness == 0:
                lambda_f = 0.3164 * re**(-0.25)
            else:
                t1 = self.roughness / (3.7 * self.inner_diameter_m)
                t2 = 5.74 / (re**0.9)
                lambda_f = 0.25 / (math.log10(t1 + t2)**2)

        dp_pa_pipe = lambda_f * (self.length / self.inner_diameter_m) * (fluid.rho / 2) * velocity**2
        dp_pa_total = dp_pa_pipe * (1.0 + self.surcharge_factor)
        return dp_pa_total / 100000.0 

class Consumer:
    def __init__(self, data):
        self.name = data['name']
        self.design_power = data['design_power_w']
        self.design_flow = data['design_flow_lh']
        self.current_kv = data['valve_kv']
        self.connection_pipe_str = data.get('connection_pipe', 'CU15x1.0')
        self.is_direct = data.get('is_direct', False)
        self.design_delta_t = self.design_power / (self.design_flow * 1.16) if self.design_flow > 0 else 15

    def set_kv(self, new_kv):
        self.current_kv = new_kv

    def calculate_flow(self, available_pressure_bar):
        if available_pressure_bar <= 0: return 0
        if self.current_kv:
            q_m3h = self.current_kv * math.sqrt(available_pressure_bar)
            return q_m3h * 1000.0
        else:
            design_p = 0.1 
            k_factor = self.design_flow / math.sqrt(design_p) 
            return k_factor * math.sqrt(available_pressure_bar)

    def calculate_power(self, actual_flow_lh):
        if self.design_flow == 0: return 0
        ratio = actual_flow_lh / self.design_flow
        return self.design_power * (ratio ** 1.0) 

class NetworkNode:
    def __init__(self, pipe_segment_data, surcharge_factor=0.0, parent=None):
        self.pipe = Pipe(
            pipe_segment_data['pipe']['dim'], 
            pipe_segment_data['pipe']['length'],
            surcharge_factor
        )
        self.consumer = Consumer(pipe_segment_data['consumer'])
        self.next_node = None
        self.parent = parent
        self.sim_pressure_before = 0
        self.sim_pressure_after = 0
        self.sim_flow_consumer = 0
        self.sim_flow_pipe = 0 

class HeatingCircuit:
    def __init__(self, data, fluid, global_surcharge=0.0):
        self.name = data['name']
        self.pump_head_m = data['pump_head_m']
        self.pump_pressure_bar = self.pump_head_m * 0.0981
        self.fluid = fluid
        self.nodes = []
        
        prev_node = None
        for segment in data['topology']:
            node = NetworkNode(segment, surcharge_factor=global_surcharge, parent=prev_node)
            if prev_node:
                prev_node.next_node = node
            self.nodes.append(node)
            prev_node = node

    def solve(self):
        for iteration in range(50): 
            # 1. Rückwärts (Massenstrom akkumulieren)
            for i in range(len(self.nodes) - 1, -1, -1):
                node = self.nodes[i]
                node_flow_out = node.next_node.sim_flow_pipe if node.next_node else 0
                consumer_flow = node.sim_flow_consumer if iteration > 0 else node.consumer.design_flow
                node.sim_flow_pipe = node_flow_out + consumer_flow

            # 2. Vorwärts (Druck berechnen)
            p_cursor = self.pump_pressure_bar
            for node in self.nodes:
                node.sim_pressure_before = p_cursor
                dp = node.pipe.calculate_pressure_drop(node.sim_flow_pipe, self.fluid)
                p_after = p_cursor - dp
                if p_after < 0: p_after = 0
                node.sim_pressure_after = p_after
                
                new_consumer_flow = node.consumer.calculate_flow(p_after)
                
                node.sim_flow_consumer = (node.sim_flow_consumer + new_consumer_flow) / 2 if iteration > 0 else new_consumer_flow
                p_cursor = p_after

# --- VISUALIZATION FUNCTION ---

def draw_topology(config, filename):
    """
    Zeichnet den schematischen Aufbau der Heizkreise.
    """
    # Maximale Anzahl Segmente ermitteln für Bildbreite
    max_segments = 0
    for c in config['circuits']:
        max_segments = max(max_segments, len(c['topology']))
    
    # Dynamische Bildgröße
    # Breite pro Segment ca. 1.5 inch, mindestens 10 inch
    width = max(12, max_segments * 1.5)
    # Höhe pro Circuit ca 4 inch
    height = len(config['circuits']) * 4 + 2
    
    fig, ax = plt.subplots(figsize=(width, height))
    
    # Startpunkt Y (von oben nach unten zeichnen)
    y_start = len(config['circuits']) * 4
    
    for i, circuit in enumerate(config['circuits']):
        y = y_start - (i * 4)
        x = 0
        
        # 1. Pumpe / Startknoten zeichnen
        ax.plot(x, y, 'ko', markersize=12, zorder=5) # Pumpen-Symbol
        # Pumpen Info
        ax.text(x, y+0.4, f"Pumpe\n{circuit['pump_head_m']}m", ha='center', va='bottom', fontweight='bold', fontsize=10)
        # Kreis Name
        ax.text(x-0.8, y, circuit['name'], ha='right', va='center', fontweight='bold', fontsize=12)
        
        # 2. Segmente durchlaufen
        for seg in circuit['topology']:
            # Schematische Länge (fixer Abstand für Lesbarkeit)
            dx = 2.0 
            next_x = x + dx
            
            # --- Hauptrohr (Horizontal) ---
            ax.plot([x, next_x], [y, y], 'k-', lw=2, zorder=1)
            
            # Rohr-Beschriftung (Mitte)
            mid_x = (x + next_x) / 2
            p_text = f"{seg['pipe']['dim']}\nL={seg['pipe']['length']}m"
            ax.text(mid_x, y+0.15, p_text, ha='center', va='bottom', fontsize=8, color='blue', fontweight='bold')
            
            # --- Abzweig zum Verbraucher (Vertikal nach unten) ---
            branch_y = y - 1.0
            ax.plot([next_x, next_x], [y, branch_y], 'k--', lw=1, zorder=1)
            
            # Verbraucher-Knoten
            ax.plot(next_x, branch_y, 's', color='red', markersize=8, zorder=5)
            
            # Verbraucher-Info
            c = seg['consumer']
            kv_txt = f"kV {c['valve_kv']}" if c['valve_kv'] else "Direkt"
            
            # Text vertikal rotiert für Platzersparnis
            c_label = f"{c['name']}\n{c['design_power_w']}W\n{kv_txt}"
            ax.text(next_x, branch_y - 0.2, c_label, ha='center', va='top', fontsize=9, rotation=90)
            
            # Weiter zum nächsten Segment
            x = next_x
            
    # Achsen ausblenden, aber Limits setzen, damit Text nicht abgeschnitten wird
    ax.axis('off')
    ax.set_ylim(0, y_start + 3)
    ax.set_xlim(-5, x + 14) # Platz links für Namen, rechts für Puffer
    
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"[INFO] Topologie-Diagramm gespeichert: {filename}")

# --- LOGIC ---

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def apply_scenarios(config, scenario_data):
    sim_config = copy.deepcopy(config)
    print(f"\n[INFO] Wende Szenario an: {scenario_data.get('scenario_name', 'Unbekannt')}")
    
    if 'settings_override' in scenario_data:
        for key, val in scenario_data['settings_override'].items():
            sim_config['global_settings'][key] = val
            print(f"  -> Global Setting überschrieben: '{key}' = {val}")

    for mod in scenario_data.get('modifications', []):
        m_type = mod.get('type')
        
        if m_type == 'merge_circuits':
            mode = mod.get('mode', 'parallel') 
            new_head = mod['source_head_m']
            
            if mode == 'serial_prepend':
                # SERIELL: HK2 wird VOR HK1 gehängt
                source_name = mod.get('source_circuit')
                target_name = mod.get('target_circuit')
                
                source_c = next((c for c in sim_config['circuits'] if c['name'] == source_name), None)
                target_c = next((c for c in sim_config['circuits'] if c['name'] == target_name), None)
                
                if source_c and target_c:
                    print(f"  -> Umbau SERIELL: {source_name} wird VOR {target_name} gesetzt.")
                    # Topologie zusammenführen: [Source Nodes] + [Target Nodes]
                    combined_topology = source_c['topology'] + target_c['topology']
                    target_c['topology'] = combined_topology
                    target_c['pump_head_m'] = new_head
                    
                    if mod.get('rename_to'):
                        target_c['name'] = mod['rename_to']
                    
                    # Entferne den alten Source Circuit aus der Liste
                    sim_config['circuits'] = [c for c in sim_config['circuits'] if c['name'] != source_name]
                    print(f"     {source_name} entfernt, nun Teil von {target_c['name']}.")
                else:
                    print(f"  ERROR: Konnte Circuits für seriellen Merge nicht finden ({source_name}, {target_name})")

            else:
                # PARALLEL
                print(f"  -> Umbau PARALLEL: Alle Kreise werden auf {new_head}m gesetzt.")
                for c in sim_config['circuits']:
                    c['pump_head_m'] = new_head
                    if 'name' in c and mod.get('rename_to'):
                         if c['name'] == mod.get('target_circuit'):
                             c['name'] = mod['rename_to']

        elif m_type == 'set_valve_kv':
            changes = mod.get('changes', {})
            count = 0
            for c in sim_config['circuits']:
                for seg in c['topology']:
                    c_name = seg['consumer']['name']
                    if c_name in changes:
                        seg['consumer']['valve_kv'] = changes[c_name]
                        count += 1
            print(f"  -> Ventile: {count} kV-Werte angepasst.")
            
    return sim_config

def run_simulation(config, label="Unbekannt"):
    fluid = Fluid(config['global_settings']['fluid_density'], config['global_settings']['fluid_viscosity'])
    pipe_surcharge = config['global_settings'].get('pipe_surcharge_factor', 0.0)
    
    print(f"\n--- Starte Berechnung: {label} ---")
    print(f"  > Rohrzuschlag (Fittings): {pipe_surcharge}")
    for c in config['circuits']:
        print(f"  > Kreis '{c['name']}': Pumpe = {c['pump_head_m']} m ({len(c['topology'])} Stränge)")
    
    results = []
    for c_data in config['circuits']:
        circuit = HeatingCircuit(c_data, fluid, global_surcharge=pipe_surcharge)
        circuit.solve()
        
        for node in circuit.nodes:
            res = {
                'Consumer': node.consumer.name,
                'Flow_lh': round(node.sim_flow_consumer, 1),
                'Power_W': round(node.consumer.calculate_power(node.sim_flow_consumer), 1),
                'kV': node.consumer.current_kv if node.consumer.current_kv else "N/A",
                'Pressure_Bar': round(node.sim_pressure_after, 3)
            }
            results.append(res)
    return results

def export_results(original, simulated, filename_csv, filename_png):
    header = ['Strangname', 'Urspr. Q [l/h]', 'Sim. Q [l/h]', 'Urspr. P [W]', 'Sim. P [W]', 'Urspr. kV', 'Sim. kV']
    sim_map = {r['Consumer']: r for r in simulated}
    
    with open(filename_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        names = [r['Consumer'] for r in original]
        q_orig = []
        q_sim = []
        
        for row_o in original:
            name = row_o['Consumer']
            row_s = sim_map.get(name)
            if row_s:
                line = [name, row_o['Flow_lh'], row_s['Flow_lh'], row_o['Power_W'], row_s['Power_W'], row_o['kV'], row_s['kV']]
                writer.writerow(line)
                q_orig.append(row_o['Flow_lh'])
                q_sim.append(row_s['Flow_lh'])
            else:
                pass 

    print(f"\n[INFO] Export fertig: {filename_csv}")

    plt.figure(figsize=(14, 7)) 
    x = range(len(q_orig))
    width = 0.35
    plt.bar([i - width/2 for i in x], q_orig, width, label='Ursprüngliche Ausführungsplanung', color='#A0C4FF')
    plt.bar([i + width/2 for i in x], q_sim, width, label='Ein Heizkreis, Ventile optimiert', color='#FFADAD')
    plt.xlabel('Verbraucher')
    plt.ylabel('Massenstrom [l/h]')
    plt.title('Massenstromvergleich: Ursprüngliche Planung vs. Tatsächliche Anlage mit optimierten Ventileinstellungen')
    plt.xticks(x, names, rotation=45, ha="right", fontsize=9)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename_png)
    print(f"[INFO] Diagramm gespeichert: {filename_png}")

if __name__ == "__main__":
    if not os.path.exists('heizung_config.json'):
        print("Fehler: heizung_config.json fehlt.")
        exit()
    config_base = load_json('heizung_config.json')
    
    # Visualisierung Original
    draw_topology(config_base, 'topology_original.png')
    
    results_base = run_simulation(config_base, label="BASIS")

    if os.path.exists('scenarios.json'):
        scenario_data = load_json('scenarios.json')
        config_sim = apply_scenarios(config_base, scenario_data)
        
        # Visualisierung Simulation (neu!)
        draw_topology(config_sim, 'topology_simulated.png')
        
        results_sim = run_simulation(config_sim, label="SIMULATION")
        export_results(results_base, results_sim, 'heizung_vergleich.csv', 'heizung_diagramm.png')