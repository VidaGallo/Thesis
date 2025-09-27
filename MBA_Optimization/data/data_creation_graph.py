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
    used_nodes = set()  # nodes already used by other lines

    # === Compute centrality of nodes (betweenness) === 
    # Idea to somehow made the lines to converge more to those nodes (to create some intersections)
    # Centralità di intermediazione: è una misura di quanto un nodo in un grafo si trovi sui percorsi 
    # più brevi tra altri nodi. In altre parole: indica quanto un nodo “funge da ponte” o “snodo” nella rete
    centrality = nx.betweenness_centrality(G, weight="length")
    top_k = 23  # number of nodes considered 'central'
    top_nodes = sorted(centrality, key=centrality.get, reverse=True)[:top_k]


    # === LINE CREATION ===
    min_dist = 300   # min distance among two stops (in meters)


    print(f"Generating {n_lines} lines ...")
    for line_idx in range(1, n_lines+1):
        # start from a random node
        start_node = random.choice(top_nodes)    # Si parte da qualche nodo più centrale!
        stops = [start_node]
        current_node = start_node
        used_nodes.add(start_node)

        # === generate stops for this line with minimum distance ===
        while len(stops) < n_stops:
            neighbors = list(G.neighbors(current_node))

            weights = [centrality[n] for n in neighbors]    # If higher centrality, higher probability
            for i, n in enumerate(neighbors):
                if n in used_nodes:
                    weights[i] *= 2    # We increment the weight if the node is already used by other lines 

            # If all weights are 0 => equal weights 1
            if sum(weights) == 0:
                weights = [1 for _ in neighbors]

            if not neighbors:
                break

            # We would like to have some itnersections => so already used nodes will ahve a higher 
            # probability to be selected!
            weights = [2 if n in used_nodes else 1 for n in neighbors]
            next_node = random.choices(neighbors, weights=weights, k=1)[0]

            # calcolo distanza dall'ultima fermata in lista (non solo arco diretto!)
            dist = nx.shortest_path_length(G, stops[-1], next_node, weight="length")

            if dist >= min_dist:
                stops.append(next_node)   # aggiungi nuova fermata
                current_node = next_node
                used_nodes.add(next_node)
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
    output_path_routes = f"data/input_data_graph_lines_{city_clean}.csv"
    output_path_stops = f"data/input_data_graph_stops_{city_clean}.csv"

    print(f"Saving routes to {output_path_routes} ...")
    df_routes.to_csv(output_path_routes, index=False)   # salva le linee in CSV

    print(f"Saving stops to {output_path_stops} ...")
    df_stops.to_csv(output_path_stops, index=False)     # salva le fermate in CSV

    return df_routes, df_stops, G


if __name__ == "__main__":
    city_name = "Turin, Italy"  # or Rome, Milan, ...
    print(f"Generating OSM dataset (or fake lines) for {city_name}...")
    transit_data_extraction_simple(city=city_name, n_lines=11, n_stops=15)
