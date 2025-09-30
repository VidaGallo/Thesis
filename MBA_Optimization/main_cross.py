from utils.f_for_data import *
from utils.f_for_results import *
from models.models_mba import *
from data.demands.demand_creation import *
from data.bus_lines.cross.bus_line_creation_cross import *


FLAG_g = 0   # Re-create the bus lines (YES/NO)
FLAG_r = 0   # Re-create the requests (YES/NO)

if __name__ == "__main__":

    # === CSV CREATION (optional) ===
    if FLAG_g == 1:
        df_routes, df_stops = create_test_data_cross(n_stops=7)
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


    # === CAPACITY ===
    data["Q"] = 10


    # === TRAVEL TIME ===
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f) 
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    t = compute_segment_travel_times(data['N'], G_lines)
    data['t'] = t



    # === REQUEST CREATION (optional) ===
    if FLAG_r == 1:
        df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
        with open("data/bus_lines/cross/cross_Gbar_graph.gpickle", "rb") as f:
            G_bar = pickle.load(f)
        generate_requests_graph(
            df_stops, G_bar,
            n_requests=50,
            output_csv="data/demands/cross_mobility_requests.csv"
            )

    
    # === LOAD REQUESTS ===
    # K → ID richieste
    # p → n° passeggeri
    # Pk → shortest paths sul grafo delle linee dei bus
    K, p, Pk = load_requests(
    requests_csv="data/demands/cross_mobility_requests.csv",
    data=data
    )
    data["K"] = K
    data["p"] = p
    data["Pk"] = Pk
    print(Pk)

    # === MODEL CREATION ===
    mba = MBA_ILP_BASE(data)
    mba.build()


    # === OPTIMIZATION ===
    mba.solve()


    # === RESULTS ===
    results_folder = "results"
    prefix = "cross_BASE"
    x_sol, w_sol = mba.get_solution()
    plot_bus_network(G_lines, w_sol, x_sol=x_sol, show_passengers=True)
    save_results(results_folder, prefix, x_sol, w_sol, data)
    print("Results saved")




