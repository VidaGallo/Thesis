import pandas as pd
import matplotlib.pyplot as plt




####################
# GENERATE TEST DATA
####################
def create_test_data(n_lines=2, n_stops=3, output_folder="data"):
    """
    Creates a minimal test dataset for transit ILP:
    - n_lines lines (bus 1, bus 2, ...)
    - n_stops per linea
    - saves to TWO CSV files: lines and stops
    """

    # === Lines (routes) ===
    df_routes_list = []
    for line_idx in range(1, n_lines + 1):
        # geometry semplice: linee lungo x o y per test
        coords = []
        for stop_idx in range(n_stops):
            x = stop_idx
            y = line_idx - 1
            coords.append(f"{x} {y}")
        geometry = f"LINESTRING ({', '.join(coords)})"  # Line geometry in WKT format

        df_routes_list.append({
            "route": "bus",                       # type of transit
            "ref": str(line_idx),                  # line reference number
            "name": f"Line {line_idx}",           # line name
            "geometry": geometry                   # coordinates of the line
        })

    df_routes = pd.DataFrame(df_routes_list)       # Create DataFrame for lines

    # === Stops ===
    df_stops_list = []
    stop_id = 0
    for line_idx in range(1, n_lines + 1):
        for stop_idx in range(n_stops):
            df_stops_list.append({
                "stop_id": stop_id,                        # unique stop id
                "name": f"Stop_{stop_id}",                 # stop name
                "type": "bus_stop",                         # type of stop
                "node": stop_id,                            # node id for graph mapping
                "lon": stop_idx,                            # longitude (fake for test)
                "lat": line_idx - 1                         # latitude (fake for test)
            })
            stop_id += 1

    df_stops = pd.DataFrame(df_stops_list)           # Create DataFrame for stops

    # === Save to CSV ===
    output_routes = f"{output_folder}/input_data_line_lines.csv"   # CSV file for lines
    output_stops = f"{output_folder}/input_data_line_stops.csv"    # CSV file for stops

    print(f"Saving routes to {output_routes} ...")                  
    df_routes.to_csv(output_routes, index=False)  # Save lines as CSV

    print(f"Saving stops to {output_stops} ...")                     
    df_stops.to_csv(output_stops, index=False)    # Save stops as CSV

    return df_routes, df_stops                       # Return DataFrames





def plot_transit_data(df_routes, df_stops, title="Transit Lines"):
    """
    Plot the transit lines and stops.
    df_routes: DataFrame with a 'geometry' column (LINESTRING WKT)
    df_stops: DataFrame with 'lon' and 'lat' for stop positions
    """
    plt.figure(figsize=(6, 6))
    
    # plot each line
    for idx, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, p.split())) for p in coords_text.split(", ")]
        xs, ys = zip(*coords)
        plt.plot(xs, ys, marker='o', label=row['name'])
    
    # plot stops
    plt.scatter(df_stops['lon'], df_stops['lat'], color='red', zorder=5)
    
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.show()







if __name__ == "__main__":
    # === Generate test dataset ===
    print("Generating test dataset...")
    df_routes, df_stops = create_test_data(n_lines=2, n_stops=3, output_folder="data")  # Example call

    # === Visualize generated lines and stops ===
    plot_transit_data(df_routes, df_stops, title="Test Line Transit Network")