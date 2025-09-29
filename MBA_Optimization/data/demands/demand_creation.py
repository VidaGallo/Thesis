import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np

random.seed(123)
np.random.seed(123)

def generate_requests_graph(df_stops, df_lines, G_lines, n_requests=20, output_csv=None):
    """
    Generate mobility requests using an existing bus line graph (G_lines).
    - df_stops: DataFrame with stops
    - df_lines: DataFrame with bus lines
    - G_lines: networkx graph of stops
    """
    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    # Ensure every edge has 'lines' set
    for u, v, data in G_lines.edges(data=True):
        if 'lines' not in data:
            data['lines'] = set()

    # Map coordinates -> stop_id (optional)
    coord_to_stop_id = {(row['lon'], row['lat']): row['stop_id'] for _, row in df_stops.iterrows()}

    for k in range(n_requests):
        o_k, d_k = random.sample(stop_ids, 2)

        if not nx.has_path(G_lines, o_k, d_k):
            print(f"No path between {o_k} and {d_k}, skipping request")
            continue

        path_nodes = nx.shortest_path(G_lines, source=o_k, target=d_k, weight='weight')

        # Recover lines for each edge in path
        path_lines = []
        for u, v in zip(path_nodes[:-1], path_nodes[1:]):
            lines = G_lines[u][v]['lines']
            path_lines.append(list(lines))  # multiple lines possible

        p_k = np.random.geometric(p=0.6)  # >0, most likely 1
        requests_list.append({
            "request_id": k,
            "origin": o_k,
            "destination": d_k,
            "path_nodes": path_nodes,
            "path_lines": path_lines,
            "avg_passengers_per_time_unit": p_k
        })

    df_requests = pd.DataFrame(requests_list)
    if output_csv:
        df_requests.to_csv(output_csv, index=False)
    return df_requests






# === LINE ===
with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
    G_lines = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
df_lines = pd.read_csv("data/bus_lines/cross/cross_bus_lines.csv")
generate_requests_graph(df_stops, df_lines, G_lines, n_requests=15,
                        output_csv="data/demands/cross_mobility_requests.csv")

# === GRID ===
with open("data/bus_lines/grid/grid_bus_lines_graph.gpickle", "rb") as f:
    G_lines = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/grid/grid_bus_stops.csv")
df_lines = pd.read_csv("data/bus_lines/grid/grid_bus_lines.csv")
generate_requests_graph(df_stops, df_lines, G_lines, n_requests=23,
                        output_csv="data/demands/grid_mobility_requests.csv")

# === CITY ===
city_name = "Turin, Italy"
city_clean = city_name.split(",")[0]
graph_file = f"data/bus_lines/city/city_{city_clean}_bus_lines_graph.gpickle"
with open(graph_file, "rb") as f:
    G_lines = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/city/city_{city_clean}_bus_stops.csv")
df_lines = pd.read_csv("data/bus_lines/city/city_{city_clean}_bus_lines.csv")
generate_requests_graph(df_stops, df_lines, G_lines, n_requests=100,
                        output_csv="data/demands/city_{city_clean}_mobility_requests.csv")

