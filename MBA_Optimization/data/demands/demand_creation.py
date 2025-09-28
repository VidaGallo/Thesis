import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np

random.seed(123)
np.random.seed(123)

def generate_requests(lines_csv, stops_csv, output_csv, n_requests=20, graph=None):
    df_stops = pd.read_csv(stops_csv)
    df_lines = pd.read_csv(lines_csv)

    stop_ids = df_stops['stop_id'].tolist()
    requests_list = []

    # === Build stop graph with line info ===
    G_stops = nx.Graph()
    coord_to_stop_id = {(row.lon, row.lat): row.stop_id for _, row in df_stops.iterrows()}

    for _, row in df_lines.iterrows():
        coords = row['geometry'].replace("LINESTRING (", "").replace(")", "").split(", ")
        stop_ids_line = [coord_to_stop_id[tuple(map(float, c.split()))] for c in coords]

        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            if not G_stops.has_edge(u, v):
                G_stops.add_edge(u, v, weight=1, lines=set())
            G_stops[u][v]['lines'].add(row['ref'])

    # === Generate requests ===
    for k in range(n_requests):
        o_k, d_k = random.sample(stop_ids, 2)
        if not nx.has_path(G_stops, o_k, d_k):
            print(f"No path between {o_k} and {d_k}, skipping request")
            continue

        path_nodes = nx.shortest_path(G_stops, source=o_k, target=d_k, weight='weight')

        # ricostruisci anche le linee attraversate
        path_lines = []
        for u, v in zip(path_nodes[:-1], path_nodes[1:]):
            lines = G_stops[u][v]['lines']
            path_lines.append(list(lines))  # può essere più di una linea!

        p_k = np.random.geometric(p=0.6)     # >0, highest probability for requests==1
        requests_list.append({
            "request_id": k,
            "origin": o_k,
            "destination": d_k,
            "path_nodes": path_nodes,
            "path_lines": path_lines,
            "avg_passengers_per_time_unit": p_k
        })

    df_requests = pd.DataFrame(requests_list)
    df_requests.to_csv(output_csv, index=False)
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
print("Graph\n")
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
