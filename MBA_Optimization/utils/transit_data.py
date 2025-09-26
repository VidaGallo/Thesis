import osmnx as ox
import pandas as pd




####################
# GENERATE TEST DATA
####################
def create_test_data(output_path="data/input_data_test.xlsx"):
    """
    Creates a minimal test dataset for transit ILP:
    - 2 lines (bus 1 and bus 2)
    - few stops
    - saves to ONE SINGLE Excel with two sheets: Lines and Stops
    """


    # === Lines (routes) ===
    lines_data = [
        {"route": "bus", "ref": "1", "name": "Line 1", "geometry": "LINESTRING (0 0, 1 0, 2 0)"},
        {"route": "bus", "ref": "2", "name": "Line 2", "geometry": "LINESTRING (0 1, 1 1, 2 1)"},
    ]
    df_routes = pd.DataFrame(lines_data)


    # === Stops ===
    stops_data = [
        {"stop_id": 0, "name": "Stop A", "type": "bus_stop", "node": 0, "lon": 0, "lat": 0},
        {"stop_id": 1, "name": "Stop B", "type": "bus_stop", "node": 1, "lon": 1, "lat": 0},
        {"stop_id": 2, "name": "Stop C", "type": "bus_stop", "node": 2, "lon": 2, "lat": 0},
        {"stop_id": 3, "name": "Stop D", "type": "bus_stop", "node": 3, "lon": 0, "lat": 1},
        {"stop_id": 4, "name": "Stop E", "type": "bus_stop", "node": 4, "lon": 1, "lat": 1},
        {"stop_id": 5, "name": "Stop F", "type": "bus_stop", "node": 5, "lon": 2, "lat": 1},
    ]
    df_stops = pd.DataFrame(stops_data)


    # === Save to Excel ===
    with pd.ExcelWriter(output_path) as writer:
        df_routes.to_excel(writer, sheet_name="Lines", index=False)
        df_stops.to_excel(writer, sheet_name="Stops", index=False)

    print(f"Test data saved to {output_path}")
    return df_routes, df_stops








############################
# TRAM and BUS data from OSM 
############################
def transit_data_extraction_simple(city, modes=["bus", "tram"], network_type="drive"):
    """
    Extracts bus and tram data from OpenStreetMap for a given city (ex- "Torino, Italy")
    and saves it to an Excel file.

    Returns:
    df_routes : pandas.DataFrame containing line information (bus and tram).
    df_stops : pandas.DataFrame containing stops mapped to the street network nodes.
    G : networkx.Graph, the street network graph.
    """

    # === Graph construction ===
    G = ox.graph_from_place(city, network_type=network_type)
    G = ox.project_graph(G)   # to transform the (lat,lon) into coordinates (in m) for measuring distances
    



    # === Bus and tram lines extraction ===
    routes = ox.geometries_from_place(
        city,
        tags={"route": modes}     # public transport lines (bus, trams or both)
    )
                                                            
    df_routes = routes[["route", "ref", "name", "geometry"]]
                        # route: [bus, tram]
                        # ref: n° of the line (ex. 4, 11, ...)
                        # name: name of the line
                        # gemoetry: LineString o MultiLineString that represents the route of the transport line (CONTINUOUS, not with the stops)
    df_routes = df_routes.dropna(subset=["geometry"]).reset_index(drop=True)
                          # drop rows that case some NaN => then we need to reset indices (sonce some might be missing now)



    # === Extract stops (based on modes) ===
    stop_tags = {}
    if "bus" in modes:
        stop_tags["highway"] = "bus_stop"      # prendi da OSM tutti gli elementi con highway=bus_stop
    if "tram" in modes:
        stop_tags["railway"] = "tram_stop"     # prendi da OSM tutti gli elementi con railway=tram_stop



    # Dataframe construction
    stops_list = []
    for key, value in stop_tags.items():
        stops = ox.geometries_from_place(city, tags={key: value})  # download all the required geometries from OSM
        stops_list.append(stops)    # LIST of DATAFRAMES (one for buses, one for trams)
    if stops_list:
        stops = pd.concat(stops_list, axis=0)   # We unite in a single DATAFRAME
    else:
        stops = pd.DataFrame()




    # Mapping stops to nearest street network nodes:
    stop_records = []
    for idx, row in stops.iterrows():
        if row.geometry.geom_type == "Point":    # considero solo i punti
            x, y = row.geometry.x, row.geometry.y
            nearest_node = ox.distance.nearest_nodes(G, x, y)     # nodo del grafo più vicino
            stop_records.append({
                "stop_id": idx,     # ID della fermata
                "name": row.get("name", f"stop_{idx}"),     # nome della fermata, se manca crea uno di default
                "type": row.get("highway") or row.get("railway"),    # tipo fermata (bus_stop o tram_stop)
                "node": nearest_node,   # nodo del grafo più vicino
                "lon": x, "lat": y    # coordinate
            })

    df_stops = pd.DataFrame(stop_records)    # convert to Dataframe


    
    # === Save to Excel and Return ===
    city_clean = city.split(",")[0].replace(" ", "_")     # City name selection
    modes_str = "_".join(modes)  # es. "bus", "tram", "bus_tram"
    output_path_dynamic = f"data/input_data_{city_clean}_{modes_str}.xlsx"

    print(f"Saving data to {output_path_dynamic} ...")

    with pd.ExcelWriter(output_path_dynamic) as writer:     # Creation of a SINGLE excel with 2 sheets
        df_routes.to_excel(writer, sheet_name="Lines", index=False)
        df_stops.to_excel(writer, sheet_name="Stops", index=False)

    return df_routes, df_stops, G


    
    








    