import pandas as pd
from collections import defaultdict
import networkx as nx
import math
import pickle
import json


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
        'L': L,   # insieme delle linee della rete (line IDs)
        'V': V,   # insieme di tutti i nodi della rete (fermate)
        'S': S,   # insieme delle fermate ordinarie (non giunzioni né terminali)
        'J': J,   # insieme delle giunzioni (nodi presenti in ≥2 linee)
        'T': T,   # insieme dei terminali (inizio/fine di ogni linea)
        'A': A,   # insieme degli archi della rete per ogni linea (i,j,line_ref)
        'R': R,   # insieme degli archi di ribilanciamento tra terminali e giunzioni
        'N': N    # dizionario: line_ref -> lista dei segmenti (tuple di nodi) tra giunzioni/terminali
    }



def load_requests(requests_csv, data):
    """
    Carica le richieste da CSV e costruisce K, p e Pk per il MILP.
    
    Parameters:
    requests_csv : Percorso al CSV delle richieste.
    data: Dizionario contenente  'N' e 'L'
    
    Returns:
    K : Lista ID richieste.
    p : Passeggeri per richiesta {k: p_k}.
    Pk : Archi del percorso per richiesta {k: [(i,j,ℓ,h), ...]}.
    """
    df_requests = pd.read_csv(requests_csv)
    
    K = df_requests['request_id'].tolist()
    p = dict(zip(df_requests['request_id'], df_requests['avg_passengers_per_time_unit']))
    
    Pk = {}
    N = data['N']
    L = data['L']
    
    for _, row in df_requests.iterrows():
        k = row['request_id']
        path_nodes = json.loads(row['path_nodes'])
        Pk[k] = []
        
        for i in range(len(path_nodes)-1):
            u, v = path_nodes[i], path_nodes[i+1]
            found = False
            
            # mappa l'arco (u,v) su linea ℓ e segmento h
            for ℓ in L:
                for h, seg in enumerate(N[ℓ]):
                    if u in seg and v in seg:
                        Pk[k].append((u, v, ℓ, h))
                        found = True
                        break
                if found:
                    break
            if not found:
                raise ValueError(f"Arco ({u},{v}) della richiesta {k} non trovato in alcun segmento delle linee disponibili")
    
    return K, p, Pk



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

def compute_segment_travel_times(N, G_lines):
    """
    Restituisce dizionario t[(l,h)] = travel time segmento h della linea l.
    """
    t = {}
    for l, seg_list in N.items():
        for h, seg in enumerate(seg_list):
            seg_time = 0
            for i in range(len(seg)-1):
                u, v = seg[i], seg[i+1]
                if G_lines.has_edge(u,v):
                    seg_time += G_lines[u][v].get('travel_time', 1)  # default 1 se non c'è
                else:
                    seg_time += 1
            t[l,h] = seg_time
    return t









# === FOR TEST ONLY! WILL BE USED IN MAIN ===
if __name__ == "__main__":

    # --- Lines ---
    data_sets_lines = load_sets(
        lines_csv="data/bus_lines/cross/cross_bus_lines.csv",
        stops_csv="data/bus_lines/cross/cross_bus_stops.csv"
    )
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "rb") as f:
        G_lines = pickle.load(f)
    with open("data/bus_lines/cross/cross_rebalancing_graph.gpickle", "rb") as f:
        G_reb = pickle.load(f)
    G_lines = assign_travel_times(G_lines, speed_kmh=35)
    G_reb = assign_travel_times(G_reb, speed_kmh=40)
    with open("data/bus_lines/cross/cross_bus_lines_graph.gpickle", "wb") as f:
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
        lines_csv=f"data/bus_lines/city/city_{city_name}_bus_lines.csv",
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
