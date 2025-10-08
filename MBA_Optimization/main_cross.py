from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.cross.bus_line_creation_cross import *


FLAG_g = 0  # Re-create the bus lines (YES/NO)
FLAG_r = 1   # Re-create the requests (YES/NO)
FLAG_d = 1   # Flag for debug

if __name__ == "__main__":

    # === CSV CREATION (optional) ===
    if FLAG_g == 1:
        df_routes, df_stops = create_test_data_cross(n_stops_line=4)
        G_lines, df_routes, df_stops = create_lines_graph(df_routes, df_stops)
        G_reb = create_rebalancing_graph(
            G_lines, df_routes, df_stops,
            save_path="data/bus_lines/cross/cross_rebalancing_graph.gpickle"
            )
        G_bar = create_G_bar(
            G_lines,
            save_path="data/bus_lines/cross/cross_Gbar_graph.gpickle"
        )
        # Plot (opzionale: mostri G_lines + G_reb, non G_bar perché è solo per percorsi passeggeri)
        plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing")



    # === LOAD CSV ===
    # L→ linee
    # N → segmenti per linea
    # S, J, T → nodi ordinari, giunzioni, terminali
    # A → archi della rete bus
    # R → archi di ribilanciamento
    data = load_sets(
        lines_csv=f"data/bus_lines/cross/cross_bus_lines.csv",
        stops_csv=f"data/bus_lines/cross/cross_bus_stops.csv"
        )
    
    # === DEBUG: VERIFICA STRUTTURE DATI ===
    if FLAG_d == 1:
        print("\n=== DEBUG STRUCTURE ===")

        print("\nL (linee):")
        print(data["L"])

        print("\nV (nodi):")
        print(data["V"])

        print("\nS (fermate ordinarie):")
        print(data["S"])

        print("\nJ (giunzioni):")
        print(data["J"])

        print("\nT (terminali):")
        print(data["T"])

        print("\nA (archi di linea) [i,j,l]:")
        print(data["A"])

        print("\nR (archi di riequilibrio) [i,j]:")
        print(data["R"])

        print("\nNl (segmenti per linea):")
        print(data["Nl"])



    # === CAPACITY ===
    data["Q"] = 8



    # === TRAVEL TIME ===
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open("data/bus_lines/cross/cross_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)

    # === Assegnazione travel time (m/s) ===
    G_lines = assign_travel_times(G_lines, speed_kmh=35)   # bus lines
    G_reb   = assign_travel_times(G_reb,   speed_kmh=40)   # rebalance network

    # === Calcolo tempi per segmenti e archi di rebalance ===
    t  = compute_segment_travel_times(data['Nl'], G_lines)
    tr = compute_rebalancing_travel_times(data['R'], G_reb)
    data['t']  = t
    data['tr'] = tr


    # === DEBUG ===
    if FLAG_d == 1:
        print("\n t' (tempi bus lines) [l,h]: ")
        for (l, h), val in sorted(t.items()):
            print(f"Linea {l}, segmento {h}: {val:.2f} sec")

        print("\n tau (tempi archi rebalance) [i,j]: ")
        for (i, j), val in sorted(tr.items()):
            print(f"Arco di rebalancing ({i} → {j}) : {val:.2f} sec")



    # === REQUEST CREATION (optional) ===
    if FLAG_r == 1:
        df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
        with open("data/bus_lines/cross/cross_Gbar_graph.gpickle", "rb") as f:
            G_bar = pickle.load(f)
        generate_requests_graph_asymm(    # symm or asymm
            df_stops, G_bar,     # Using G_bar (simple, directed, no bus lines)
            n_requests=20,
            output_csv="data/demands/cross_mobility_requests.csv"
            )

    
    # === LOAD REQUESTS ===
    K, p, Pk, Akl, Blk = load_requests(
        requests_csv="data/demands/cross_mobility_requests.csv",
        data=data
    )
    data["K"], data["p"], data["Pk"], data["Akl"], data["Blk"] = K, p, Pk, Akl, Blk
    
    if FLAG_d == 1:
        print(f"\nNumero richieste K: {len(K)}")
        print(f"\nPasseggeri per richiesta pk: {p}")

        print(f"\nPath richieste Pk: ")
        for k in K:
            print(f"Richiesta {k}: Pk={Pk[k]}")
        print("\n=== CHECK Akl ===")
        for (k, l), arcs in Akl.items():
            print(f"  (k={k}, l={l}) -> {arcs}")
        print("\n=== CHECK Blk ===")
        for (l, k), triples in Blk.items():
            print(f"  (l={l}, k={k}) -> {triples}")

    # === BUILD Δ⁺/Δ⁻ ===
    Delta_plus, Delta_minus = build_delta_sets(data["Nl"], data["J"], data["T"])
    data["Delta_plus"], data["Delta_minus"] = Delta_plus, Delta_minus
    if FLAG_d == 1:
        print("\n=== Δ⁺ and Δ⁻ ===")
        for j in (set(data["J"]) | set(data["T"])):
            print(f"Node {j}: Δ⁺={Delta_plus.get(j, set())}, Δ⁻={Delta_minus.get(j, set())}")



    # === MODEL CREATION ===
    mba_base = MBA_ILP_BASE(data)
    mba_base.build()
    mba_full = MBA_ILP_FULL(data)
    mba_full.build()


    # === OPTIMIZATION ===
    print("\n\n\n")
    print("============== RISOLUZIONE BASE MODEL ==============\n")
    mba_base.solve()
    print("\n\n\n")
    print("\n============== RISOLUZIONE FULL MODEL ==============\n")
    mba_full.solve()

    print("\n\n\n")
    
    # === DISPLAY + SAVE per entrambi ===
    if FLAG_d == 1:
        display_results(mba_base, "cross_BASE", data)
    x_base, w_base, z_base = save_results_model(mba_base, "cross_BASE", data, G_lines)


    if FLAG_d == 1:
        display_results(mba_full, "cross_FULL", data)
    x_full, w_full, z_full, v_full = save_results_model(mba_full, "cross_FULL", data, G_lines)




    # Plot confronto
    #plot_comparison_base_full(G_lines, G_reb, w_base, w_full, v_full)

