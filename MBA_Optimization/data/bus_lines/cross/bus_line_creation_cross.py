import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
from collections import defaultdict
import math
import numpy as np

random.seed(123)
np.random.seed(123)



# === GENERATE CROSS DATA ===
# Si vuole generare 2 linee di autobus che si itnersecano, ciascuna con n_stops = 5
def create_test_data_cross(n_stops=5):
    """
    Generate a minimal transit dataset with 2 lines forming a cross.
    - Each line has `n_stops` stops
    - Lines intersect at a single stop (random index)
    - Saves CSV files for lines and stops
    - 'geometry' column contains a list of stop_ids (integers)
    """
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
    df_routes_list.append({
        "route": "bus",
        "ref": "1",
        "name": "Line 1",
        "geometry": coords_line1  
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
    df_routes_list.append({
        "route": "bus",
        "ref": "2",
        "name": "Line 2",
        "geometry": coords_line2
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

    # Terminals (primo e ultimo nodo della linea)
    T_nodes = set()
    for nodes in line_nodes.values():
        T_nodes.add(nodes[0])
        T_nodes.add(nodes[-1])

    # Junctions (dove si intersecano almeno 2 linee)
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_nodes = set(n for n, cnt in node_count.items() if cnt >= 2)

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




# === PLOT GRAPHS ===
# Visualizzazione dei grafi delle linee bus e linee di rebalance
def plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing"):
    """
    Plot the bus line graph and rebalancing graph
    """
    plt.figure(figsize=(8, 8))

    # Plot bus lines
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['name']==name]['x'].values[0],
                   df_stops[df_stops['name']==name]['y'].values[0])
                  for name in stop_ids_line]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)

    # Plot all stops
    xs = [row['x'] for _, row in df_stops.iterrows()]
    ys = [row['y'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', zorder=5, s=50, label="Stops")

    # Plot rebalancing arcs
    for u, v, key in G_reb.edges(keys=True):
        x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
        x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
        plt.arrow(x1, y1, x2 - x1, y2 - y1,
                  color='green', alpha=0.5,
                  length_includes_head=True,
                  head_width=0.1, head_length=0.1)

    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.show()




# === MAIN ===
if __name__ == "__main__":
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops=3)
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

    # Plot graphs
    plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing")
    print("Finish")
