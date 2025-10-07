import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np
import json

random.seed(123)
np.random.seed(123)


def generate_requests_graph(df_stops, G_lines, n_requests=20, output_csv=None):
    """
    Generate mobility requests:
    - Only origin, destination, and node path
    - Works with MultiDiGraph
    """
    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    k = 0
    while k < n_requests:
        # Estrai origine e destinazione casuali
        o_k, d_k = random.sample(stop_ids, 2)

        if not nx.has_path(G_lines, o_k, d_k):
            continue

        # Percorso minimo basato sul peso
        path_nodes = nx.shortest_path(G_lines, source=o_k, target=d_k, weight='weight')
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
generate_requests_graph(
    df_stops, G_bar,
    n_requests=50,
    output_csv="data/demands/cross_mobility_requests.csv"
)


### Grid
with open("data/bus_lines/grid/grid_Gbar_graph.gpickle", "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/grid/grid_bus_stops.csv")
generate_requests_graph(
    df_stops, G_bar,
    n_requests=100,
    output_csv="data/demands/grid_mobility_requests.csv"
)


### City
city_name = "Turin, Italy"
city_clean = city_name.split(",")[0].strip()
graph_file = f"data/bus_lines/city/city_{city_clean}_Gbar_graph.gpickle"
with open(graph_file, "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv(f"data/bus_lines/city/city_{city_clean}_bus_stops.csv")
generate_requests_graph(
    df_stops, G_bar,
    n_requests=100,
    output_csv=f"data/demands/city_{city_clean}_mobility_requests.csv"
)

