import pandas as pd


def load_transit_data(lines_file, stops_file):
    """
    Load transit network data from CSV files and build sets for the ILP model.
    """
    # === Load CSVs ===
    df_routes = pd.read_csv(lines_file)
    df_stops = pd.read_csv(stops_file)

    # === Sets of nodes and lines ===
    V = set(df_stops["node"])                       # all nodes
    L = set(df_routes["ref"])                       # all lines

    # === Extract arcs (A) from line geometries ===
    A = []
    for _, row in df_routes.iterrows():
        line_id = row["ref"]
        coords_text = row["geometry"].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, p.split())) for p in coords_text.split(", ")]
        nodes = df_stops[df_stops[["lon", "lat"]].apply(tuple, axis=1).isin(coords)]["node"].tolist()

        # Build arcs as consecutive pairs (i,j,l)
        for i in range(len(nodes)-1):
            A.append((nodes[i], nodes[i+1], line_id))

    # === Terminals (first/last stops of each line) ===
    T = set()
    for line in L:
        nodes_line = [a for a in A if a[2] == line]
        if nodes_line:
            T.add(nodes_line[0][0])        # first node
            T.add(nodes_line[-1][1])       # last node

    # === Junctions (nodes shared by ≥ 2 lines) ===
    node_to_lines = {}
    for (i, j, l) in A:
        node_to_lines.setdefault(i, set()).add(l)
        node_to_lines.setdefault(j, set()).add(l)
    J = {n for n, lines in node_to_lines.items() if len(lines) > 1}

    # === Ordinary stops ===
    S = V - (T | J)

    # === Rebalancing arcs (R) between T ∪ J) ===
    TJ = list(T | J)
    R = {(i, j) for i in TJ for j in TJ if i != j}

    return {
        "V": V,
        "L": L,
        "A": A,
        "T": T,
        "J": J,
        "S": S,
        "R": R,
        "df_routes": df_routes,
        "df_stops": df_stops
    }
