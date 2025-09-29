import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random


random.seed(123)


#########################
# GENERATE GRID TEST DATA
########################
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import pickle
import random
import math
from collections import defaultdict

random.seed(123)


#########################
# GENERATE GRID TEST DATA
#########################
def create_grid_test_data(n_lines=4, n_stops=5, grid_size=5):
    """
    Generate a grid-like transit network:
    - n_lines lines
    - n_stops per line
    - Ensures connectivity by intersecting previous lines
    - Saves CSV files for lines and stops
    """
    df_routes_list = []
    df_stops_list = []
    stop_positions = {}  # map (x,y) -> stop_id
    line_nodes = {}
    stop_id = 0
    directions = [(1,0), (-1,0), (0,1), (0,-1)]

    line_idx = 1
    max_retries = 200

    while line_idx <= n_lines and max_retries > 0:
        # === Choose starting point ===
        if line_idx == 1:
            x, y = random.randint(1, grid_size), random.randint(1, grid_size)
        else:
            x, y = random.choice(list(stop_positions.keys()))  # start from existing stop

        stops = [(x, y)]
        candidate_nodes = set([(x, y)])

        # === Build the line ===
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

        # === Check overlap & intersection ===
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

        # === Accept line ===
        line_nodes[line_idx] = candidate_nodes
        coords = [f"{x} {y}" for x, y in stops]
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": f"Line {line_idx}",
            "geometry": f"LINESTRING ({', '.join(coords)})"
        })

        for x, y in stops:
            if (x, y) not in stop_positions:
                stop_positions[(x, y)] = stop_id
                df_stops_list.append({
                    "stop_id": stop_id,
                    "name": f"Stop_{stop_id}",
                    "type": "bus_stop",
                    "node": stop_id,
                    "lon": x,
                    "lat": y
                })
                stop_id += 1

        line_idx += 1

    # === Convert to DataFrames and save ===
    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)
    df_routes.to_csv(f"data/bus_lines/grid/grid_bus_lines.csv", index=False)
    df_stops.to_csv(f"data/bus_lines/grid/grid_bus_stops.csv", index=False)

    return df_routes, df_stops



# === CREATE GRID GRAPH ===
def create_grid_graph(df_routes, df_stops):
    """
    Build a NetworkX graph for the grid:
    - Each stop is a node
    - Consecutive stops along lines are connected by edges with weight=1
    """
    G = nx.Graph()
    for _, row in df_stops.iterrows():
        G.add_node(row['stop_id'], lon=row['lon'], lat=row['lat'])

    coord_to_stop_id = {(row['lon'], row['lat']): row['stop_id'] for _, row in df_stops.iterrows()}

    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        stop_ids_line = [coord_to_stop_id[tuple(map(float, c.split()))] for c in coords_text.split(", ")]
        for u, v in zip(stop_ids_line[:-1], stop_ids_line[1:]):
            G.add_edge(u, v, weight=1)

    # Save graph
    graph_file = f"data/bus_lines/grid/grid_bus_lines_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)
    print(f"Grid graph saved as {graph_file}")
    return G



# === CREATE REBALANCING GRAPH ===
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




# === PLOT GRID GRAPH + REBALANCING ===
def plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Transit + Rebalancing"):
    """
    Plot grid lines, stops, and rebalancing arcs
    """
    plt.figure(figsize=(8,8))
    # Lines
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, c.split())) for c in coords_text.split(", ")]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=2)
    # Stops
    xs = [row['lon'] for _, row in df_stops.iterrows()]
    ys = [row['lat'] for _, row in df_stops.iterrows()]
    plt.scatter(xs, ys, color='red', s=50, zorder=5, label="Stops")
    # Rebalancing arcs
    for u,v in G_reb.edges():
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
        plt.arrow(x1, y1, x2-x1, y2-y1, color='green', alpha=0.5, length_includes_head=True, head_width=0.1, head_length=0.1)
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.show()



if __name__ == "__main__":
    print("Generating grid test dataset...")
    # === Generate dataset ===
    df_routes, df_stops = create_grid_test_data(
        n_lines=4,
        n_stops=6,
        grid_size=8
    )

    # === Create line graph ===
    G_lines = create_grid_graph(df_routes, df_stops)

    # === Create rebalancing graph ===
    G_reb = create_rebalancing_graph(
        G_lines,
        df_routes,
        df_stops,
        save_path="data/bus_lines/grid/grid_rebalancing_graph.gpickle"
    )

    # === Plot transit + rebalancing ===
    plot_grid_transit(G_lines, G_reb, df_routes, df_stops, title="Grid Transit + Rebalancing")