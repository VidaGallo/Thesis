import osmnx as ox
import pandas as pd
import random
import networkx as nx

############################
# TRAM and BUS data from OSM (or fake lines if missing)
############################
def transit_data_extraction_simple(city, n_lines=2, n_stops=8, network_type="drive"):
    """
    Creates fake bus/tram lines on the street network of a city (ex. Turin)
    and saves it to an Excel file. If no data is found in OSM, generates fake lines.

    Returns:
    df_routes : pandas.DataFrame containing line information
    df_stops : pandas.DataFrame containing stops mapped to the street network nodes
    G : networkx.Graph, the street network graph.
    """

    # === Graph construction / costruzione del grafo ===
    G = ox.graph_from_place(city, network_type=network_type)
    G = ox.project_graph(G)   # transform (lat, lon) into coordinates (in meters) for distance calculation

    df_routes_list = []
    df_stops_list = []
    stop_id = 0

    # === LINE CREATION ===
    min_dist = 300   # min distance among two stops (in meters)

    print(f"Generating {n_lines} lines ...")
    for line_idx in range(1, n_lines+1):
        # start from a random node
        start_node = random.choice(list(G.nodes))
        stops = [start_node]
        current_node = start_node

        # === generate stops for this line with minimum distance ===
        while len(stops) < n_stops:
            neighbors = list(G.neighbors(current_node))
            if not neighbors:
                break
            next_node = random.choice(neighbors)

                # calcolo distanza dall'ultima fermata in lista (non solo arco diretto!)
            dist = nx.shortest_path_length(G, stops[-1], next_node, weight="length")

            if dist >= min_dist:
                stops.append(next_node)   # aggiungi nuova fermata
                current_node = next_node
            else:
                # altrimenti prova con un altro vicino
                current_node = next_node

        # === add route / aggiungi linea ===
        line_name = f"Line {line_idx}"
        geometry_str = "LINESTRING (" + ", ".join([f"{G.nodes[n]['x']} {G.nodes[n]['y']}" for n in stops]) + ")"
        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": line_name,
            "geometry": geometry_str
        })

        # === add stops / aggiungi fermate ===
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

    # === convert to DataFrame ===
    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # === Save to CSV and Return ===
    city_clean = city.split(",")[0].replace(" ", "_")
    output_path_routes = f"data/input_data_{city_clean}_lines_fake.csv"
    output_path_stops = f"data/input_data_{city_clean}_stops_fake.csv"

    print(f"Saving routes to {output_path_routes} ...")
    df_routes.to_csv(output_path_routes, index=False)   # salva le linee in CSV

    print(f"Saving stops to {output_path_stops} ...")
    df_stops.to_csv(output_path_stops, index=False)     # salva le fermate in CSV

    return df_routes, df_stops, G


if __name__ == "__main__":
    city_name = "Turin, Italy"  # or Rome, Milan, ...
    print(f"Generating OSM dataset (or fake lines) for {city_name}...")
    transit_data_extraction_simple(city=city_name, n_lines=2, n_stops=5)
