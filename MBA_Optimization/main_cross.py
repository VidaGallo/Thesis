from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.cross.bus_line_creation_cross import *


FLAG_g = 0   # Re-create the bus lines (YES/NO)
FLAG_r = 1   # Re-create the requests (YES/NO)
FLAG_d = 1   # Flag for debug

if __name__ == "__main__":

    # === CSV CREATION (optional) ===
    if FLAG_g == 1:
        df_routes, df_stops = create_test_data_cross(n_stops=5)
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
    if FLAG_d == 1:
        print(f"L (linee): {data['L']}")
        print(f"Numero archi A: {len(data['A'])}")
        print(f"Numero segmenti Nl: {sum(len(v) for v in data['Nl'].values())}")
        # --- Linee ---
        print(f"\nLinee (L): {data['L']} (totale {len(data['L'])})")
        # --- Nodi ---
        print(f"Totale nodi V: {len(data['V'])}")
        print(f"  Ordinari S ({len(data['S'])}): {sorted(list(data['S']))}")
        print(f"  Giunzioni J ({len(data['J'])}): {sorted(list(data['J']))}")
        print(f"  Terminali T ({len(data['T'])}): {sorted(list(data['T']))}")
        # --- Archi ---
        print(f"\nArchi A (line arcs): {len(data['A'])}")
        for (i,j,l) in sorted(data['A']):
            print(f"  ({i}->{j}, linea {l})")
        # --- Archi di ribilanciamento ---
        print(f"\nArchi di ribilanciamento R: {len(data['R'])}")
        for (i,j) in sorted(data['R']):
            print(f"  ({i}->{j})")
        # --- Segmenti Nl ---
        print(f"\nNumero segmenti totali: {sum(len(v) for v in data['Nl'].values())}")
        for l, segs in data["Nl"].items():
            print(f"  Linea {l} ha {len(segs)} segmenti:")
            for idx, seg in enumerate(segs):
                print(f"    Segmento {idx}: {seg} (tipo={type(seg)})")

        


    # === CAPACITY ===
    data["Q"] = 10


    # === TRAVEL TIME ===
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f) 
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    t = compute_segment_travel_times(data['Nl'], G_lines)
    data['t'] = t
    if FLAG_d == 1:
        print("Segment travel times:")
        for k,v in t.items():
            print(f"  {k} -> {v:.3f} sec")




    # === REQUEST CREATION (optional) ===
    if FLAG_r == 1:
        df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
        with open("data/bus_lines/cross/cross_Gbar_graph.gpickle", "rb") as f:
            G_bar = pickle.load(f)
        generate_requests_graph(
            df_stops, G_bar,     # Using G_bar (simple, directed, no bus lines)
            n_requests=5,
            output_csv="data/demands/cross_mobility_requests.csv"
            )

    
    # === LOAD REQUESTS ===
    K, p, Pk, Pkl, Blk = load_requests(
        requests_csv="data/demands/cross_mobility_requests.csv",
        data=data
    )
    data["K"], data["p"], data["Pk"], data["Pkl"], data["Blk"] = K, p, Pk, Pkl, Blk
    
    if FLAG_d == 1:
        print(f"Numero richieste K: {len(K)}")
        print(f"Passeggeri per richiesta: {p}")
        for k in K:
            print(f"  Richiesta {k}: Pk={Pk[k]}")
        print("\n=== CHECK Pkl ===")
        for (k, l), arcs in Pkl.items():
            print(f"  (k={k}, l={l}) -> {arcs}")
        print("\n=== CHECK Blk ===")
        for (l, k), triples in Blk.items():
            print(f"  (l={l}, k={k}) -> {triples}")

    # === BUILD Δ⁺/Δ⁻ ===
    Delta_plus, Delta_minus = build_delta_sets(data["Nl"], data["J"], data["T"])
    data["Delta_plus"], data["Delta_minus"] = Delta_plus, Delta_minus
    print("\n=== Δ⁺ and Δ⁻ ===")
    for j in (data["J"] | data["T"]):
        print(f"Node {j}: Δ⁺={Delta_plus.get(j, set())}, Δ⁻={Delta_minus.get(j, set())}")



    # === MODEL CREATION ===
    mba = MBA_ILP_BASE(data)
    mba.build()


    # === OPTIMIZATION ===
    mba.solve()


    # === RESULTS ===
    results_folder = "results"
    prefix = "cross_BASE"
    x_sol, w_sol, z_sol = mba.get_solution()
    plot_bus_network(G_lines, w_sol, x_sol=x_sol, z_sol=z_sol, show_passengers=True)
    save_results(results_folder, prefix, x_sol, w_sol, data, z_sol=z_sol)
    print("Results saved")





