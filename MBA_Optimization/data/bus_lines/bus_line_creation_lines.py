import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random


random.seed(123)


####################
# GENERATE TEST DATA
####################
def create_test_data_cross(n_stops=5, output_folder="data"):
    """
    Generate a minimal transit dataset with 2 lines forming a cross.
    - Each line has `n_stops` stops
    - Lines intersect at a single stop (random index)
    - Saves CSV files for lines and stops
    """
    df_routes_list = []
    df_stops_list = []
    stop_id = 0

    # Choose random intersection index (between 1 and n_stops-2)
    intersection_idx = random.randint(1, n_stops-2)

    # === Line 1: horizontal ===
    coords_line1 = []
    for i in range(n_stops):
        x = i
        y = n_stops // 2  # horizontal line at mid-y
        coords_line1.append(f"{x} {y}")
        df_stops_list.append({
            "stop_id": stop_id,
            "name": f"Stop_{stop_id}",
            "type": "bus_stop",
            "node": stop_id,
            "lon": x,
            "lat": y
        })
        stop_id += 1
    df_routes_list.append({
        "route": "bus",
        "ref": "1",
        "name": "Line 1",
        "geometry": f"LINESTRING ({', '.join(coords_line1)})"
    })

    # === Line 2: vertical ===
    coords_line2 = []
    for i in range(n_stops):
        x = intersection_idx  # vertical line intersects horizontal here
        y = i
        # Reuse stop at intersection (don't create new stop)
        if y == n_stops // 2:
            # find existing stop_id at intersection
            intersection_stop_id = df_stops_list[intersection_idx]['stop_id']
        else:
            df_stops_list.append({
                "stop_id": stop_id,
                "name": f"Stop_{stop_id}",
                "type": "bus_stop",
                "node": stop_id,
                "lon": x,
                "lat": y
            })
            stop_id += 1
        coords_line2.append(f"{x} {y}")
    df_routes_list.append({
        "route": "bus",
        "ref": "2",
        "name": "Line 2",
        "geometry": f"LINESTRING ({', '.join(coords_line2)})"
    })

    # Convert to DataFrames
    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # Save CSV files
    output_routes = f"{output_folder}/line_lines.csv"
    output_stops = f"{output_folder}/line_stops.csv"

    print(f"Saving routes to {output_routes} ...")
    df_routes.to_csv(output_routes, index=False)
    print(f"Saving stops to {output_stops} ...")
    df_stops.to_csv(output_stops, index=False)

    return df_routes, df_stops







def create_lines_graph(output_folder="data"):
    """
    Build a NetworkX graph of stops:
    - Each stop is a node
    - Consecutive stops along lines are connected by edges with weight=1
    Saves the graph as a .gpickle file.
    """
    # Load cross dataset
    df_routes, df_stops = create_test_data_cross(output_folder=output_folder)

    G = nx.Graph()   # directed graph (can later add travel times)

    # Add nodes
    for _, row in df_stops.iterrows():
        G.add_node(row['stop_id'], name=row['name'], lon=row['lon'], lat=row['lat'])

    # Add edges for each line
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        stop_ids_line = []
        for coord in coords_text.split(", "):
            x, y = map(float, coord.split())
            stop_id = df_stops[(df_stops['lon']==x) & (df_stops['lat']==y)]['stop_id'].values[0]
            stop_ids_line.append(stop_id)

        # Add consecutive edges with weight=1
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            G.add_edge(u, v, weight=1)
            

    # Save graph
    graph_file = f"{output_folder}/line_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)

    print(f"Graph saved in {graph_file}")
    return G, df_routes, df_stops


def create_rebalancing_graph(G_lines, df_routes, df_stops, speed_kmh=30, save_path=None):
    """
    Create a rebalancing graph connecting terminals and junctions.
    - G_lines: grafo delle linee (bidirezionale)
    - df_routes, df_stops: dataset delle linee e delle fermate
    - speed_kmh: velocità per calcolo travel_time
    - save_path: percorso per salvare il grafo
    Returns: G_reb (grafo diretto dei rebalancing)
    """
    import math
    speed_m_per_min = (speed_kmh * 1000) / 60  # m/min

    # --- Identifica terminal e junction ---
    line_nodes = {}
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, c.split())) for c in coords_text.split(", ")]
        line_nodes[row['ref']] = coords

    # Terminal = primi e ultimi nodi di ciascuna linea
    T = set()
    for nodes in line_nodes.values():
        T.add(nodes[0])
        T.add(nodes[-1])

    # Junction = nodi condivisi da ≥2 linee
    from collections import defaultdict
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J = set(n for n, cnt in node_count.items() if cnt >= 2)

    # Nodi speciali = terminal + junction
    special_nodes = T.union(J)

    # --- Costruisci grafo di rebalancing ---
    G_reb = nx.DiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['stop_id'] == n].iloc[0]
        G_reb.add_node(n, lon=stop_info['lon'], lat=stop_info['lat'])

    # Aggiungi archi tra tutti i nodi speciali
    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                u_data = G_reb.nodes[u]
                v_data = G_reb.nodes[v]
                dist = math.hypot(v_data['lon'] - u_data['lon'], v_data['lat'] - u_data['lat'])
                travel_time = dist / speed_m_per_min
                G_reb.add_edge(u, v, travel_time=travel_time)

    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved in {save_path}")

    return G_reb, T, J



if __name__ == "__main__":
    # === Generate test dataset ===
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops=3, output_folder="data/bus_lines/") 
    G_lines, df_routes, df_stops = create_lines_graph(output_folder="data/bus_lines/")

    # Crea grafo di rebalancing
    G_reb, T, J = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        speed_kmh=30,
        save_path="data/bus_lines/line_rebalancing_graph.gpickle"
    )

