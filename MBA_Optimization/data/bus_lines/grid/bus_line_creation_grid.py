import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
from collections import defaultdict
import os

random.seed(123)

#########################
# CREATE GRID TEST DATA
#########################
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
    directions = [(1,0), (-1,0), (0,1), (0,-1)]

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
                    "lon": x,
                    "lat": y
                })
                node_id += 1
            node_ids_line.append(stop_positions[(x, y)])

        # Save line as list of integers
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": f"Line {line_idx}",
            "geometry": node_ids_line  # list of ints
        })

        line_idx += 1

    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    df_routes.to_csv("data/bus_lines/grid/grid_bus_lines.csv", index=False)
    df_stops.to_csv("data/bus_lines/grid/grid_bus_stops.csv", index=False)

    return df_routes, df_stops


#########################
# CREATE GRID GRAPH
#########################
def create_grid_graph(df_routes, df_stops):
    """
    Build a NetworkX graph for the grid:
    - Nodes are integers
    - Consecutive stops along lines are connected
    """
    G = nx.Graph()
    for _, row in df_stops.iterrows():
        G.add_node(row['node'], lon=row['lon'], lat=row['lat'])

    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']  # already list of ints
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            G.add_edge(u, v, weight=1)

    os.makedirs("data/bus_lines/grid", exist_ok=True)
    graph_file = "data/bus_lines/grid/grid_bus_lines_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)
    print(f"Grid graph saved as {graph_file}")
    return G


#########################
# CREATE REBALANCING GRAPH
#########################
def create_rebalancing_graph(G, df_routes, df_stops, save_path=None):
    """
    Create directed rebalancing graph for terminals/junctions
    """
    line_nodes = {row['ref']: row['geometry'] for _, row in df_routes.iterrows()}

    T_nodes = set()
    for nodes in line_nodes.values():
        T_nodes.add(nodes[0])
        T_nodes.add(nodes[-1])

    node_count = defaultdict(int)
    for nodes in line_nodes.values():
        for n in nodes:
            node_count[n] += 1
    J_nodes = set(n for n, cnt in node_count.items() if cnt >= 2)

    special_nodes = T_nodes.union(J_nodes)

    G_reb = nx.DiGraph()
    for n in special_nodes:
        stop_info = df_stops[df_stops['node']==n].iloc[0]
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
# PLOT GRID TRANSIT
#########################
def plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing"):
    plt.figure(figsize=(8,8))
    for _, row in df_routes.iterrows():
        stop_ids_line = row['geometry']
        coords = [(df_stops[df_stops['node']==n]['lon'].values[0],
                   df_stops[df_stops['node']==n]['lat'].values[0]) for n in stop_ids_line]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)

    xs = [row['lon'] for _, row in df_stops.iterrows()]
    ys = [row['lat'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', s=50, zorder=5, label="Stops")

    for u, v in G_reb.edges():
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
        plt.arrow(x1, y1, x2-x1, y2-y1, color='green', alpha=0.5,
                  length_includes_head=True, head_width=0.1, head_length=0.1)

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
    print("Generating grid test dataset...")
    df_routes, df_stops = create_grid_test_data(n_lines=4, n_stops=6, grid_size=8)

    G_lines = create_grid_graph(df_routes, df_stops)
    G_reb = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path="data/bus_lines/grid/grid_rebalancing_graph.gpickle"
    )

    plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Grid Transit + Rebalancing")
