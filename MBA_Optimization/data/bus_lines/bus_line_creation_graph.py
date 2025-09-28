import osmnx as ox
import pandas as pd
import random
import networkx as nx
import pickle
import matplotlib.pyplot as plt

random.seed(123)



############################
# TRAM and BUS data from OSM (or fake lines if missing)
############################
def transit_data_extraction_simple(city, n_lines=2, n_stops=8, network_type="drive"):
    """
    Creates fake bus/tram lines on the street network of a city (ex. Turin),
    ensuring that the resulting transit network is connected (each new line
    intersects at least one existing line).
    """
    # === Graph construction ===
    G = ox.graph_from_place(city, network_type=network_type)
    G = ox.project_graph(G)

    df_routes_list = []
    df_stops_list = []
    stop_id = 0
    used_nodes = set()  # nodes already used by other lines

    # Centrality
    centrality = nx.betweenness_centrality(G, weight="length")
    top_k = 30     # We start from the 30 most central nodes (so we have more lines in the center of the city)
    top_nodes = sorted(centrality, key=centrality.get, reverse=True)[:top_k]

    min_dist = 300      # min distance = 300m between one stop and the next

    print(f"Generating {n_lines} lines ...")
    for line_idx in range(1, n_lines+1):
        # === START NODE ===
        if line_idx == 1:
            start_node = random.choice(top_nodes)
        else:
            start_node = random.choice(list(used_nodes))  # guarantee intersection

        stops = [start_node]
        current_node = start_node
        used_nodes.add(start_node)

        # === Generate stops ===
        while len(stops) < n_stops:
            neighbors = list(G.neighbors(current_node))
            if not neighbors:
                break

            # bias toward central or already used nodes
            weights = [2 if n in used_nodes else 1 for n in neighbors]
            next_node = random.choices(neighbors, weights=weights, k=1)[0]

            dist = nx.shortest_path_length(G, stops[-1], next_node, weight="length")

            if dist >= min_dist:
                stops.append(next_node)
                current_node = next_node
                used_nodes.add(next_node)
            else:
                current_node = next_node  # try another step

        # === Save line ===
        line_name = f"Line {line_idx}"
        geometry_str = "LINESTRING (" + ", ".join([f"{G.nodes[n]['x']} {G.nodes[n]['y']}" for n in stops]) + ")"
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": line_name,
            "geometry": geometry_str
        })

        # === Save stops ===
        for n in stops:
            df_stops_list.append({
                "stop_id": stop_id,
                "name": f"Stop_{stop_id}",
                "type": "bus_stop",
                "node": n,
                "lon": G.nodes[n]['x'],
                "lat": G.nodes[n]['y']
            })
            stop_id += 1

    # Convert to DataFrames
    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # Save CSVs
    city_clean = city.split(",")[0].replace(" ", "_")
    output_path_routes = f"data/bus_lines/graph_lines_{city_clean}.csv"
    output_path_stops = f"data/bus_lines/graph_stops_{city_clean}.csv"
    df_routes.to_csv(output_path_routes, index=False)
    df_stops.to_csv(output_path_stops, index=False)

    return df_routes, df_stops, G




def plot_transit_graph(G, df_routes, df_stops, title="Transit Lines on Graph"):
    """
    Plot the transit lines and stops on the city graph.
    """
    fig, ax = ox.plot_graph(G, show=False, close=False, node_size=0, edge_color='lightgray', edge_linewidth=0.5)
    title=f"Transit Lines in {city_name}"
    # Plot lines
    colors = plt.cm.get_cmap('tab10', len(df_routes))
    for idx, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, p.split())) for p in coords_text.split(", ")]
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color=colors(idx), linewidth=2, label=row['name'])

    # Plot stops
    ax.scatter(df_stops['lon'], df_stops['lat'], color='red', s=20, zorder=5, label='Stops')

    ax.set_title(title)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.show()




if __name__ == "__main__":
    city_name = "Turin, Italy"  # or Rome, Milan, ...
    city_clean = city_name.split(",")[0]
    print(f"Generating lines for {city_name}...")
    df_routes, df_stops, G  = transit_data_extraction_simple(city=city_name, n_lines=5, n_stops=15)
    plot_transit_graph(G, df_routes, df_stops)

    # === Save graph ===
    output_path = f"data/bus_lines/bus_lines_{city_clean}_graph.gpickle"
    with open(output_path, "wb") as f:
        pickle.dump(G, f)
