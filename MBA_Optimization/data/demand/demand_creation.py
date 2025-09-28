import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np

random.seed(123)
np.random.seed(123)

def generate_requests(lines_csv, stops_csv, output_csv, n_requests=20, graph=None):
    """
    Generate mobility requests from line/grid/graph CSVs.
    
    Parameters:
    - lines_csv: path to lines CSV
    - stops_csv: path to stops CSV
    - output_csv: path to save mobility requests CSV
    - n_requests: number of requests to generate
    - seed: random seed for reproducibility
    - graph: optional networkx graph (for 'graph' type data)
    """
    # === Load stops ===
    df_stops = pd.read_csv(stops_csv)
    stop_ids = df_stops['stop_id'].tolist()
    
    requests_list = []

    for k in range(n_requests):
        o_k = random.choice(stop_ids)
        d_k = random.choice([s for s in stop_ids if s != o_k])  # destination != origin

        # Path: list of stops between origin and destination along the line
        if graph is not None:
            # For graph: use shortest path along network
            try:
                path_nodes = nx.shortest_path(graph, source=o_k, target=d_k, weight='length')
            except:
                path_nodes = [o_k, d_k]
        else:
            # For line/grid: assume direct path along node IDs (just origin -> destination)
            path_nodes = [o_k, d_k]

        # Average passengers per unit time
        p_k = np.random.geometric(p=0.7)     # Geompetric distribution (with max prob. at 1, no 0)

        requests_list.append({
            "request_id": k,
            "origin": o_k,
            "destination": d_k,
            "path": path_nodes,
            "avg_passengers_per_time_unit": p_k
        })

    df_requests = pd.DataFrame(requests_list)
    df_requests.to_csv(output_csv, index=False)
    print(f"Saved {n_requests} mobility requests to {output_csv}")

    return df_requests



### Line 
generate_requests(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv",
    output_csv="data/demand/mobility_requests_line.csv",
    n_requests=10
)

### Grid
generate_requests(
    lines_csv="data/bus_lines/grid_lines.csv",
    stops_csv="data/bus_lines/grid_stops.csv",
    output_csv="data/demand/mobility_requests_grid.csv",
    n_requests=20
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
    output_csv="data/demand/mobility_requests_graph.csv",
    n_requests=50,
    graph=G
)
