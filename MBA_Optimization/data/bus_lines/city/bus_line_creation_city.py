import gurobipy
import osmnx as ox
import pandas as pd
import random
import networkx as nx
import pickle
import matplotlib.pyplot as plt
from collections import defaultdict
import os
import math

random.seed(123)



# GENERATE FAKE CITY BUS LINES
# Creazione di linee di autobus (fittizie) basandosi su un grafo esistente delle strade di una città (es. Torino)
def transit_data_city(city, n_lines=2, n_stops=8, network_type="drive"):
    os.makedirs("data/bus_lines/city", exist_ok=True)

    # === STEP 1: crea grafo OSM in coordinate geografiche ===
    G_city = ox.graph_from_place(city, network_type=network_type)

    # salvo lon/lat prima della proiezione
    for n, data in G_city.nodes(data=True):
        data['lon'] = data['x']   # longitudine (gradi)
        data['lat'] = data['y']   # latitudine (gradi)

    # === STEP 2: proietto il grafo in metri (per i calcoli) ===
    G_proj = ox.project_graph(G_city)
    for n, data in G_proj.nodes(data=True):
        data['x_proj'] = data['x']  # metri
        data['y_proj'] = data['y']  # metri

    df_routes_list = []
    df_stops_list = []
    stop_id = 0
    used_nodes = set()

    # Centrality for intersections
    # Per cercare di iniziare da nodi che sono "centrali" e avere la maggior parte delle linee autobus nel centro città
    centrality = nx.betweenness_centrality(G_proj, weight="length")
    top_k = 30
    top_nodes = sorted(centrality, key=centrality.get, reverse=True)[:top_k]

    min_dist = 500    # distanza tra uno stop e il prossimo

    for line_idx in range(1, n_lines+1):
        if line_idx == 1:
            start_node = random.choice(top_nodes)
        else:
            start_node = random.choice(list(used_nodes))

        stops = [start_node]
        current_node = start_node
        used_nodes.add(start_node)
        stop_ids_line = []

        while len(stops) < n_stops:
            neighbors = list(G_proj.neighbors(current_node))
            if not neighbors:
                break
            weights = [2 if n in used_nodes else 1 for n in neighbors]
            next_node = random.choices(neighbors, weights=weights, k=1)[0]
            stops.append(next_node)
            current_node = next_node
            used_nodes.add(next_node)

        # Add stops to df_stops_list
        for n in stops:
            df_stops_list.append({
                "stop_id": stop_id,
                "name": stop_id,       # integer name
                "type": "bus_stop",
                "node": stop_id,
                "lon": G_city.nodes[n]['lon'],     # per plot
                "lat": G_city.nodes[n]['lat'],     # per plot
                "x": G_proj.nodes[n]['x_proj'],    # per calcoli
                "y": G_proj.nodes[n]['y_proj'],    # per calcoli
                "osm_node": n          # original OSM node
            })
            stop_ids_line.append(stop_id)
            stop_id += 1

        # Save line as list of stop_id integers
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": f"Line {line_idx}",
            "geometry": stop_ids_line
        })

    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # Build directed MULTIGRAPH for lines
    G_lines = nx.MultiDiGraph()
    for _, row in df_stops.iterrows():
        G_lines.add_node(row['stop_id'], x=row['x'], y=row['y'], lon=row['lon'], lat=row['lat'])
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            # calcolo la lunghezza euclidea in metri
            x1, y1 = G_lines.nodes[u]['x'], G_lines.nodes[u]['y']
            x2, y2 = G_lines.nodes[v]['x'], G_lines.nodes[v]['y']
            length = math.dist((x1, y1), (x2, y2))     # servirà poi per calcolare il tempo di percorrenza

            # ogni arco è distinto → MultiDiGraph salva chiave (key) diversa
            G_lines.add_edge(u, v, weight=1, length=length, ref=row['ref'])
            G_lines.add_edge(v, u, weight=1, length=length, ref=row['ref'])

    # Save CSVs
    city_clean = city.split(",")[0].replace(" ", "_")
    df_routes.to_csv(f"data/bus_lines/city/city_{city_clean}_bus_lines.csv", index=False)
    df_stops.to_csv(f"data/bus_lines/city/city_{city_clean}_bus_stops.csv", index=False)

    return df_routes, df_stops, G_city, G_lines




# === CREATE REBALANCING GRAPH ===
def create_rebalancing_graph(G, df_routes, df_stops, save_path=None):
    # line_nodes: ref -> list of stop_id integers
    line_nodes = {row['ref']: row['geometry'] for _, row in df_routes.iterrows()}

    # Terminals
    T_nodes = set()
    for nodes in line_nodes.values():
        T_nodes.add(nodes[0])
        T_nodes.add(nodes[-1])

    # Junctions
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_nodes = set(n for n, cnt in node_count.items() if cnt >= 2)

    special_nodes = T_nodes.union(J_nodes)

    # Build directed MULTIGRAPH for rebalancing
    G_reb = nx.MultiDiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['stop_id']==n].iloc[0]
        G_reb.add_node(n, x=stop_info['x'], y=stop_info['y'], lon=stop_info['lon'], lat=stop_info['lat'])

    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
                x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
                length = math.dist((x1, y1), (x2, y2))      # la lunghezza servirà poi anche per il calcolo del tempo di percorrenza
                G_reb.add_edge(u, v, weight=1, length=length)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved as {save_path}")

    return G_reb




# === PLOT FUNCTION ===
# Plot del grafo delle linee autobus e linee di rebalance sul grafo della città
def plot_transit_graph(G_city, G_lines, G_reb, df_routes, df_stops, title="Transit Lines + Rebalancing"):
    fig, ax = ox.plot_graph(G_city, show=False, close=False, node_size=0, edge_color='lightgray', edge_linewidth=0.5)

    colors = plt.cm.get_cmap('tab10', len(df_routes))

    for idx, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['stop_id']==n]['lon'].values[0],
                   df_stops[df_stops['stop_id']==n]['lat'].values[0])
                  for n in stop_ids_line]
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color=colors(idx), linewidth=2, label=row['name'])

    ax.scatter(df_stops['lon'], df_stops['lat'], color='red', s=20, zorder=5, label='Stops')

    # Rebalancing arcs
    for u, v, key in G_reb.edges(keys=True):
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
        ax.arrow(x1, y1, x2-x1, y2-y1, color='green', alpha=0.5, length_includes_head=True,
                 head_width=0.1, head_length=0.1)

    ax.set_title(title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.show()






# === MAIN ===
if __name__ == "__main__":
    city_name = "Turin, Italy"
    city_clean = city_name.split(",")[0].strip()
    print(f"Generating transit data for {city_name}...")

    df_routes, df_stops, G_city, G_lines = transit_data_city(city=city_name, n_lines=7, n_stops=20)

    G_reb = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path=f"data/bus_lines/city/city_{city_clean}_rebalancing_graph.gpickle"
    )

    plot_transit_graph(G_city, G_lines, G_reb, df_routes, df_stops, title="Transit Lines + Rebalancing")

    # Save line and city graphs
    with open(f"data/bus_lines/city/city_{city_clean}_bus_lines_graph.gpickle", "wb") as f:
        pickle.dump(G_lines, f)
    with open(f"data/bus_lines/city/city_{city_clean}_street_graph.gpickle", "wb") as f:
        pickle.dump(G_city, f)
