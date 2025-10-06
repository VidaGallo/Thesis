import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
from collections import defaultdict
import os
import math
import numpy as np

random.seed(123)
np.random.seed(123)



# === CREATE GRID TEST DATA ===
# Creazione di linee di autobus disposte su una GRIGLIA
def create_grid_test_data(n_lines=4, n_stops=5, grid_size=5):
    """
    Generate a grid-like transit network:
    - n_lines lines
    - n_stops per line
    - Node IDs are integers
    - 'geometry' column contains a list of node_ids
    """
    os.makedirs("data/bus_lines/grid", exist_ok=True)

    df_routes_list = []
    df_stops_list = []
    stop_positions = {}  # map (x,y) -> node_id
    line_nodes = {}
    node_id = 0
    directions = [(1,0), (-1,0), (0,1), (0,-1)]  # mosse possibili (dx, sx, su, giù)

    line_idx = 1
    max_retries = 200

    while line_idx <= n_lines and max_retries > 0:
        if line_idx == 1:
            x, y = random.randint(1, grid_size), random.randint(1, grid_size)
        else:
            x, y = random.choice(list(stop_positions.keys()))

        stops = [(x, y)]
        candidate_nodes = set([(x, y)])

        for _ in range(1, n_stops):
            last_move = (stops[-1][0]-stops[-2][0], stops[-1][1]-stops[-2][1]) if len(stops) > 1 else (0,0)
            probs = [0.6 if (dx, dy)==last_move else 0.4/3 for dx, dy in directions]
            for _ in range(10):
                dx, dy = random.choices(directions, weights=probs)[0]
                nx_coord = max(1, min(grid_size, stops[-1][0]+dx))
                ny_coord = max(1, min(grid_size, stops[-1][1]+dy))
                if (nx_coord, ny_coord) not in stops:
                    stops.append((nx_coord, ny_coord))
                    candidate_nodes.add((nx_coord, ny_coord))
                    break

        too_much_overlap = False
        has_intersection = (line_idx == 1)
        for nodes in line_nodes.values():
            shared = candidate_nodes & nodes
            if len(shared) > 2:
                too_much_overlap = True
                break
            if len(shared) >= 1:
                has_intersection = True

        if too_much_overlap or not has_intersection:
            max_retries -= 1
            continue

        line_nodes[line_idx] = candidate_nodes
        node_ids_line = []

        for x, y in stops:
            if (x, y) not in stop_positions:
                stop_positions[(x, y)] = node_id
                df_stops_list.append({
                    "stop_id": node_id,
                    "name": node_id,
                    "type": "bus_stop",
                    "node": node_id,
                    "x": x,
                    "y": y
                })
                node_id += 1
            node_ids_line.append(stop_positions[(x, y)])

        # Save line as list of integers
        geometry_closed = node_ids_line + node_ids_line[-2::-1]   # andata e ritorno
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": f"Line {line_idx}",
            "geometry": geometry_closed 
        })

        line_idx += 1

    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    df_routes.to_csv("data/bus_lines/grid/grid_bus_lines.csv", index=False)
    df_stops.to_csv("data/bus_lines/grid/grid_bus_stops.csv", index=False)

    return df_routes, df_stops



# === CREATE GRID GRAPH ===
def create_grid_graph(df_routes, df_stops, save_path="data/bus_lines/grid/grid_bus_lines_graph.gpickle"):
    """
    Build a NetworkX MULTIDIGRAPH for the grid:
    - Nodes are integers
    - Consecutive stops along lines are connected
    - Each edge has a 'length' attribute (euclidean distance)
    """
    G = nx.MultiDiGraph()
    for _, row in df_stops.iterrows():
        G.add_node(row['node'], x=row['x'], y=row['y'])

    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']  # already list of ints
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
            x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
            length = math.dist((x1, y1), (x2, y2))  # distanza euclidea sulla griglia

            # aggiungo archi in entrambe le direzioni con attributo length
            G.add_edge(u, v, weight=1, length=length)
            G.add_edge(v, u, weight=1, length=length)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        pickle.dump(G, f)
    print(f"Grid graph saved as {save_path}")
    return G


# === CREATE SIMPLE GRAPH G_bar ===
def create_G_bar(G_lines, save_path="data/bus_lines/grid/grid_Gbar_graph.gpickle"):
    """
    Crea il grafo semplice G_bar a partire dal MultiDiGraph G_lines.
    - I nodi restano identici
    - Se due nodi sono collegati da almeno una linea, aggiungo un arco unico
    - Se più linee collegano la stessa coppia, tengo la lunghezza minima
    """
    G_bar = nx.Graph()

    # Copio i nodi con attributi
    for n, data in G_lines.nodes(data=True):
        G_bar.add_node(n, **data)

    # Aggiungo un solo arco per ogni coppia di nodi
    for u, v, data in G_lines.edges(data=True):
        length = data.get("length", 1.0)
        if G_bar.has_edge(u, v):
            if length < G_bar[u][v]["length"]:
                G_bar[u][v]["length"] = length
        else:
            G_bar.add_edge(u, v, length=length)

    # Salva se richiesto
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(G_bar, f)
        print(f"G_bar saved as {save_path}")

    return G_bar



