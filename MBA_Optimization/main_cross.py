from utils.data_loader import *
from utils.save_results import *
from models.model_mba_BASE import *
import pandas as pd
import json




if __name__ == "__main__":

    # === LOAD CSV ===
    # L→ linee
    # N → segmenti per linea
    # S, J, T → nodi ordinari, giunzioni, terminali
    # A → archi della rete
    # R → archi di ribilanciamento
    data = load_sets(
        lines_csv=f"data/bus_lines/cross/cross_bus_lines.csv",
        stops_csv=f"data/bus_lines/cross/cross_bus_stops.csv"
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


    # === CAPACITY ===
    data["Q"] = 10


    # === TRAVEL TIME ===
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f) 
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    t = compute_segment_travel_times(data['N'], G_lines)
    data['t'] = t



    # === MODEL CREATION ===
    mba = MBA_ILP_BASE(data)
    mba.build()


    # === OPTIMIZATION ===
    mba.solve()


    # === RESULTS ===
    results_folder = "results"
    prefix = "cross_BASE"
    x_sol, w_sol = mba.get_solution()
    save_results(results_folder, prefix, x_sol, w_sol, data)




