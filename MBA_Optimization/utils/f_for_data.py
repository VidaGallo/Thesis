import pandas as pd
from collections import defaultdict
import networkx as nx
import math
import pickle
import json


# === DATA LOADER ===
# Load data and generate the sets needed to solve the model
def load_sets(lines_csv, stops_csv, G_lines=None):
    """
    Load transit network data and create sets for ILP.
    Assumes 'geometry' column in lines CSV is a list of ints (stop_ids).
    Returns sets: L, V, S, J, T, A, R, Nl
    """
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)

    # === Set of lines ===
    L = set(df_lines['ref']) 

    # === Nodes per line ===
    line_nodes = {}
    for _, row in df_lines.iterrows():
        nodes_list = eval(row['geometry']) if isinstance(row['geometry'], str) else row['geometry']
        line_nodes[row['ref']] = nodes_list

    # === Set of nodes ===
    V = set()
    for nodes in line_nodes.values():
        V.update(nodes)

    # === Junctions ===
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

    # === Arcs A ===
    A = set()
    if G_lines:
        for u, v, key, data in G_lines.edges(keys=True, data=True):
            A.add((u, v, data["ref"]))
    else:
        for line_ref, nodes in line_nodes.items():
            for i in range(len(nodes)-1):
                u, v = nodes[i], nodes[i+1]
                A.add((u, v, line_ref))

    # === Rebalancing arcs R ===
    R_nodes = list(T.union(J))
    R = set()
    for i in range(len(R_nodes)):
        for j in range(len(R_nodes)):
            if i != j:
                R.add((R_nodes[i], R_nodes[j]))

    # === Segments Nl ===
    Nl = {}  # dict: line_ref -> list of segments (tuple of nodes)
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
        Nl[line_ref] = seg_list

    return {
        'L': L,   # linee
        'V': V,   # nodi
        'S': S,   # fermate ordinarie
        'J': J,   # giunzioni
        'T': T,   # terminali
        'A': A,   # archi (i,j,ℓ)
        'R': R,   # archi di ribilanciamento
        'Nl': Nl  # segmenti N_l
    }



# === Caricamento delle richieste ===
# id richiesta, numero persone per richiesta, percorso richiesta
def load_requests(requests_csv, data):
    """
    Carica le richieste da CSV e costruisce:
    - K: lista ID richieste
    - p: passeggeri per richiesta {k: p_k}
    - Pk: path come lista di nodi [n0,...,nm]
    - Pkl: archi del path k mappati su linee (i,j,h)
    - Blk: triple (i,j,m) consecutive sul path k servite dalla stessa linea ℓ
    """
    df_requests = pd.read_csv(requests_csv)

    K = df_requests['request_id'].tolist()
    p = dict(zip(df_requests['request_id'], df_requests['avg_passengers_per_time_unit']))

    Nl = data['Nl']
    L  = data['L']
    A  = data['A']

    Pk  = {}
    Pkl = {}
    
    ok = {}
    dk = {}
    Blk = defaultdict(list)

    # Dizionario rapido: (i,j) -> linee che coprono quell'arco
    L_ij = defaultdict(set)
    for (i, j, ell) in A:
        L_ij[(i, j)].add(ell)

    for _, row in df_requests.iterrows():
        k = row['request_id']
        path_nodes = json.loads(row['path_nodes'])

        # === Origine e destinazione ===
        ok[k] = path_nodes[0]
        dk[k] = path_nodes[-1]

        # === Pk: lista di nodi ===
        Pk[k] = path_nodes

        # === Pkl: archi mappati su linee ===
        for i in range(len(path_nodes)-1):
            u, v = path_nodes[i], path_nodes[i+1]
            found = False
            for ℓ in L:
                for h, seg in enumerate(Nl[ℓ]):
                    if u in seg and v in seg:
                        Pkl.setdefault((k, ℓ), []).append((u, v, h))
                        found = True
                        break
                if found:
                    break
            if not found:
                raise ValueError(f"Arco ({u},{v}) della richiesta {k} non trovato in alcuna linea")

        # === Blk: triple consecutive (i,j,m) sul path k ===
        for t in range(1, len(path_nodes)-1):
            i, j, m = path_nodes[t-1], path_nodes[t], path_nodes[t+1]

            # escludi se j è origine o destinazione di quella richiesta
            if j == ok[k] or j == dk[k]:
                continue

            common_lines = L_ij.get((i, j), set()) & L_ij.get((j, m), set())
            for l in common_lines:
                Blk[(l, k)].append((i, j, m))

    return K, p, Pk, Pkl, Blk



def build_delta_sets(Nl, J, T):
    """
    Costruisce Δ⁺(j) e Δ⁻(j) per tutti j in T∪J.
    - Δ⁺(j): segmenti (ℓ,h) che partono da j
    - Δ⁻(j): segmenti (ℓ,h) che arrivano a j
    """
    from collections import defaultdict
    Delta_plus = defaultdict(set)
    Delta_minus = defaultdict(set)

    for ell, seg_list in Nl.items():
        for h, seg in enumerate(seg_list):
            start, end = seg[0], seg[-1]
            if start in J or start in T:
                Delta_plus[start].add((ell, h))
            if end in J or end in T:
                Delta_minus[end].add((ell, h))
    return Delta_plus, Delta_minus



# === Travel times ===
# lunghezza / velocità
def assign_travel_times(G, speed_kmh=30):
    """
    Assign travel time (minutes) to edges in a graph.
    Usa direttamente l'attributo 'length' già presente in ogni arco.
    """
    speed_m_per_s = speed_kmh * 1000 / 3600  # m/s

    for u, v, key, data in G.edges(keys=True, data=True):
        travel_time = data['length'] / speed_m_per_s
        data['travel_time'] = travel_time

        # Imposta travel_time anche come peso standard dell'arco
        data['weight'] = travel_time  

    return G


# === Segment travel time ===
# lunghezza / velocità
def compute_segment_travel_times(N, G_lines):
    """
    Restituisce dizionario t[(ℓ,h)] = travel time del segmento h della linea ℓ.
    Somma i travel_time degli archi consecutivi.
    """
    t = {}
    for ℓ, seg_list in N.items():
        for h, seg in enumerate(seg_list):
            seg_time = 0
            for i in range(len(seg)-1):
                u, v = seg[i], seg[i+1]
                if G_lines.has_edge(u, v):
                    first_key = list(G_lines[u][v].keys())[0]
                    seg_time += G_lines[u][v][first_key]['travel_time']
            t[ℓ, h] = seg_time
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
    print(type(G_lines))
    print(type(G_reb))
    print("ok cross")
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
    print(type(G_lines))
    print(type(G_reb))
    print("ok grid")
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
    print(type(G_lines))
    print(type(G_reb))
    print("ok city")
    with open(f"data/bus_lines/city/city_{city_name}_bus_lines_graph.gpickle", "wb") as f:
        pickle.dump(G_lines, f)
    with open(f"data/bus_lines/city/city_{city_name}_rebalancing_graph.gpickle", "wb") as f:
        pickle.dump(G_reb, f)
