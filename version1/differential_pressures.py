import math

def calculate_available_pressure(
    pump_pressure_bar: float,
    segments: list,
    temp_spread_k: float = 15.0,
    fittings_surcharge: float = 0.4
) -> dict:
    """
    Berechnet den verfügbaren Differenzdruck am Ende eines Rohrleitungsstrangs.
    
    Physik: Verwendet die Darcy-Weisbach-Gleichung für Rohrreibung.
    
    Parameter:
    ----------
    pump_pressure_bar : float
        Der Förderdruck der Pumpe in bar (z.B. 0.4 bar).
    segments : list
        Eine Liste von Dictionaries. Jedes Dict repräsentiert ein Teilstück 
        auf dem Weg von der Pumpe zum Zielpunkt.
        Format: {'length_m': float, 'diameter_mm': float, 'power_kw': float}
        
        WICHTIG: 'power_kw' ist die Leistung, die DURCH dieses Rohr fließt 
        (also die Summe aller dahinterliegenden Heizkörper).
    temp_spread_k : float, optional (Standard: 15.0)
        Temperaturspreizung Vorlauf/Rücklauf in Kelvin.
    fittings_surcharge : float, optional (Standard: 0.4 entspricht 40%)
        Pauschaler Zuschlag für Einzelwiderstände (Bögen, T-Stücke, Ventile).
        
    Rückgabe:
    ---------
    dict
        Ergebnis mit Restdruck, Gesamterlust und Details pro Teilstrecke.
    """
    
    # --- Konstanten für Wasser bei ca. 60°C ---
    DENSITY = 983.2       # kg/m³ (Dichte)
    KIN_VISCOSITY = 0.47e-6 # m²/s (Kinematische Viskosität)
    SPEC_HEAT = 4185.0    # J/(kg*K) (Spezifische Wärmekapazität)
    ROUGHNESS = 0.045e-3  # m (Rauheit für Stahlrohr, bei Kupfer/Kunststoff eher 0.007e-3)

    total_pressure_loss_pa = 0.0
    segment_details = []

    print(f"{'Nr':<3} | {'Länge (m)':<10} | {'DN (mm)':<8} | {'Last (kW)':<10} | {'v (m/s)':<8} | {'Druckverlust (mbar)':<20}")
    print("-" * 85)

    for i, seg in enumerate(segments):
        length = seg['length_m']
        diameter_mm = seg['diameter_mm']
        power_kw = seg['power_kw']

        if power_kw <= 0:
            continue

        # 1. Volumenstrom berechnen (Q = m * c * dT)
        # power_kw * 1000 = Watt
        mass_flow_kg_s = (power_kw * 1000) / (SPEC_HEAT * temp_spread_k)
        vol_flow_m3_s = mass_flow_kg_s / DENSITY

        # 2. Strömungsgeschwindigkeit (v = V_punkt / A)
        diameter_m = diameter_mm / 1000.0
        area_m2 = math.pi * (diameter_m / 2)**2
        velocity_m_s = vol_flow_m3_s / area_m2

        # 3. Reynolds-Zahl (Re = v * d / nu)
        reynolds = (velocity_m_s * diameter_m) / KIN_VISCOSITY

        # 4. Rohrreibungszahl Lambda (nach Colebrook-White Näherung oder Blasius)
        # Für turbulente Strömungen in Heizungsrohren (Swamee-Jain Näherung für vollturbulent)
        if reynolds < 2300:
            # Laminar
            lam = 64 / reynolds
        else:
            # Turbulent (Haaland Gleichung - explizite Näherung für Colebrook)
            epsilon = ROUGHNESS / diameter_m
            lam = (-1.8 * math.log10((epsilon / 3.7)**1.11 + 6.9 / reynolds)) ** -2

        # 5. Druckverlust Gerade Rohrleitung (Darcy-Weisbach)
        # dp = lambda * (L/d) * (rho/2) * v²
        pressure_loss_pipe_pa = lam * (length / diameter_m) * (DENSITY / 2) * velocity_m_s**2

        # 6. Zuschlag für Formstücke (Z-Werte pauschal)
        pressure_loss_fittings_pa = pressure_loss_pipe_pa * fittings_surcharge

        # Gesamtverlust dieses Segments
        segment_loss_pa = pressure_loss_pipe_pa + pressure_loss_fittings_pa
        total_pressure_loss_pa += segment_loss_pa

        # Speichern für Ausgabe
        segment_details.append({
            'id': i + 1,
            'velocity': velocity_m_s,
            'loss_pa': segment_loss_pa,
            'reynolds': reynolds
        })
        
        print(f"{i+1:<3} | {length:<10.1f} | {diameter_mm:<8.1f} | {power_kw:<10.1f} | {velocity_m_s:<8.2f} | {segment_loss_pa/100:<20.2f}")

    # Ergebnisse zusammenfassen
    pump_pressure_pa = pump_pressure_bar * 100000
    available_pressure_pa = pump_pressure_pa - total_pressure_loss_pa
    
    # Warnung bei zu hoher Geschwindigkeit
    high_velocity = any(d['velocity'] > 1.0 for d in segment_details)

    return {
        "pump_pressure_bar": pump_pressure_bar,
        "total_loss_mbar": total_pressure_loss_pa / 100,
        "available_pressure_mbar": available_pressure_pa / 100,
        "available_pressure_bar": available_pressure_pa / 100000,
        "high_velocity_warning": high_velocity
    }

# --- ANWENDUNGSBEISPIEL ---

if __name__ == "__main__":
    # BEISPIEL-SZENARIO:
    # Wir wollen den Druck am Heizkörper im 2. OG wissen.
    # Strang 1: Kellerverteilung (dickes Rohr, versorgt ALLES)
    # Strang 2: Steigstrang bis 1. OG (mittleres Rohr, versorgt 1.OG + 2.OG)
    # Strang 3: Steigstrang bis 2. OG (dünneres Rohr, versorgt nur 2.OG)
    
    # Pumpe liefert 0.4 bar (z.B. 4m Förderhöhe Einstellung)
    PUMP_PRESSURE = 0.4 
    
    path_segments = [
        # Segment 1: Hauptverteilung Keller
        # Länge 5m, DN32 (35mm innen?), Versorgt Gesamthaus (z.B. 20 kW)
        {"length_m": 5.0, "diameter_mm": 32.0, "power_kw": 20.0},
        
        # Segment 2: Steigleitung bis zum Abzweig 1. OG
        # Länge 3m, DN25, Versorgt 1.OG (5kW) + 2.OG (5kW) = 10 kW Rest
        {"length_m": 3.0, "diameter_mm": 25.0, "power_kw": 10.0},
        
        # Segment 3: Weiterführung zum Heizkörper im 2. OG
        # Länge 4m, DN20, Versorgt nur noch Heizkörper 2.OG (5kW)
        {"length_m": 4.0, "diameter_mm": 20.0, "power_kw": 5.0}
    ]

    print("\n--- Berechnung startet ---")
    result = calculate_available_pressure(PUMP_PRESSURE, path_segments)
    
    print("-" * 85)
    print(f"Pumpendruck:              {result['pump_pressure_bar']:.3f} bar")
    print(f"Gesamter Druckverlust:    {result['total_loss_mbar']:.1f} mbar")
    print(f"Verfügbarer Differenzdruck: {result['available_pressure_mbar']:.1f} mbar")
    
    if result['high_velocity_warning']:
        print("\nWARNUNG: In mindestens einem Teilstück ist die Fließgeschwindigkeit > 1.0 m/s!")
        print("Dies kann zu Strömungsgeräuschen führen.")