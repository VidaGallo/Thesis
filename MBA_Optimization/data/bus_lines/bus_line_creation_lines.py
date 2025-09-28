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
    output_routes = f"{output_folder}/cross_lines.csv"
    output_stops = f"{output_folder}/cross_stops.csv"

    print(f"Saving routes to {output_routes} ...")
    df_routes.to_csv(output_routes, index=False)
    print(f"Saving stops to {output_stops} ...")
    df_stops.to_csv(output_stops, index=False)

    return df_routes, df_stops




def plot_transit_data(df_routes, df_stops, title="Transit Lines"):
    """
    Plot transit lines and stops.
    df_routes: DataFrame with 'geometry' column in WKT LINESTRING format
    df_stops: DataFrame with 'lon' and 'lat' columns
    """
    plt.figure(figsize=(6, 6))

    # Plot each line
    for _, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, p.split())) for p in coords_text.split(", ")]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'])

    # Plot stops
    plt.scatter(df_stops['lon'], df_stops['lat'], color='red', zorder=5)

    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.show()




def create_cross_graph(output_folder="data"):
    """
    Build a NetworkX graph of stops:
    - Each stop is a node
    - Consecutive stops along lines are connected by edges with weight=1
    Saves the graph as a .gpickle file.
    """
    # Load cross dataset
    df_routes, df_stops = create_test_data_cross(output_folder=output_folder)

    G = nx.DiGraph()  # directed graph (can later add travel times)

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
            G.add_edge(v, u, weight=1)  # bidirectional

    # Save graph
    graph_file = f"{output_folder}/cross_graph.gpickle"
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)

    print(f"Graph saved in {graph_file}")
    return G, df_routes, df_stops






if __name__ == "__main__":
    # === Generate test dataset ===
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data_cross(n_stops=3, output_folder="data/bus_lines/") 
    G, df_routes, df_stops = create_cross_graph(output_folder="data/bus_lines/")

    # === Visualize generated lines and stops ===
    plot_transit_data(df_routes, df_stops, title="Cross Transit Network")