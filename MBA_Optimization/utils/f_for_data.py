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
    Returns sets: L, V, S, J, T, A, R, N
    """
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)

    # === Set of lines ===
    L = set(df_lines['ref']) 

    # === Nodes per line ===
    line_nodes = {}
    for _, row in df_lines.iterrows():
        # 'geometry' is a list of ints
        nodes_list = eval(row['geometry']) if isinstance(row['geometry'], str) else row['geometry']
        line_nodes[row['ref']] = nodes_list

    # === Set of nodes ===
    V = set()
    for nodes in line_nodes.values():
        V.update(nodes)

    # === Set of junctions  ===
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for node in nodes:
            node_count[node] += 1
    J = set(node for node, cnt in node_count.items() if cnt >= 2)    # At least intersection between 2 bus lines

    # === Set of terminals ===
    T = set()
    for nodes in line_nodes.values():
        T.add(nodes[0])
        T.add(nodes[-1])

    # === Set of ordinary stops ===
    S = V - J - T

    # === Set of archs ===
    A = set()
    if G_lines:
        for u, v, key, data in G_lines.edges(keys=True, data=True):
            A.add((u, v, data["ref"]))   # uso la linea 'ref' come identificatore
    else:
        for line_ref, nodes in line_nodes.items():
            for i in range(len(nodes)-1):
                u, v = nodes[i], nodes[i+1]
                A.add((u, v, line_ref))


    # === Set of rebalancing arcs ===
    R_nodes = list(T.union(J))
    R = set()
    for i in range(len(R_nodes)):
        for j in range(len(R_nodes)):
            if i != j:
                R.add((R_nodes[i], R_nodes[j]))

    # === Set og segments Nl (segments of the line l) ===
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

    return {
        'L': L,   # insieme delle linee della rete (line IDs)
        'V': V,   # insieme di tutti i nodi della rete (fermate)
        'S': S,   # insieme delle fermate ordinarie (non giunzioni né terminali)
        'J': J,   # insieme delle giunzioni (nodi presenti in ≥2 linee)
        'T': T,   # insieme dei terminali (inizio/fine di ogni linea)
        'A': A,   # insieme degli archi della rete per ogni linea (i,j,line_ref,key)
        'R': R,   # insieme degli archi di ribilanciamento tra terminali e giunzioni
        'N': N    # dizionario: line_ref -> lista dei segmenti (tuple di nodi) tra giunzioni/terminali
    }


# === Caricamento delle richieste ===
# id richiesta, numero persone per richiesta, percorso richiesta
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
    
    K = df_requests['request_id'].tolist()   # Salvataggio ID della richiesta
    p = dict(zip(df_requests['request_id'], df_requests['avg_passengers_per_time_unit']))    # Numero di persone per la richiesta k
    
    Pk = {}    # percorso richiesta
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



# === Travel times ===
# lunghezza / velocità
def assign_travel_times(G, speed_kmh=30):
    """
    Assign travel time (minutes) to edges in a graph.
    Usa direttamente l'attributo 'length' già presente in ogni arco.
    """
    speed_m_per_min = speed_kmh * 1000 / 60  # m/min

    for u, v, key, data in G.edges(keys=True, data=True):
        travel_time = data['length'] / speed_m_per_min
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
