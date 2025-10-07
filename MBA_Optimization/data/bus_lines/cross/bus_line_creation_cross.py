import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
from collections import defaultdict
import math
import numpy as np
import os

random.seed(123)
np.random.seed(123)



# === GENERATE CROSS DATA ===
# Si vuole generare 2 linee di autobus che si intersecano
def create_test_data_cross(n_stops_line=5):
    """
    Generate a minimal transit dataset with 2 lines forming a cross.
    - Each line has `n_stops` stops
    - Lines intersect at a single stop (random index)
    - Saves CSV files for lines and stops
    - 'geometry' column contains a list of stop_ids (integers) representing the bus line
    """
    n_stops = n_stops_line
    df_routes_list = []  
    df_stops_list = []
    stop_id = 0

    # Choose random intersection index (between 1 and n_stops-2)
    intersection_idx = random.randint(1, n_stops-2)    # punto di intersezione

    # === Line 1: horizontal ===
    coords_line1 = []     # si salvano i punti lungo la linea 1
    for i in range(n_stops):
        x = i
        y = n_stops // 2
        stop_name = stop_id
        coords_line1.append(stop_name)
        df_stops_list.append({
            "stop_id": stop_id,
            "name": stop_name,
            "type": "bus_stop",
            "node": stop_name,
            "x": x,
            "y": y
        })
        stop_id += 1
    geometry_closed_1 = coords_line1 + coords_line1[-2::-1]    # Sia andata che ritorno
    df_routes_list.append({
        "route": "bus",
        "ref": "1",
        "name": "Line 1",
        "geometry": geometry_closed_1  
    })

    # === Line 2: vertical ===
    coords_line2 = []
    for i in range(n_stops):
        x = intersection_idx
        y = i
        # reuse intersection stop
        if y == n_stops // 2:
            intersection_stop_name = df_stops_list[intersection_idx]['name']
            coords_line2.append(intersection_stop_name)
        else:
            stop_name = stop_id
            coords_line2.append(stop_name)
            df_stops_list.append({
                "stop_id": stop_id,
                "name": stop_name,
                "type": "bus_stop",
                "node": stop_name,
                "x": x,
                "y": y
            })
            stop_id += 1
    geometry_closed_2 = coords_line2 + coords_line2[-2::-1]    # andata e ritorno
    df_routes_list.append({
        "route": "bus",
        "ref": "2",
        "name": "Line 2",
        "geometry": geometry_closed_2
    })

    # Convert to DataFrames
    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # Save CSV files
    output_routes = f"data/bus_lines/cross/cross_bus_lines.csv"
    output_stops = f"data/bus_lines/cross/cross_bus_stops.csv"

    print(f"Saving routes to {output_routes} ...")
    df_routes.to_csv(output_routes, index=False)
    print(f"Saving stops to {output_stops} ...")
    df_stops.to_csv(output_stops, index=False)

    return df_routes, df_stops




# === CREATE LINES GRAPH ===
# Si vuole creare un grafo delle line degli autobus
def create_lines_graph(df_routes, df_stops):
    """
    Build a NetworkX MULTIDIGRAPH of stops:
    - Each stop is a node (integer)
    - Consecutive stops along lines are connected by directed edges
    - Allows multiple edges (multi-lines between same nodes)
    - Saves the graph as a .gpickle file
    """
    G = nx.MultiDiGraph()   # Multi-Directed Graph

    # Add nodes using stop_id (integer)
    for _, row in df_stops.iterrows():
        G.add_node(int(row['name']), x=row['x'], y=row['y'])

    # Add edges along each line
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']   # Geometry contiene tutti gli stop di una determinata linea di bus
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            # distanza euclidea tra le coordinate dei due stop
            x1, y1 = df_stops.loc[df_stops['name']==u, ['x','y']].values[0]
            x2, y2 = df_stops.loc[df_stops['name']==v, ['x','y']].values[0]
            length = math.dist((x1, y1), (x2, y2))

            # aggiungo due archi direzionali (andata/ritorno) con attributo ref=linea
            G.add_edge(u, v, weight=1, length=length, ref=row['ref'])
            G.add_edge(v, u, weight=1, length=length, ref=row['ref'])

    # Save graph
    graph_file = f"data/bus_lines/cross/cross_bus_lines_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved in {graph_file}")

    return G, df_routes, df_stops



# === CREATE SIMPLE GRAPH G_bar ===
# Serve per definire i cammini dei passeggeri (no multiarci, solo un arco se almeno una linea collega due nodi)
def create_G_bar(G_lines, save_path=None):
    """
    Crea il grafo semplice G_bar a partire dal MultiDiGraph G_lines.
    - I nodi restano gli stessi
    - Se due nodi sono collegati da almeno una linea, aggiungo un arco unico
    - Se più linee collegano gli stessi nodi, tengo la lunghezza minima
    """
    G_bar = nx.Graph()

    # Copio i nodi con gli stessi attributi
    for n, data in G_lines.nodes(data=True):
        G_bar.add_node(n, **data)

    # Aggiungo un arco unico per ogni coppia di nodi collegati
    for u, v, data in G_lines.edges(data=True):
        length = data.get("length", 1.0)
        if G_bar.has_edge(u, v):
            if length < G_bar[u][v]["length"]:
                G_bar[u][v]["length"] = length
        else:
            G_bar.add_edge(u, v, length=length)

    # Salvo il grafo se richiesto
    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_bar, f)
        print(f"G_bar saved as {save_path}")

    return G_bar





