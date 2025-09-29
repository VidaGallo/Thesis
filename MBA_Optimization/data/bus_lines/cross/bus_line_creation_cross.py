import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
from collections import defaultdict

random.seed(123)

####################
# GENERATE TEST DATA
####################
def create_test_data_cross(n_stops=5):
    """
    Generate a minimal transit dataset with 2 lines forming a cross.
    - Each line has `n_stops` stops
    - Lines intersect at a single stop (random index)
    - Saves CSV files for lines and stops
    - 'geometry' column now contains a list of stop_ids (integers)
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
        y = n_stops // 2
        stop_name = stop_id
        coords_line1.append(stop_name)
        df_stops_list.append({
            "stop_id": stop_id,
            "name": stop_name,
            "type": "bus_stop",
            "node": stop_name,
            "lon": x,
            "lat": y
        })
        stop_id += 1
    df_routes_list.append({
        "route": "bus",
        "ref": "1",
        "name": "Line 1",
        "geometry": coords_line1  # now a list of ints
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
                "lon": x,
                "lat": y
            })
            stop_id += 1
    df_routes_list.append({
        "route": "bus",
        "ref": "2",
        "name": "Line 2",
        "geometry": coords_line2  # now a list of ints
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


#########################
# CREATE LINES GRAPH
#########################
def create_lines_graph():
    """
    Build a NetworkX graph of stops:
    - Each stop is a node (integer)
    - Consecutive stops along lines are connected by edges with weight=1
    - Saves the graph as a .gpickle file
    """
    df_routes, df_stops = create_test_data_cross()

    G = nx.Graph()

    # Add nodes using stop_id (integer)
    for _, row in df_stops.iterrows():
        G.add_node(int(row['name']), lon=row['lon'], lat=row['lat'])

    # Add edges along each line
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            G.add_edge(u, v, weight=1)

    # Save graph
    graph_file = f"data/bus_lines/cross/cross_bus_lines_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved in {graph_file}")

    return G, df_routes, df_stops


#########################
# CREATE REBALANCING GRAPH
#########################
def create_rebalancing_graph(G, df_routes, df_stops, save_path=None):
    """
    Create a directed rebalancing graph connecting terminals and junctions.
    - Terminals: first and last stop of each line
    - Junctions: stops shared by multiple lines
    """
    # Map line to stop_ids (integers)
    line_nodes = {}
    for _, row in df_routes.iterrows():
        line_nodes[row['ref']] = row['geometry']

    # Identify terminals
    T_nodes = set()
    for nodes in line_nodes.values():
        T_nodes.add(nodes[0])
        T_nodes.add(nodes[-1])

    # Identify junctions
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_nodes = set(n for n, cnt in node_count.items() if cnt >= 2)

    special_nodes = T_nodes.union(J_nodes)

    # Build directed graph
    G_reb = nx.DiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['name']==n].iloc[0]
        G_reb.add_node(n, lon=stop_info['lon'], lat=stop_info['lat'])

    # Add arcs between all special nodes
    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                G_reb.add_edge(u, v)

    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved as {save_path}")

    return G_reb


#########################
# PLOT GRAPHS
#########################
def plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing"):
    """
    Plot the bus line graph and rebalancing graph
    """
    plt.figure(figsize=(8, 8))

    # Plot bus lines
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['name']==name]['lon'].values[0],
                   df_stops[df_stops['name']==name]['lat'].values[0])
                  for name in stop_ids_line]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)

    # Plot all stops
    xs = [row['lon'] for _, row in df_stops.iterrows()]
    ys = [row['lat'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', zorder=5, s=50, label="Stops")

    # Plot rebalancing arcs
    for u, v in G_reb.edges():
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
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


#########################
# MAIN
#########################
if __name__ == "__main__":
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops=3)
    G_lines, df_routes, df_stops = create_lines_graph()

    # Create rebalancing graph
    G_reb = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path="data/bus_lines/cross/cross_rebalancing_graph.gpickle"
    )

    # Plot graphs
    plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing")
