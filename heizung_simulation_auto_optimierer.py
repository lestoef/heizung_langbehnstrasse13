import json
import math
import csv
import matplotlib.pyplot as plt
import copy
import os

# --- PHYSIK & HYDRAULIK KLASSEN ---

class Fluid:
    def __init__(self, density=983.2, viscosity=0.00047):
        self.rho = density  # kg/m^3
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
            # Fixer Widerstand (Direktanschluss)
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
            # 1. Rückwärts
            for i in range(len(self.nodes) - 1, -1, -1):
                node = self.nodes[i]
                node_flow_out = node.next_node.sim_flow_pipe if node.next_node else 0
                consumer_flow = node.sim_flow_consumer if iteration > 0 else node.consumer.design_flow
                node.sim_flow_pipe = node_flow_out + consumer_flow

            # 2. Vorwärts
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

# --- LOGIC & OPTIMIZATION ---

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
                source_name = mod.get('source_circuit')
                target_name = mod.get('target_circuit')
                
                source_c = next((c for c in sim_config['circuits'] if c['name'] == source_name), None)
                target_c = next((c for c in sim_config['circuits'] if c['name'] == target_name), None)
                
                if source_c and target_c:
                    print(f"  -> Umbau SERIELL: {source_name} wird VOR {target_name} gesetzt.")
                    combined_topology = source_c['topology'] + target_c['topology']
                    target_c['topology'] = combined_topology
                    target_c['pump_head_m'] = new_head
                    if mod.get('rename_to'):
                        target_c['name'] = mod['rename_to']
                    sim_config['circuits'] = [c for c in sim_config['circuits'] if c['name'] != source_name]
                else:
                    print(f"  ERROR: Circuits nicht gefunden ({source_name}, {target_name})")

            else: # Parallel
                print(f"  -> Umbau PARALLEL: Alle Kreise auf {new_head}m.")
                for c in sim_config['circuits']:
                    c['pump_head_m'] = new_head
                    if 'name' in c and mod.get('rename_to') and c['name'] == mod.get('target_circuit'):
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

def run_simulation(config, label="Unbekannt", silent=False):
    fluid = Fluid(config['global_settings']['fluid_density'], config['global_settings']['fluid_viscosity'])
    pipe_surcharge = config['global_settings'].get('pipe_surcharge_factor', 0.0)
    
    if not silent:
        print(f"\n--- Starte Berechnung: {label} ---")
        print(f"  > Rohrzuschlag: {pipe_surcharge}")
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

def optimize_kv_values(config, target_results):
    print("\n--- STARTE AUTOMATISCHEN ABGLEICH (Adaptiv & Robust) ---")
    
    targets = {r['Consumer']: r['Flow_lh'] for r in target_results}
    sim_config = copy.deepcopy(config)
    
    best_config = copy.deepcopy(sim_config)
    min_max_deviation = 9999.0
    best_iteration = -1
    
    # Adaptive Parameter
    iterations = 80
    damping = 0.2
    damping_decay = 0.98 # Dämpfung wird mit der Zeit noch kleiner
    
    max_kv_limit = 35.0 # "Voll offen" Limit
    saturated_nodes = set()

    for i in range(iterations):
        results = run_simulation(sim_config, silent=True)
        res_map = {r['Consumer']: r for r in results}
        
        current_max_deviation = 0.0
        worst_node = ""
        
        # 1. Analyse der Abweichung
        for c in sim_config['circuits']:
            for seg in c['topology']:
                name = seg['consumer']['name']
                if seg['consumer']['valve_kv'] is None: continue # Direktanschluss ignorieren
                
                target = targets.get(name, 0)
                actual = res_map[name]['Flow_lh']
                
                if target > 1:
                    dev = abs(1.0 - (actual / target))
                    if dev > current_max_deviation:
                        current_max_deviation = dev
                        worst_node = name
        
        # Check ob das der beste Lauf war
        if current_max_deviation < min_max_deviation:
            min_max_deviation = current_max_deviation
            best_config = copy.deepcopy(sim_config)
            best_iteration = i
        
        # Log Output alle 10 Schritte
        if i % 10 == 0:
            print(f"  > It {i:02d}: Abw. {current_max_deviation*100:5.1f}% | Worst: {worst_node} | Dämpfung: {damping:.3f}")

        # Konvergenz-Kriterium
        if current_max_deviation < 0.02: # 2% Ziel
            break
            
        # Wenn wir uns verschlechtern, Dämpfung reduzieren (Notbremse)
        if current_max_deviation > min_max_deviation * 1.5:
            damping *= 0.8
            # Reset auf beste Config, wenn wir zu weit wegdriften
            if current_max_deviation > 0.5: # >50% Abweichung
                 sim_config = copy.deepcopy(best_config)
        
        # 2. Update der kV Werte
        for c in sim_config['circuits']:
            for seg in c['topology']:
                cons = seg['consumer']
                name = cons['name']
                if cons['valve_kv'] is None: continue
                
                target = targets.get(name, 0)
                actual = res_map[name]['Flow_lh']
                
                if target < 1 or actual < 0.1: continue
                
                # Wenn wir am Limit sind (kV > 30) UND zu wenig Fluss haben -> Aufgeben für diesen Knoten
                # Das verhindert, dass der Algorithmus kV auf 1000 setzt und alles andere ruiniert
                if cons['valve_kv'] >= max_kv_limit and actual < target:
                    saturated_nodes.add(name)
                    continue 

                ratio = target / actual
                
                # Extreme Korrekturen abfangen (Soft Clamping)
                ratio = max(0.9, min(ratio, 1.1))
                
                # Update
                new_kv = cons['valve_kv'] * (ratio ** damping)
                new_kv = max(0.01, min(new_kv, max_kv_limit))
                cons['valve_kv'] = new_kv
        
        # Dämpfung leicht reduzieren für Feinjustierung gegen Ende
        damping *= damping_decay

    print(f"  > Ende bei It {iterations}. Bestes Ergebnis: {min_max_deviation*100:.1f}% (bei It {best_iteration})")
    
    if min_max_deviation > 0.10: # Warnung bei >10% Abweichung
        print("\n[WARNUNG] Der hydraulische Abgleich konnte nicht vollständig erreicht werden.")
        print("Mögliche Ursache: Die Pumpe (4m) ist zu schwach für die serielle Schaltung.")
        if saturated_nodes:
            print("Folgende Stränge sind voll geöffnet und dennoch unterversorgt:")
            for n in list(saturated_nodes)[:3]: print(f"  - {n}")
            if len(saturated_nodes) > 3: print("  - ...")

    # Ergebnis
    print("\n[RESULTAT] Optimierte Ventil-Einstellungen für scenarios.json:")
    print("-" * 50)
    print('"changes": {')
    kv_list = []
    for c in best_config['circuits']:
        for seg in c['topology']:
            cons = seg['consumer']
            if cons['valve_kv'] is not None:
                kv_list.append(f'  "{cons["name"]}": {round(cons["valve_kv"], 2)}')
    print(",\n".join(kv_list))
    print("}")
    print("-" * 50)
    
    return best_config

