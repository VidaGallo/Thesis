import pandas as pd
from collections import defaultdict
import networkx as nx
import math
import pickle


def load_sets(lines_csv, stops_csv, G_lines=None):
    """
    Load transit network data and create sets for ILP.
    Assumes 'geometry' column in lines CSV is a list of ints (stop_ids).
    Returns sets: L, V, S, J, T, A, R, N
    """
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)

    # === Lines ===
    L = set(df_lines['ref'])

    # === Nodes per line ===
    line_nodes = {}
    for _, row in df_lines.iterrows():
        # 'geometry' is already list of ints
        nodes_list = eval(row['geometry']) if isinstance(row['geometry'], str) else row['geometry']
        line_nodes[row['ref']] = nodes_list

    # === All nodes ===
    V = set()
    for nodes in line_nodes.values():
        V.update(nodes)

    # === Count appearances → junctions ===
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for node in nodes:
            node_count[node] += 1
    J = set(node for node, cnt in node_count.items() if cnt >= 2)

    # === Terminals ===
    T = set()
    for nodes in line_nodes.values():
        T.add(nodes[0])
        T.add(nodes[-1])

    # === Ordinary stops ===
    S = V - J - T

    # === Line arcs ===
    A = set()
    for line_ref, nodes in line_nodes.items():
        for i in range(len(nodes)-1):
            A.add((nodes[i], nodes[i+1], line_ref))

    # === Rebalancing arcs ===
    R_nodes = list(T.union(J))
    R = set()
    for i in range(len(R_nodes)):
        for j in range(len(R_nodes)):
            if i != j:
                R.add((R_nodes[i], R_nodes[j]))

    # === Segments N ===
    N = {}  # dict: line_ref -> list of segments
    for line_ref, nodes in line_nodes.items():
        seg_list = []
        current_seg = [nodes[0]]
        for node in nodes[1:]:
            current_seg.append(node)
            if node in J or node in T:
                seg_list.append(tuple(current_seg))
                current_seg = [node]
        if len(current_seg) > 1:
            seg_list.append(tuple(current_seg))
        N[line_ref] = seg_list

    # === Optional: map to G_lines if provided ===
    if G_lines is not None:
        # If nodes in V are not already G_lines nodes, map them
        V_new, T_new, J_new, A_new, R_new = set(), set(), set(), set(), set()
        N_new = {}
        for v in V:
            V_new.add(v if v in G_lines.nodes else v)
        for t in T:
            T_new.add(t if t in G_lines.nodes else t)
        for j in J:
            J_new.add(j if j in G_lines.nodes else j)
        for u, v, l in A:
            A_new.add((u if u in G_lines.nodes else u, v if v in G_lines.nodes else v, l))
        for u, v in R:
            R_new.add((u if u in G_lines.nodes else u, v if v in G_lines.nodes else v))
        for line_ref, seg_list in N.items():
            N_new[line_ref] = [tuple(n for n in seg) for seg in seg_list]
        V, T, J, A, R, N = V_new, T_new, J_new, A_new, R_new, N_new

    return {
        'L': L,
        'V': V,
        'S': S,
        'J': J,
        'T': T,
        'A': A,
        'R': R,
        'N': N
    }


def assign_travel_times(G, speed_kmh=30):
    """
    Assign travel time (minutes) to edges in a graph.
    Uses 'length' if available, otherwise Euclidean distance.
    """
    speed_m_per_min = speed_kmh * 1000 / 60  # m/min

    for u, v, data in G.edges(data=True):
        if 'length' in data:
            travel_time = data['length'] / speed_m_per_min
        elif 'lon' in G.nodes[u] and 'lon' in G.nodes[v]:
            x1, y1 = G.nodes[u]['lon'], G.nodes[u]['lat']
            x2, y2 = G.nodes[v]['lon'], G.nodes[v]['lat']
            dist = math.hypot(x2 - x1, y2 - y1)
            travel_time = dist / speed_m_per_min
        else:
            travel_time = 1  # fallback
        data['travel_time'] = travel_time

    return G




if __name__ == "__main__":
    # --- Lines ---
    data_sets_lines = load_sets(
        lines_csv="data/bus_lines/cross/cross_bus_lines.csv",
        stops_csv="data/bus_lines/cross_bus_stops.csv"
    )
    with open("data/bus_lines/cross/cross_bus_line_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open("data/bus_lines/cross/cross_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    G_reb = assign_travel_times(G_reb, speed_kmh=40)
    with open("data/bus_lines/cross/cross_bus_line_graph.gpickle", "wb") as f:
        pickle.dump(G_lines, f)
    with open("data/bus_lines/cross/cross_rebalancing_graph.gpickle", "wb") as f:
        pickle.dump(G_reb, f)

    # --- Grid ---
    data_sets_grid = load_sets(
        lines_csv="data/bus_lines/grid/grid_bus_lines.csv",
        stops_csv="data/bus_lines/grid/grid_bus_stops.csv"
    )
    with open("data/bus_lines/grid/grid_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open("data/bus_lines/grid/grid_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    G_reb = assign_travel_times(G_reb, speed_kmh=40)
    with open("data/bus_lines/grid/grid_bus_lines_graph.gpickle", "wb") as f:
        pickle.dump(G_lines, f)
    with open("data/bus_lines/grid/grid_rebalancing_graph.gpickle", "wb") as f:
        pickle.dump(G_reb, f)

    # --- City ---
    city_name = "Turin"
    data_sets_city = load_sets(
        lines_csv=f"data/bus_lines/city/city_{city_name}_bus_lines_graph.csv",
        stops_csv=f"data/bus_lines/city/city_{city_name}_bus_stops.csv"
    )
    with open(f"data/bus_lines/city/city_{city_name}_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open(f"data/bus_lines/city/city_{city_name}_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    G_reb = assign_travel_times(G_reb, speed_kmh=40)
    with open(f"data/bus_lines/city/city_{city_name}_bus_lines_graph.gpickle", "wb") as f:
        pickle.dump(G_lines, f)
    with open(f"data/bus_lines/city/city_{city_name}_rebalancing_graph.gpickle", "wb") as f:
        pickle.dump(G_reb, f)
