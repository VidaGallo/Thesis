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


if __name__ == "__main__":
    # === Generate test dataset ===
    print("Generating test dataset...")
    create_test_data(output_path="data/input_data_test.xlsx")