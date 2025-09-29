import pandas as pd
from collections import defaultdict
import networkx as nx
import math
import pickle





def load_sets(lines_csv, stops_csv, G_lines=None):
    """
    Load transit network data and create sets needed for ILP.
    If G_lines is provided, nodes' coordinates are taken from the graph.
    Returns sets: L, V, S, J, T, A, R, N
    """
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)


    # === Lines ===
    L = set(df_lines['ref'])


    # === Nodes per line ===
    line_nodes = {}
    for _, row in df_lines.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, p.split())) for p in coords_text.split(", ")]
        line_nodes[row['ref']] = coords


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
            # close segment if junction or terminal
            if node in J or node in T:
                seg_list.append(tuple(current_seg))
                current_seg = [node]  # start new segment from here
        if len(current_seg) > 1:  # if something remains
            seg_list.append(tuple(current_seg))
        N[line_ref] = seg_list


    # === Optional: use G_lines to attach coordinates ===
    if G_lines is not None:
        coord_to_stop = { (data['lon'], data['lat']): n for n, data in G_lines.nodes(data=True) }
        V_new, T_new, J_new, A_new, R_new = set(), set(), set(), set(), set()
        N_new = {}
        for v in V:
            V_new.add(coord_to_stop.get(v, v))
        for t in T:
            T_new.add(coord_to_stop.get(t, t))
        for j in J:
            J_new.add(coord_to_stop.get(j, j))
        for u, v, l in A:
            A_new.add((coord_to_stop.get(u, u), coord_to_stop.get(v, v), l))
        for u, v in R:
            R_new.add((coord_to_stop.get(u, u), coord_to_stop.get(v, v)))
        # Segments with mapped nodes
        for line_ref, seg_list in N.items():
            N_new[line_ref] = [tuple(coord_to_stop.get(n, n) for n in seg) for seg in seg_list]
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



# === Assign travel times to archs along bus lines/rebalancing archs ===
def assign_travel_times(G, speed_kmh=30):
    """
    Assign travel time (in minutes) to edges of a graph.
    """
    speed_m_per_min = speed_kmh * 1000 / 60  # m/min

    for u, v, data in G.edges(data=True):
        # 1. Use 'length' if available
        if 'length' in data:
            travel_time = data['length'] / speed_m_per_min
        # 2. Otherwise, use Euclidean distance if coordinates exist
        elif 'lon' in G.nodes[u] and 'lon' in G.nodes[v]:
            x1, y1 = G.nodes[u]['lon'], G.nodes[u]['lat']
            x2, y2 = G.nodes[v]['lon'], G.nodes[v]['lat']
            dist = math.hypot(x2 - x1, y2 - y1)
            travel_time = dist / speed_m_per_min
        else:
            travel_time = 1  # fallback
        data['travel_time'] = travel_time

    return G





### Lines
# Create sets (L, A, ...)
data_sets_lines = load_sets(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv"
)
# Assign travel times to bus line graph and rebalancing graph
with open("data/bus_lines/line_graph.gpickle", "rb") as f:
    G_lines = pickle.load(f)
with open("data/bus_lines/line_rebalancing_graph.gpickle", "rb") as f:
    G_reb = pickle.load(f)
G_lines = assign_travel_times(G_lines, speed_kmh=35)  # average bus speed
G_reb = assign_travel_times(G_reb, speed_kmh=40)  # average rebalancing speed

# Save the new graph with time
with open("data/bus_lines/line_graph.gpickle", "wb") as f:
    pickle.dump(G_lines, f)
with open("data/bus_lines/line_rebalancing_graph.gpickle", "wb") as f:
    pickle.dump(G_reb, f)



### Grid
data_sets_grid = load_sets(
    lines_csv="data/bus_lines/line_lines.csv",
    stops_csv="data/bus_lines/line_stops.csv"
)
# Assign travel times to bus line graph and rebalancing graph
with open("data/bus_lines/grid_graph.gpickle", "rb") as f:
    G_lines = pickle.load(f)
with open("data/bus_lines/grid_rebalancing_graph.gpickle", "rb") as f:
    G_reb = pickle.load(f)
G_lines = assign_travel_times(G_lines, speed_kmh=35)  # average bus speed
G_reb = assign_travel_times(G_reb, speed_kmh=40)  # average rebalancing speed

# Save the new graph with time
with open("data/bus_lines/grid_graph.gpickle", "wb") as f:
    pickle.dump(G_lines, f)
with open("data/bus_lines/grid_rebalancing_graph.gpickle", "wb") as f:
    pickle.dump(G_reb, f)



### Graph
data_sets_graph = load_sets(
    lines_csv="data/bus_lines/graph_lines_Turin.csv",
    stops_csv="data/bus_lines/graph_stops_Turin.csv"
)
# Assign travel times to bus line graph and rebalancing graph
with open("data/bus_lines/city_graph.gpickle", "rb") as f:
    G_lines = pickle.load(f)
with open("data/bus_lines/graph_rebalancing_graph.gpickle", "rb") as f:
    G_reb = pickle.load(f)
G_lines = assign_travel_times(G_lines, speed_kmh=35)  # average bus speed
G_reb = assign_travel_times(G_reb, speed_kmh=40)  # average rebalancing speed

# Save the new graph with time
with open("data/bus_lines/graph_graph.gpickle", "wb") as f:
    pickle.dump(G_lines, f)
with open("data/bus_lines/graph_rebalancing_graph.gpickle", "wb") as f:
    pickle.dump(G_reb, f)