# === CREATE REBALANCING GRAPH ===
def create_grid_rebalancing_graph(G, df_routes, df_stops, save_path="data/bus_lines/grid/grid_rebalancing_graph.gpickle"):
    """
    Create directed MULTIDIGRAPH for terminals/junctions
    - Each edge has a 'length' attribute (euclidean distance)
    """
    line_nodes = {row['ref']: row['geometry'] for _, row in df_routes.iterrows()}

    ### Terminals
    # Nodi che appaiono una sola volta nella linea (es. 1 e 3 in 1-2-3-2-1)
    T_nodes = set()
    for nodes in line_nodes.values():
        counts = defaultdict(int)
        for n in nodes:
            counts[n] += 1
        terminals_line = [n for n, c in counts.items() if c == 1]
        # Se tutti i nodi appaiono due volte (loop puro), prendo almeno il primo
        if not terminals_line and len(nodes) > 0:
            terminals_line = [nodes[0]]
        T_nodes.update(terminals_line)

    ### Junctions = shared stops
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_nodes = set(n for n, cnt in node_count.items() if cnt >= 2)

    ### T U J
    special_nodes = T_nodes.union(J_nodes)

    G_reb = nx.MultiDiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['node'] == n].iloc[0]
        G_reb.add_node(n, x=stop_info['x'], y=stop_info['y'])

    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
                x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
                length = math.dist((x1, y1), (x2, y2))

                # aggiungo arco diretto con length
                G_reb.add_edge(u, v, weight=1, length=length)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        pickle.dump(G_reb, f)
    print(f"Rebalancing graph saved as {save_path}")

    return G_reb



# === CREATION of the FULL GRAPH G ===
def create_full_grid_graph(G_lines, G_reb, save_path="data/bus_lines/grid/grid_Gfull_graph.gpickle"):
    """
    Crea il grafo completo G_full unendo:
    - gli archi delle linee bus (G_lines)
    - gli archi di rebalancing (G_reb)
    Tutti i nodi condivisi; ogni arco ha attributo 'type' ('line' o 'rebalancing').
    """
    G_full = nx.MultiDiGraph()

    # === NODI ===
    for n, data in G_lines.nodes(data=True):
        G_full.add_node(n, **data)
    for n, data in G_reb.nodes(data=True):
        if n not in G_full:
            G_full.add_node(n, **data)

    # === ARCHI DELLE LINEE ===
    for u, v, key, data in G_lines.edges(keys=True, data=True):
        edge_data = data.copy()
        edge_data["type"] = "line"
        edge_data["ref"] = data.get("ref")
        G_full.add_edge(u, v, key=f"line_{edge_data['ref']}_{key}", **edge_data)

    # === ARCHI DI REBALANCING ===
    for u, v, key, data in G_reb.edges(keys=True, data=True):
        edge_data = data.copy()
        edge_data["type"] = "rebalancing"
        edge_data["ref"] = None
        G_full.add_edge(u, v, key=f"reb_{key}", **edge_data)

    # === Salvataggio ===
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(G_full, f)
        print(f"G_full saved as {save_path}")

    return G_full




# === PLOT GRID TRANSIT ===
def plot_grid_transit(G_lines, G_reb, df_routes, df_stops,
                      title="Grid Transit + Rebalancing", save_fig=False):
    """
    Plot the grid bus network and rebalancing graph.
    If save_fig=True, saves the plot as .png in the folder:
    C:/Users/vidag/Documents/UNIVERSITA/TESI/code/Thesis/MBA_Optimization/data/bus_lines/grid
    """
    plt.figure(figsize=(8,8))
    # Plot bus lines
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['node']==n]['x'].values[0],
                   df_stops[df_stops['node']==n]['y'].values[0]) for n in stop_ids_line]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)

    # Plot all stops
    xs = [row['x'] for _, row in df_stops.iterrows()]
    ys = [row['y'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', s=50, zorder=5, label="Stops")

    # Plot rebalancing arcs
    for u, v in G_reb.edges():
        x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
        x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
        plt.arrow(x1, y1, x2-x1, y2-y1, color='grey', alpha=0.5,
                  length_includes_head=True, head_width=0.1, head_length=0.1)

    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)

    # === Salvataggio ===
    if save_fig:
        save_dir = f"C:/Users/vidag/Documents/UNIVERSITA/TESI/code/Thesis/MBA_Optimization/data/bus_lines/grid"
        filename = title.replace(" ", "_").lower() + ".png"
        full_path = os.path.join(save_dir, filename)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')

    plt.show()




# === MAIN ===
if __name__ == "__main__":
    print("Generating grid test dataset...")
    df_routes, df_stops = create_grid_test_data(n_lines=4, n_stops=6, grid_size=8)

    G_lines = create_grid_graph(df_routes, df_stops)
    G_bar = create_G_bar(G_lines, save_path="data/bus_lines/grid/grid_Gbar_graph.gpickle")
    G_reb = create_grid_rebalancing_graph(G_lines, df_routes, df_stops)

    plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Grid Transit + Rebalancing", save_fig=True)
    print("Finish")