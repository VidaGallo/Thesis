import gurobipy
import osmnx as ox
import pandas as pd
import random
import networkx as nx
import pickle
import matplotlib.pyplot as plt
from collections import defaultdict
import os

random.seed(123)

######################################
# GENERATE FAKE CITY BUS LINES
######################################
def transit_data_city(city, n_lines=2, n_stops=8, network_type="drive"):
    os.makedirs("data/bus_lines/city", exist_ok=True)

    G_city = ox.graph_from_place(city, network_type=network_type)
    G_city = ox.project_graph(G_city)

    df_routes_list = []
    df_stops_list = []
    stop_id = 0
    used_nodes = set()

    # Centrality for intersections
    centrality = nx.betweenness_centrality(G_city, weight="length")
    top_k = 10
    top_nodes = sorted(centrality, key=centrality.get, reverse=True)[:top_k]

    min_dist = 500

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
            neighbors = list(G_city.neighbors(current_node))
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
                "lon": G_city.nodes[n]['x'],
                "lat": G_city.nodes[n]['y'],
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

    # Build undirected line graph
    G_lines = nx.Graph()
    for _, row in df_stops.iterrows():
        G_lines.add_node(row['stop_id'], lon=row['lon'], lat=row['lat'])
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            if not G_lines.has_edge(u, v):
                G_lines.add_edge(u, v, weight=1, lines=set())
            G_lines[u][v]['lines'].add(row['ref'])

    # Save CSVs
    city_clean = city.split(",")[0].replace(" ", "_")
    df_routes.to_csv(f"data/bus_lines/city/city_{city_clean}_bus_lines.csv", index=False)
    df_stops.to_csv(f"data/bus_lines/city/city_{city_clean}_bus_stops.csv", index=False)

    return df_routes, df_stops, G_city, G_lines


#########################
# CREATE REBALANCING GRAPH
#########################
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

    G_reb = nx.DiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['stop_id']==n].iloc[0]
        G_reb.add_node(n, lon=stop_info['lon'], lat=stop_info['lat'])

    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                G_reb.add_edge(u, v)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved as {save_path}")

    return G_reb


#########################
# PLOT FUNCTION
#########################
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
    for u, v in G_reb.edges():
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
        ax.arrow(x1, y1, x2-x1, y2-y1, color='green', alpha=0.5, length_includes_head=True,
                 head_width=0.1, head_length=0.1)

    ax.set_title(title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.show()


#########################
# MAIN
#########################
if __name__ == "__main__":
    city_name = "Turin, Italy"
    city_clean = city_name.split(",")[0].strip()
    print(f"Generating transit data for {city_name}...")

    df_routes, df_stops, G_city, G_lines = transit_data_city(city=city_name, n_lines=5, n_stops=15)

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
