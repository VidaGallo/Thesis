import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np
import json

random.seed(123)
np.random.seed(123)


def generate_requests_graph_symm(df_stops, G_bar, n_requests=20, output_csv=None):
    """
    Generate mobility requests:
    - For each O-D pair, also generate the reverse D-O request
    - Works with MultiDiGraph
    """
    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    k = 0
    used_pairs = set()   # to avoid duplicates

    while k < n_requests:
        # Estrai origine e destinazione casuali
        o_k, d_k = random.sample(stop_ids, 2)

        # Evita coppie già usate (in entrambe le direzioni)
        if (o_k, d_k) in used_pairs or (d_k, o_k) in used_pairs:
            continue

        # Controlla se esiste un percorso in entrambe le direzioni
        if not nx.has_path(G_bar, o_k, d_k) or not nx.has_path(G_bar, d_k, o_k):
            continue

        # Percorso minimo O→D
        path_fwd = nx.shortest_path(G_bar, source=o_k, target=d_k, weight='weight')
        path_fwd = [int(n) for n in path_fwd]

        # Percorso inverso D→O
        path_rev = list(reversed(path_fwd))

        # Passeggeri medi
        p_k = int(np.random.geometric(p=0.6))
        if p_k == 0:
            p_k = 1  # evita 0 passeggeri

        # Richiesta O→D
        requests_list.append({
            "request_id": len(requests_list),
            "origin": o_k,
            "destination": d_k,
            "path_nodes": json.dumps(path_fwd),
            "avg_passengers_per_time_unit": p_k
        })

        # Richiesta D→O (stesso p_k, percorso inverso)
        requests_list.append({
            "request_id": len(requests_list),
            "origin": d_k,
            "destination": o_k,
            "path_nodes": json.dumps(path_rev),
            "avg_passengers_per_time_unit": p_k
        })

        used_pairs.add((o_k, d_k))
        k += 1

    df_requests = pd.DataFrame(requests_list)

    if output_csv:
        df_requests.to_csv(output_csv, index=False)

    print(f"✅ Generated {len(df_requests)} requests ({n_requests} pairs, with reverse directions).")

    return df_requests




def generate_requests_graph_asymm(df_stops, G_bar, n_requests=20, output_csv=None):
    """
    Generate mobility requests:
    - Only origin, destination, and node path
    - Works with MultiDiGraph
    """
    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    k = 0
    used_pairs = set()   # to avoid duplicates
    while k < n_requests:
        # Estrai origine e destinazione casuali
        o_k, d_k = random.sample(stop_ids, 2)
        #print(o_k, d_k)

        # Skip if already used (in either direction)
        if (o_k, d_k) in used_pairs:
            continue

        if not nx.has_path(G_bar, o_k, d_k):
            #print("no path")
            continue

        # Percorso minimo basato sul peso
        path_nodes = nx.shortest_path(G_bar, source=o_k, target=d_k, weight='weight')
        path_nodes = [int(n) for n in path_nodes]

        # Passeggeri medi
        p_k = int(np.random.geometric(p=0.6))

        requests_list.append({
            "request_id": k,
            "origin": o_k,
            "destination": d_k,
            "path_nodes": json.dumps(path_nodes),
            "avg_passengers_per_time_unit": p_k
        })

        used_pairs.add((o_k, d_k))
        #print(used_pairs)
        k += 1

    df_requests = pd.DataFrame(requests_list)

    if output_csv:
        df_requests.to_csv(output_csv, index=False)

    return df_requests



# === EXAMPLE TO USE IN MAIN ===
### Cross
with open("data/bus_lines/cross/cross_Gbar_graph.gpickle", "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
generate_requests_graph_asymm(
    df_stops, G_bar,
    n_requests=5,
    output_csv="data/demands/cross_mobility_requests.csv"
)

"""
### Grid
with open("data/bus_lines/grid/grid_Gbar_graph.gpickle", "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/grid/grid_bus_stops.csv")
generate_requests_graph_asymm(
    df_stops, G_bar,
    n_requests=5,
    output_csv="data/demands/grid_mobility_requests.csv"
)
"""
"""
### City
city_name = "Turin, Italy"
city_clean = city_name.split(",")[0].strip()
graph_file = f"data/bus_lines/city/city_{city_clean}_Gbar_graph.gpickle"
with open(graph_file, "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv(f"data/bus_lines/city/city_{city_clean}_bus_stops.csv")
generate_requests_graph_asymm(
    df_stops, G_bar,
    n_requests=5,
    output_csv=f"data/demands/city_{city_clean}_mobility_requests.csv"
)

"""