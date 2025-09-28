import pandas as pd
from collections import defaultdict


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
    # === Load CSVs ===
    df_lines = pd.read_csv(lines_csv)
    df_stops = pd.read_csv(stops_csv)

    # === Set of lines ===
    L = set(df_lines['ref'])
    
    # === Nodes per line ===
    line_nodes = {}  # line_ref -> list of node ids
    for idx, row in df_lines.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, p.split())) for p in coords_text.split(", ")]
        line_nodes[row['ref']] = coords
    
    # === All nodes V ===
    V = set()
    for nodes in line_nodes.values():
        V.update(nodes)
    
    # === Count nodes appearances to find junctions ===
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for node in nodes:
            node_count[node] += 1
    J = set(node for node, cnt in node_count.items() if cnt >= 2)
    
    # === Terminals: first and last node of each line ===
    T = set()
    for nodes in line_nodes.values():
        T.add(nodes[0])
        T.add(nodes[-1])
    
    # === Ordinary stops S ===
    S = V - J - T
    
    # === Line arcs A ===
    A = set()
    for line_ref, nodes in line_nodes.items():
        for i in range(len(nodes)-1):
            A.add((nodes[i], nodes[i+1], line_ref))
    
    # === Rebalancing arcs R ===
    # Gli archi di rebalancing sono connessioni tra nodi “speciali”, cioè terminal o junctions, 
    # lungo le quali i moduli possono spostarsi senza seguire la linea.
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

# Example of the usage (for the main)
if __name__ == "__main__":
    data_sets = load_sets(
        lines_csv="data/bus_lines/input_data_line_lines.csv",
        stops_csv="data/bus_lines/input_data_line_stops.csv"
    )
    
    print("Lines (L):", data_sets['L'])
    print("All nodes (V):", data_sets['V'])
    print("Ordinary stops (S):", data_sets['S'])
    print("Junctions (J):", data_sets['J'])
    print("Terminals (T):", data_sets['T'])
    print("Number of line arcs (A):", len(data_sets['A']))
    print("Number of rebalancing arcs (R):", len(data_sets['R']))