# === CREATE REBALANCING GRAPH ===
# Creazione del grafo degli archi aggiuntivi che possono fungere da percorsi per i moduli vuoti quando devono essere ribilanciati
def create_rebalancing_graph(G, df_routes, df_stops, save_path=None):
    """
    Create a directed MULTIDIGRAPH connecting terminals and junctions.
    - Terminals: first and last stop of each line
    - Junctions: stops shared by multiple lines
    """
    line_nodes = {row['ref']: row['geometry'] for _, row in df_routes.iterrows()}

    ### Terminals
    # Primo nodo + eventualmente quello che compare una sola volta (es.1e3 in 1-2-3-2-1)
    T_nodes = set()
    for nodes in line_nodes.values():
        counts = defaultdict(int)
        for n in nodes:
            counts[n] += 1
        # Prendi sempre il primo nodo
        terminals_line = [nodes[0]]
        # Aggiungi eventuali nodi che compaiono una sola volta
        terminals_line += [n for n, c in counts.items() if c == 1 and n != nodes[0]]
        T_nodes.update(terminals_line)


    ### Junctions (dove si intersecano almeno 2 linee)
    node_in_lines = defaultdict(set)
    for line_ref, nodes in line_nodes.items():
        for n in set(nodes):  # conta ogni nodo una sola volta per linea
            node_in_lines[n].add(line_ref)
    J_nodes = set(n for n, lines in node_in_lines.items() if len(lines) >= 2)


    ### T U J
    special_nodes = T_nodes.union(J_nodes)    # Nodi dove può avvenire il ribilanciamento

    # Build directed MULTIDIGRAPH
    G_reb = nx.MultiDiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['name']==n].iloc[0]
        G_reb.add_node(n, x=stop_info['x'], y=stop_info['y'])    # Aggiungiamo il nodo se è "special"

    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
                x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
                length = math.dist((x1, y1), (x2, y2))
                G_reb.add_edge(u, v, weight=1, length=length)   # Aggiungiamo i vari archi tra tutti questi nodi

    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved as {save_path}")

    return G_reb


# === CREATION of the FULL GRAPH G ===
def create_full_graph(G_lines, G_reb, save_path=None):
    """
    Unisce il grafo delle linee (G_lines) e quello di rebalancing (G_reb)
    in un unico MultiDiGraph G_full.
    Ogni arco è etichettato come 'line' o 'rebalancing'.
    """
    G_full = nx.MultiDiGraph()

    # === NODI ===
    # Copio i nodi da entrambi i grafi
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

    # === Salvataggio opzionale ===
    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_full, f)
        print(f"G_full saved as {save_path}")

    return G_full



# === PLOT GRAPHS ===
# Visualizzazione dei grafi delle linee bus e linee di rebalance
def plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing", save_fig=False):
    """
    Plot the bus line graph and rebalancing graph.
    Shows node labels (stop IDs) to identify terminals and junctions.
    If save_fig=True, saves the figure as a .png in the same folder as this script.
    """
    plt.figure(figsize=(8, 8))

    # === Plot bus lines ===
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['name'] == name]['x'].values[0],
                   df_stops[df_stops['name'] == name]['y'].values[0])
                  for name in stop_ids_line]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=f"Line {row['ref']}", linewidth=2)

    # === Plot all stops ===
    xs = [row['x'] for _, row in df_stops.iterrows()]
    ys = [row['y'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', zorder=5, s=60, label="Stops")

    # === Add node labels (stop IDs) ===
    for _, row in df_stops.iterrows():
        x, y = row['x'], row['y']
        stop_id = row['name']
        plt.text(x + 0.04, y + 0.04, str(stop_id), fontsize=11, color='black', weight='bold')

    # === Plot rebalancing arcs ===
    for u, v, key in G_reb.edges(keys=True):
        x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
        x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
        plt.arrow(x1, y1, x2 - x1, y2 - y1,
                  color='green', alpha=0.4,
                  length_includes_head=True,
                  head_width=0.05, head_length=0.05)

    # === Layout ===
    plt.title(title, fontsize=14)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.axis("equal")

    # === Salvataggio ===
    if save_fig:
        save_dir = f"C:/Users/vidag/Documents/UNIVERSITA/TESI/code/Thesis/MBA_Optimization/data/bus_lines/cross"
        filename = title.replace(" ", "_").lower() + ".png"
        full_path = os.path.join(save_dir, filename)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')

    plt.show()





# === MAIN ===
if __name__ == "__main__":
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops_line=3)
    G_lines, df_routes, df_stops = create_lines_graph(df_routes, df_stops)

    # Crea grafo semplice G_bar per i cammini passeggeri
    G_bar = create_G_bar(
        G_lines,
        save_path="data/bus_lines/cross/cross_Gbar_graph.gpickle"
    )

    # Create rebalancing graph
    G_reb = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path="data/bus_lines/cross/cross_rebalancing_graph.gpickle"
    )

    # === Create unified graph G_full (lines + rebalancing) ===
    G_full = create_full_graph(
        G_lines,
        G_reb,
        save_path="data/bus_lines/cross/cross_G_graph.gpickle"
    )
    # Plot graphs
    plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Cross Transit + Rebalancing", save_fig=True)
    print("Finish")
