from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.cross.bus_line_creation_cross import *


FLAG_g = 1   # Re-create the bus lines (YES/NO)
FLAG_r = 1   # Re-create the requests (YES/NO)
FLAG_d = 0   # Flag for debug

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
        print("\n=== DEBUG STRUCTURE (RAW PRINT) ===")

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
            n_requests=2,
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
    if FLAG_d == 1:
        print("\n=== Δ⁺ and Δ⁻ ===")
        for j in (set(data["J"]) | set(data["T"])):
            print(f"Node {j}: Δ⁺={Delta_plus.get(j, set())}, Δ⁻={Delta_minus.get(j, set())}")



    # === MODEL CREATION ===
    mba = MBA_ILP_BASE(data)
    mba.build()


    # === OPTIMIZATION ===
    mba.solve()

    for v in mba.model.getVars():
        if v.VarName.startswith("x") and v.X > 1e-6:
            print(v.VarName, v.X)

    print("\n=== DEBUG: tutti i w (anche zero) ===")
    for l, segs in data["Nl"].items():
        for h, seg in enumerate(segs):
            var_name = f"w_{l}_{h}"
            var = mba.model.getVarByName(var_name)
            val = var.X if var is not None else None
            print(f"Linea {l}, segmento {h}, seg={seg}, w={val}, t={data['t'].get((l,h))}")



    # === RESULTS ===
    x_sol, w_sol, z_sol = mba.get_solution()
    data["model"] = mba.model 
    save_results("results", "cross_BASE", x_sol, w_sol, data, G_lines=G_lines, z_sol=z_sol)
    print("Results saved")
    plot_bus_network(G_lines, w_sol, x_sol=x_sol, z_sol=z_sol, show_passengers=True)
    





