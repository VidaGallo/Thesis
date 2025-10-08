from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.grid.bus_line_creation_grid import *

FLAG_g = 1  # 1 per ricreare il dataset bus lines
FLAG_r = 1  # 1 per ricreare le richieste
FLAG_d = 1  # debug print

if __name__ == "__main__":

    # === GENERAZIONE BUS LINES (opzionale) ===
    if FLAG_g == 1:
        df_routes, df_stops = create_grid_test_data(n_lines=4, n_stops=6, grid_size=8)
        G_lines = create_grid_graph(df_routes, df_stops)
        G_bar   = create_G_bar(G_lines, save_path="data/bus_lines/grid/grid_Gbar_graph.gpickle")
        G_reb   = create_grid_rebalancing_graph(G_lines, df_routes, df_stops)
        plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Grid Transit + Rebalancing", save_fig=True)

    # === LOAD DATA ===
    data = load_sets(
        lines_csv="data/bus_lines/grid/grid_bus_lines.csv",
        stops_csv="data/bus_lines/grid/grid_bus_stops.csv"
    )

    # === DEBUG ===
    if FLAG_d == 1:
        print("\n=== STRUCTURE CHECK (GRID) ===")
        for k in ["L","V","S","J","T","A","R","Nl"]:
            print(f"\n{k} = {data[k]}")

    # === CAPACITÀ ===
    data["Q"] = 8

    # === TRAVEL TIMES ===
    with open("data/bus_lines/grid/grid_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open("data/bus_lines/grid/grid_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)

    # assegna tempi di percorrenza (m/s)
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    G_reb   = assign_travel_times(G_reb, speed_kmh=40)

    # calcola tempi per segmenti e per archi di rebalancing
    t  = compute_segment_travel_times(data["Nl"], G_lines)
    tr = compute_rebalancing_travel_times(data["R"], G_reb)
    data["t"], data["tr"] = t, tr

    if FLAG_d == 1:
        print("\n--- Tempi medi (t, τ) ---")
        for (l,h), val in sorted(t.items()):
            print(f"Linea {l}, segmento {h} : {val:.2f} sec")
        for (i,j), val in sorted(tr.items()):
            print(f"Arco di rebalancing ({i}→{j}) : {val:.2f} sec")

    # === RICHIESTE (creazione opzionale) ===
    if FLAG_r == 1:
        df_stops = pd.read_csv("data/bus_lines/grid/grid_bus_stops.csv")
        with open("data/bus_lines/grid/grid_Gbar_graph.gpickle", "rb") as f:
            G_bar = pickle.load(f)
        generate_requests_graph_asymm(
            df_stops, G_bar,
            n_requests=20,
            output_csv="data/demands/grid_mobility_requests.csv"
        )

    # === LOAD REQUESTS ===
    K, p, Pk, Akl, Blk = load_requests(
        requests_csv="data/demands/grid_mobility_requests.csv",
        data=data
    )
    data["K"], data["p"], data["Pk"], data["Akl"], data["Blk"] = K, p, Pk, Akl, Blk

    if FLAG_d == 1:
        print(f"\nNumero richieste: {len(K)}")
        print("\nPasseggeri per richiesta:")
        print(p)
        print("\nEsempi Pk:")
        for k in list(K)[:5]:
            print(f"  k={k}: {Pk[k]}")

    # === COSTRUZIONE Δ⁺ / Δ⁻ ===
    Delta_plus, Delta_minus = build_delta_sets(data["Nl"], data["J"], data["T"])
    data["Delta_plus"], data["Delta_minus"] = Delta_plus, Delta_minus

    if FLAG_d == 1:
        print("\n--- Δ⁺ / Δ⁻ ---")
        for j in (set(data["J"]) | set(data["T"])):
            print(f"Node {j}: Δ⁺={Delta_plus.get(j, set())}, Δ⁻={Delta_minus.get(j, set())}")

    # === MODELLI ===
    mba_base = MBA_ILP_BASE(data)
    mba_base.build()

    mba_full = MBA_ILP_FULL(data)
    mba_full.build()

    # === RISOLUZIONE ===
    print("\n\n\n============== RISOLUZIONE BASE MODEL (GRID) ==============\n")
    mba_base.solve()
    print("\n\n\n============== RISOLUZIONE FULL MODEL (GRID) ==============\n")
    mba_full.solve()

    print("\n\n\n")
    # === DISPLAY + SAVE ===
    if FLAG_d == 1:
        display_results(mba_base, "grid_BASE", data)
    x_base, w_base, z_base = save_results_model(mba_base, "grid_BASE", data, G_lines)

    if FLAG_d == 1:
        display_results(mba_full, "grid_FULL", data)
    x_full, w_full, z_full, v_full = save_results_model(mba_full, "grid_FULL", data, G_lines)

    # === OPTIONAL PLOT ===
    #plot_comparison_base_full(G_lines, G_reb, w_base, w_full, v_full)
