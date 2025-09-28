import pandas as pd
from collections import defaultdict


import pandas as pd
from collections import defaultdict
import networkx as nx
import math
import pickle

def load_sets(lines_csv, stops_csv):
    """
    Load transit network data and create sets needed for ILP:
    L: set of lines
    V: set of all nodes
    S: ordinary stops (V \ (T ∪ J))
    J: junctions (nodes where ≥2 lines intersect)
    T: terminals (start/end of each line)
    A: line arcs (consecutive nodes along lines)
    R: rebalancing arcs (between terminals and junctions)
    """
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)

    # Lines
    L = set(df_lines['ref'])

    # Nodes per line
    line_nodes = {}
    for idx, row in df_lines.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, p.split())) for p in coords_text.split(", ")]
        line_nodes[row['ref']] = coords

    # All nodes
    V = set()
    for nodes in line_nodes.values():
        V.update(nodes)

    # Count appearances → junctions
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for node in nodes:
            node_count[node] += 1
    J = set(node for node, cnt in node_count.items() if cnt >= 2)

    # Terminals
    T = set()
    for nodes in line_nodes.values():
        T.add(nodes[0])
        T.add(nodes[-1])

    # Ordinary stops
    S = V - J - T

    # Line arcs
    A = set()
    for line_ref, nodes in line_nodes.items():
        for i in range(len(nodes)-1):
            A.add((nodes[i], nodes[i+1], line_ref))

    # Rebalancing arcs (tra T ∪ J)
    R_nodes = list(T.union(J))
    R = set()
    for i in range(len(R_nodes)):
        for j in range(len(R_nodes)):
            if i != j:
                R.add((R_nodes[i], R_nodes[j]))

    return {
        'L': L,
        'V': V,
        'S': S,
        'J': J,
        'T': T,
        'A': A,
        'R': R
    }


def build_rebalancing_graph(G_lines, R, speed_kmh=30, save_path=None):
    """
    Build a directed rebalancing graph with travel_time as weight.
    G_lines: grafo dei bus/linee originale per ottenere le coordinate.
    R: set di tuple (u, v) che rappresentano gli archi di rebalancing.
    speed_kmh: velocità media dei moduli.
    save_path: se non None, salva il grafo in un file gpickle.
    """
    G_reb = nx.DiGraph()
    speed_m_per_min = speed_kmh * 1000 / 60

    # Aggiungi nodi
    nodes_in_R = set([u for u, v in R] + [v for u, v in R])
    for n in nodes_in_R:
        G_reb.add_node(n, lon=G_lines.nodes[n]['lon'], lat=G_lines.nodes[n]['lat'])

    # Aggiungi archi con travel_time
    for u, v in R:
        x1, y1 = G_lines.nodes[u]['lon'], G_lines.nodes[u]['lat']
        x2, y2 = G_lines.nodes[v]['lon'], G_lines.nodes[v]['lat']
        travel_time = math.hypot(x2 - x1, y2 - y1) / speed_m_per_min
        G_reb.add_edge(u, v, travel_time=travel_time)

    # Salva se richiesto
    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)

    return G_reb



# === Assign travel times to archs along bus lines ===
def assign_travel_times(G, speed_kmh=30):
    """
    Assigns travel time in minutes to each edge.
    - If 'length' exists, compute travel_time = length / speed.
    - Otherwise, compute Euclidean distance from node coordinates if available.
    - If coords are missing, travel_time = 1.
    """
    import math

    speed_m_per_min = (speed_kmh * 1000) / 60  # m/min

    for u, v, data in G.edges(data=True):
        if 'length' in data:
            length = data['length']
            travel_time = length / speed_m_per_min
        elif 'lon' in G.nodes[u] and 'lon' in G.nodes[v]:
            x1, y1 = G.nodes[u]['lon'], G.nodes[u]['lat']
            x2, y2 = G.nodes[v]['lon'], G.nodes[v]['lat']
            dist = math.hypot(x2 - x1, y2 - y1)
            travel_time = dist / speed_m_per_min
        else:
            travel_time = 1    # case line and grid

        data['travel_time'] = travel_time

    return G



# === Creation of rebalancing archs ===
def create_rebalancing_graph(G_lines, speed_kmh=30):
    """
    Create a rebalancing graph connecting terminals and junctions with travel_time as weight.
    """
    # 1. Identifica terminali e junctions
    node_count = {}
    for u, v, data in G_lines.edges(data=True):
        node_count[u] = node_count.get(u, 0) + 1
        node_count[v] = node_count.get(v, 0) + 1

    J = set(n for n, cnt in node_count.items() if cnt >= 2)  # junctions
    T = set()
    for _, row in df_routes.iterrows():
        coords = row['geometry'].replace("LINESTRING (", "").replace(")", "").split(", ")
        T.add(coords[0])
        T.add(coords[-1])
    # converti coords in stop_ids se serve
    T = set(coord_to_stop_id.get(tuple(map(float, c.split())), c) for c in T)
    
    special_nodes = T.union(J)

    # 2. Crea grafo
    G_reb = nx.DiGraph()
    for n in special_nodes:
        G_reb.add_node(n, lon=G_lines.nodes[n]['lon'], lat=G_lines.nodes[n]['lat'])

    # 3. Connetti tutti i nodi speciali
    speed_m_per_min = speed_kmh * 1000 / 60
    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                x1, y1 = G_lines.nodes[u]['lon'], G_lines.nodes[u]['lat']
                x2, y2 = G_lines.nodes[v]['lon'], G_lines.nodes[v]['lat']
                dist = math.hypot(x2 - x1, y2 - y1)
                travel_time = dist / speed_m_per_min
                G_reb.add_edge(u, v, travel_time=travel_time)

    return G_reb, T, J





# === Example of the usage (in the main) ===

### Lines
# Create sets (L, A, ...)
data_sets_lines = load_sets(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv"
)
# Rebalancing graph:
G_reb = build_rebalancing_graph(G_lines, data_sets_lines['R'], speed_kmh=30, save_path="data/bus_lines/rebalancing_graph.gpickle")



### Grid
data_sets_grid = load_sets(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv"
)

### Graph
data_sets_graph = load_sets(
    lines_csv="data/bus_lines/graph_lines_Turin.csv",
    stops_csv="data/bus_lines/graph_stops_Turin.csv"
)