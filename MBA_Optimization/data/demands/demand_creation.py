import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np

random.seed(123)
np.random.seed(123)


def generate_requests(lines_csv, stops_csv, output_csv, n_requests=20, graph=None):
    """
    Generate mobility requests with full paths from line/grid/graph CSVs.

    Parameters:
    - lines_csv: path to lines CSV
    - stops_csv: path to stops CSV
    - output_csv: path to save mobility requests CSV
    - n_requests: number of requests to generate
    - graph: optional networkx graph (for 'graph' type data)
    """
    # === Load data ===
    df_stops = pd.read_csv(stops_csv)
    df_lines = pd.read_csv(lines_csv)
    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    # === Build stop graph ===
    G_stops = nx.Graph()
    for _, row in df_lines.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        # Map coordinates to stop_ids (assumes order matches creation)
        line_stop_ids = []
        for i, coord in enumerate(coords_text.split(", ")):
            if 'node' in df_stops.columns:
                # For test/grid data
                stop_id = df_stops.iloc[i]['stop_id']
            else:
                stop_id = i
            line_stop_ids.append(stop_id)

        # Add edges between consecutive stops
        for u, v in zip(line_stop_ids[:-1], line_stop_ids[1:]):
            if graph is not None:
                # If a graph is provided, take distance from it
                if graph.has_edge(u, v):
                    weight = graph[u][v].get('length', 1)
                else:
                    weight = 1
            else:
                weight = 1
            G_stops.add_edge(u, v, weight=weight)

    # === Generate requests ===
    for k in range(n_requests):
        o_k = random.choice(stop_ids)
        d_k = random.choice([s for s in stop_ids if s != o_k])

        # Compute path
        try:
            path_nodes = nx.shortest_path(G_stops, source=o_k, target=d_k, weight='weight')
        except nx.NetworkXNoPath:
            path_nodes = [o_k, d_k]  # fallback

        # Average passengers per unit time
        p_k = np.random.geometric(p=0.7)
        requests_list.append({
            "request_id": k,
            "origin": o_k,
            "destination": d_k,
            "path": path_nodes,
            "avg_passengers_per_time_unit": p_k
        })

    # === Save ===
    df_requests = pd.DataFrame(requests_list)
    df_requests.to_csv(output_csv, index=False)
    print(f"Saved {n_requests} mobility requests to {output_csv}")
    return df_requests





### Line 
generate_requests(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv",
    output_csv="data/demands/mobility_requests_line.csv",
    n_requests=15
)

### Grid
generate_requests(
    lines_csv="data/bus_lines/grid_lines.csv",
    stops_csv="data/bus_lines/grid_stops.csv",
    output_csv="data/demands/mobility_requests_grid.csv",
    n_requests=23
)

### Graph
city_name = "Turin, Italy" 
city_clean = city_name.split(",")[0]
graph_file = f"data/bus_lines/bus_lines_{city_clean}_graph.gpickle"
with open(graph_file, "rb") as f:
    G = pickle.load(f)
generate_requests(
    lines_csv="data/bus_lines/graph_lines_Turin.csv",
    stops_csv="data/bus_lines/graph_stops_Turin.csv",
    output_csv="data/demands/mobility_requests_graph.csv",
    n_requests=100,
    graph=G
)
