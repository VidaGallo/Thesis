import pandas as pd
import random
import matplotlib.pyplot as plt


random.seed(123)

#########################
# GENERATE GRID TEST DATA
########################

def create_grid_test_data(n_lines=3, n_stops=5, grid_size=5, min_dist=1, output_folder="data"):
    """
    Creates a test dataset on a NxN grid:
    - n_lines lines
    - n_stops per line
    - min_dist controls min distance between consecutive stops
    - lines can intersect at stops
    - saves two CSVs: lines and stops
    """

    df_routes_list = []
    df_stops_list = []
    stop_id = 0
    stop_positions = {}  # key: (x,y), value: list of stop_ids for multi-line stops
    line_nodes = {}           # key: line_idx, value: set of nodes in that line

    directions = [(1,0), (-1,0), (0,1), (0,-1)]  # right, left, up, down
    occupied_starts = set()   # A line can't start from the same node as another line

    for line_idx in range(1, n_lines+1):
        # Pick a random start outside of already used start positions
        while True:
            x = random.randint(1, grid_size)
            y = random.randint(1, grid_size)
            if (x, y) not in occupied_starts:
                occupied_starts.add((x, y))
                break
        stops = [(x, y)]
        line_nodes[line_idx] = set([(x, y)])

        for stop_num in range(1, n_stops):
            # Move with preference to continue straight
            last_move = (stops[-1][0] - stops[-2][0], stops[-1][1] - stops[-2][1]) if len(stops) > 1 else (0,0)
            probs = []

            move_valid = False
            attempt = 0
            max_attempts = 5   # max 5 retries per stop
            
            for dx, dy in directions:
                if (dx, dy) == last_move:
                    probs.append(0.6)  # 60% chance to continue straight
                else:
                    probs.append(0.4/3)  # distribute remaining probability
            while not move_valid and attempt < max_attempts:
                move = random.choices(directions, weights=probs)[0]

                # Next stop coordinates
                nx = max(0, min(grid_size-1, stops[-1][0] + move[0]))
                ny = max(0, min(grid_size-1, stops[-1][1] + move[1]))

                # Check if the move would be diagonal relative to last step
                if abs(nx - stops[-1][0]) + abs(ny - stops[-1][1]) == 1:
                    move_valid = True  # valid horizontal or vertical step
                #else loop again
                attempt += 1

            # Avoid stops too close
            if abs(nx - stops[-1][0]) + abs(ny - stops[-1][1]) < min_dist:
                nx, ny = stops[-1]

            # Avoid revisiting nodes except the first
            if (nx, ny) in stops and (nx, ny) != stops[0]:
                continue

            # Skip if more than 2 nodes would be shared with any other line
            shared_count = sum(1 for ln, nodes in line_nodes.items() 
                                if ln != line_idx and (nx, ny) in nodes)
            
            # Otherwise accept
            stops.append((nx, ny))


        # Save line geometry
        coords = [f"{x} {y}" for x,y in stops]
        geometry = f"LINESTRING ({', '.join(coords)})"
        df_routes_list.append({
            "route": "bus",                       
            "ref": str(line_idx),                  
            "name": f"Line {line_idx}",           
            "geometry": geometry
        })

        # Save stops
        for x, y in stops:
            key = (x,y)
            if key in stop_positions:
                stop_positions[key].append(stop_id)
            else:
                stop_positions[key] = [stop_id]
            
            df_stops_list.append({
                "stop_id": stop_id,                        
                "name": f"Stop_{stop_id}",                 
                "type": "bus_stop",                         
                "node": stop_id,                            
                "lon": x,                                  
                "lat": y                                   
            })
            stop_id += 1

    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)

    # Save to CSV
    output_routes = f"{output_folder}/bus_lines/grid_lines.csv"
    output_stops = f"{output_folder}/bus_lines/grid_stops.csv"

    print(f"Saving routes to {output_routes} ...")                  
    df_routes.to_csv(output_routes, index=False)  

    print(f"Saving stops to {output_stops} ...")                     
    df_stops.to_csv(output_stops, index=False)    

    return df_routes, df_stops



def plot_transit_data(df_routes, df_stops, grid_size=None, title="Transit network"):
    """
    Plots the transit lines and stops from the given DataFrames.
    Uses a small offset for each line so overlapping routes are still visible.
    """
    plt.figure(figsize=(8, 6))
    title="Grid Transit Network"

    # === Plot lines (with offset) ===
    for idx, row in df_routes.iterrows():
        coords_text = row['geometry'].replace("LINESTRING (", "").replace(")", "")
        coords = [list(map(float, p.split())) for p in coords_text.split(", ")]
        xs, ys = zip(*coords)

        offset = 0.0 * idx
        xs = [x + offset for x in xs]
        ys = [y + offset for y in ys]

        plt.plot(xs, ys, marker='o', label=row['name'], linewidth=3, alpha=0.8)

    # === Stops ===
    plt.scatter(df_stops["lon"], df_stops["lat"], c="red", s=40, zorder=5, label="Stops")

    # === Setup ===
    if grid_size is not None:
        plt.xlim(1, grid_size)
        plt.ylim(1, grid_size)
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.grid(True)
    plt.show()




if __name__ == "__main__":
    print("Generating grid test dataset...")
    gs = 7
    df_routes, df_stops = create_grid_test_data(n_lines=5, n_stops=11, grid_size=gs, min_dist=1)
    plot_transit_data(df_routes, df_stops, grid_size = gs)
