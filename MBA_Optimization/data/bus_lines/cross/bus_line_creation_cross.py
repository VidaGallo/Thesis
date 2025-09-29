import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
import math
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
    output_routes = f"data/bus_lines/cross/cross_bus_lines.csv"
    output_stops = f"data/bus_lines/cross/cross_bus_stops.csv"

    print(f"Saving routes to {output_routes} ...")
    df_routes.to_csv(output_routes, index=False)
    print(f"Saving stops to {output_stops} ...")
    df_stops.to_csv(output_stops, index=False)

    return df_routes, df_stops







def create_lines_graph():
    """
    Build a NetworkX graph of stops:
    - Each stop is a node
    - Consecutive stops along lines are connected by edges with weight=1
    Saves the graph as a .gpickle file.
    """
    # Load cross dataset
    df_routes, df_stops = create_test_data_cross()

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
    graph_file = f"data/bus_lines/cross/cross_bus_lines_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)

    print(f"Graph saved in {graph_file}")
    return G, df_routes, df_stops






# === CREATE REBALANCING GRAPH  ===
def create_rebalancing_graph(G, df_routes, df_stops, save_path=None):
    """
    Create a directed rebalancing graph connecting terminals and junctions.
    Travel times will be assigned later.
    """
    # Identify terminals and junctions
    line_nodes = {}
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [tuple(map(float, c.split())) for c in coords_text.split(", ")]
        line_nodes[row['ref']] = coords

    # Terminals
    T_coords = set()
    for nodes in line_nodes.values():
        T_coords.add(nodes[0])
        T_coords.add(nodes[-1])

    # Junctions
    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_coords = set(n for n, cnt in node_count.items() if cnt >= 2)

    special_coords = T_coords.union(J_coords)
    coord_to_stop_id = {(row['lon'], row['lat']): row['stop_id'] for _, row in df_stops.iterrows()}
    special_nodes = set(coord_to_stop_id[c] for c in special_coords)

    # Build directed graph
    G_reb = nx.DiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['stop_id']==n].iloc[0]
        G_reb.add_node(n, lon=stop_info['lon'], lat=stop_info['lat'])

    # Add all possible arcs between special nodes (travel time will be assigned later)
    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                G_reb.add_edge(u, v)

    if save_path:
        with open(save_path, "wb") as f:
            pickle.dump(G_reb, f)
        print(f"Rebalancing graph saved as {save_path}")

    return G_reb





def plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing"):
    """
    Plots of the bus line graph and rebalancing graph.
    """
    plt.figure(figsize=(8, 8))
    
    # Plot linee bus
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, p.split())) for p in coords_text.split(", ")]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)

    # Plot nodi
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



if __name__ == "__main__":
    # === Generate test dataset ===
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops=3) 
    G_lines, df_routes, df_stops = create_lines_graph()

    # Crea grafo di rebalancing
    G_reb= create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path="data/bus_lines/cross/cross_rebalancing_graph.gpickle"
    )

    # Plots
    plot_transit_graphs(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing")

