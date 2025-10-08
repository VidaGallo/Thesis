from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.city.bus_line_creation_city import *

FLAG_g = 1   # 1 = rigenera le linee (OSM + bus), 0 = usa file esistenti
FLAG_r = 1   # 1 = rigenera richieste casuali
FLAG_d = 1   # debug prints



if __name__ == "__main__":

    # === CITY SETUP ===
    city_name = "Turin, Italy"
    city_clean = city_name.split(",")[0].strip()

    # === GENERAZIONE DATI BUS (facoltativo) ===
    if FLAG_g == 1:
        print(f"Generating transit data for {city_name}...")
        df_routes, df_stops, G_city, G_lines = transit_data_city(
            city=city_name,
            n_lines=7,          # numero linee bus fittizie
            n_stops=20,         # fermate per linea
            network_type="drive"
        )

        G_bar = build_G_bar(G_lines)
        with open(f"data/bus_lines/city/city_{city_clean}_Gbar_graph.gpickle", "wb") as f:
            pickle.dump(G_bar, f)

        G_reb = create_rebalancing_graph(
            G_lines, df_routes, df_stops,
            save_path=f"data/bus_lines/city/city_{city_clean}_rebalancing_graph.gpickle"
        )

        G_full = create_full_graph(G_lines, G_reb)
        with open(f"data/bus_lines/city/city_{city_clean}_G_graph.gpickle", "wb") as f:
            pickle.dump(G_full, f)

        plot_transit_graph(G_city, G_lines, G_reb, df_routes, df_stops,
                           title=f"Transit Lines + Rebalancing ({city_clean})", save_fig=True)

    # === LOAD CITY DATA ===
    lines_csv = f"data/bus_lines/city/city_{city_clean}_bus_lines.csv"
    stops_csv = f"data/bus_lines/city/city_{city_clean}_bus_stops.csv"
    data = load_sets(lines_csv, stops_csv)

    if FLAG_d:
        print(f"\n=== STRUCTURE CHECK ({city_clean}) ===")
        for k in ["L", "V", "J", "T", "S"]:
            print(f"{k}: {len(data[k])} elementi")

    # === CAPACITÀ BUS ===
    data["Q"] = 10  # moduli max per linea (es. bus modulari da 10 posti)

    # === GRAFI ===
    with open(f"data/bus_lines/city/city_{city_clean}_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open(f"data/bus_lines/city/city_{city_clean}_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)

    # === ASSEGNAZIONE TEMPI DI VIAGGIO ===
    G_lines = assign_travel_times(G_lines, speed_kmh=30)   # bus line speed
    G_reb   = assign_travel_times(G_reb,   speed_kmh=40)   # rebalancing speed

    t  = compute_segment_travel_times(data["Nl"], G_lines)
    tr = compute_rebalancing_travel_times(data["R"], G_reb)
    data["t"], data["tr"] = t, tr

    if FLAG_d:
        print("\n--- TEMPI DI VIAGGIO (MEDIA) ---")
        for (l, h), val in list(t.items())[:10]:
            print(f"Linea {l}, seg {h}: {val/60:.1f} min")
        for (i, j), val in list(tr.items())[:5]:
            print(f"Reb ({i}→{j}): {val/60:.1f} min")

    # === GENERAZIONE RICHIESTE (opzionale) ===
    if FLAG_r == 1:
        df_stops = pd.read_csv(stops_csv)
        with open(f"data/bus_lines/city/city_{city_clean}_Gbar_graph.gpickle", "rb") as f:
            G_bar = pickle.load(f)

        generate_requests_graph_asymm(
            df_stops, G_bar,
            n_requests=25,   # numero richieste da simulare
            output_csv=f"data/demands/city_{city_clean}_mobility_requests.csv"
        )

    # === LOAD REQUESTS ===
    K, p, Pk, Akl, Blk = load_requests(
        requests_csv=f"data/demands/city_{city_clean}_mobility_requests.csv",
        data=data
    )
    data["K"], data["p"], data["Pk"], data["Akl"], data["Blk"] = K, p, Pk, Akl, Blk

    if FLAG_d:
        print(f"\nNumero richieste: {len(K)}")
        print("Esempi:")
        for k in list(K)[:5]:
            print(f"  k={k}: path={Pk[k]}, p={p[k]}")

    # === COSTRUZIONE Δ⁺ / Δ⁻ ===
    Delta_plus, Delta_minus = build_delta_sets(data["Nl"], data["J"], data["T"])
    data["Delta_plus"], data["Delta_minus"] = Delta_plus, Delta_minus

    if FLAG_d:
        print("\n--- Δ⁺ / Δ⁻ (nodi speciali) ---")
        for j in list(set(data["J"]) | set(data["T"]))[:5]:
            print(f"Node {j}: Δ⁺={Delta_plus.get(j, set())}, Δ⁻={Delta_minus.get(j, set())}")

    # === MODELLI ===
    mba_base = MBA_ILP_BASE(data)
    mba_base.build()
    mba_full = MBA_ILP_FULL(data)
    mba_full.build()

    # === RISOLUZIONE ===
    print(f"\n============== RISOLUZIONE BASE MODEL ({city_clean}) ==============\n")
    mba_base.solve()
    print(f"\n============== RISOLUZIONE FULL MODEL ({city_clean}) ==============\n")
    mba_full.solve()

    # === DISPLAY + SAVE ===
    if FLAG_d:
        display_results(mba_base, f"{city_clean}_BASE", data)
    x_base, w_base, z_base = save_results_model(mba_base, f"{city_clean}_BASE", data, G_lines)

    if FLAG_d:
        display_results(mba_full, f"{city_clean}_FULL", data)
    x_full, w_full, z_full, v_full = save_results_model(mba_full, f"{city_clean}_FULL", data, G_lines)

    # === OPTIONAL VISUAL COMPARISON ===
    # plot_comparison_base_full(G_lines, G_reb, w_base, w_full, v_full)