def draw_topology(config, filename):
    max_segments = 0
    for c in config['circuits']:
        max_segments = max(max_segments, len(c['topology']))
    width = max(12, max_segments * 1.5)
    height = len(config['circuits']) * 4 + 2
    fig, ax = plt.subplots(figsize=(width, height))
    y_start = len(config['circuits']) * 4
    for i, circuit in enumerate(config['circuits']):
        y = y_start - (i * 4)
        x = 0
        ax.plot(x, y, 'ko', markersize=12)
        ax.text(x, y+0.4, f"Pumpe\n{circuit['pump_head_m']}m", ha='center', va='bottom', fontweight='bold', fontsize=10)
        ax.text(x-0.8, y, circuit['name'], ha='right', va='center', fontweight='bold', fontsize=12)
        for seg in circuit['topology']:
            next_x = x + 2.0
            ax.plot([x, next_x], [y, y], 'k-', lw=2)
            mid_x = (x + next_x) / 2
            ax.text(mid_x, y+0.15, f"{seg['pipe']['dim']}\n{seg['pipe']['length']}m", ha='center', va='bottom', fontsize=8, color='blue')
            branch_y = y - 1.0
            ax.plot([next_x, next_x], [y, branch_y], 'k--', lw=1)
            ax.plot(next_x, branch_y, 's', color='red', markersize=8)
            c = seg['consumer']
            kv_val = f"{c['valve_kv']:.2f}" if c['valve_kv'] else "Direkt"
            ax.text(next_x, branch_y - 0.2, f"{c['name']}\n{kv_val}", ha='center', va='top', fontsize=9, rotation=90)
            x = next_x
    ax.axis('off')
    ax.set_ylim(0, y_start + 3)
    ax.set_xlim(-3, x + 2)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"[INFO] Topologie-Diagramm gespeichert: {filename}")

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
    print(f"\n[INFO] Export fertig: {filename_csv}")
    plt.figure(figsize=(14, 7))
    x = range(len(q_orig))
    width = 0.35
    plt.bar([i - width/2 for i in x], q_orig, width, label='Ursprünglich', color='#A0C4FF')
    plt.bar([i + width/2 for i in x], q_sim, width, label='Simuliert (Optimiert)', color='#FFADAD')
    plt.xlabel('Verbraucher')
    plt.ylabel('Massenstrom [l/h]')
    plt.title('Ergebnis nach Auto-Balancing')
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
    
    # 1. Basis-Lauf
    results_base = run_simulation(config_base, label="BASIS")

    if os.path.exists('scenarios.json'):
        scenario_data = load_json('scenarios.json')
        
        # 2. Szenario anwenden (Startwerte)
        config_sim = apply_scenarios(config_base, scenario_data)
        
        # 3. OPTIMIERUNG LAUFEN LASSEN
        config_optimized = optimize_kv_values(config_sim, results_base)
        
        # 4. Finaler Lauf mit optimierten Werten
        results_final = run_simulation(config_optimized, label="SIMULATION (Optimiert)")
        
        # Visualisierung der optimierten Topologie
        draw_topology(config_optimized, 'topology_optimized.png')
        
        export_results(results_base, results_final, 'heizung_vergleich.csv', 'heizung_diagramm.png')