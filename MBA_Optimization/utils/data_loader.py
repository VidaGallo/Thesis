import pandas as pd

class TransitDataLoader:
    """
    Generic loader for transit datasets (lines + stops in CSV).
    Builds dictionaries and helper structures for optimization.
    """

    def __init__(self, lines_csv, stops_csv):
        """
        lines_csv : path to lines CSV file
        stops_csv : path to stops CSV file
        """
        self.lines_csv = lines_csv
        self.stops_csv = stops_csv
        self.lines_df = None
        self.stops_df = None
        self.stops_at_node = {}      # node -> list of stop_ids
        self.line_stops = {}         # line_ref -> list of stop_ids
        self.load_data()

    def load_data(self): 
        # === Read CSVs ===
        self.lines_df = pd.read_csv(self.lines_csv)
        self.stops_df = pd.read_csv(self.stops_csv)

        # === Map stops by node ===
        for idx, row in self.stops_df.iterrows():  
            # Per ogni fermata, creo un dizionario che dice quali stop si trovano su quel nodo del grafo
            # Più linee possono condividere lo stesso nodo (intersezioni)
            node = row["node"]
            stop_id = row["stop_id"]
            if node not in self.stops_at_node:
                self.stops_at_node[node] = []
            self.stops_at_node[node].append(stop_id)

        # === Map stops by line ===
        for idx, row in self.lines_df.iterrows():
            line_ref = row["ref"]
            geometry = row["geometry"]
            # LINESTRING "x y, x y, ..."
            coords = [tuple(map(float, c.split())) for c in geometry.replace("LINESTRING (","").replace(")","").split(",")]
            
            # find stops that match coordinates (approximate match)
            stop_ids = []
            for x, y in coords:
                # naive closest match
                closest_stop = self.stops_df.iloc[((self.stops_df["lon"] - x)**2 + (self.stops_df["lat"] - y)**2).idxmin()]
                stop_ids.append(closest_stop["stop_id"])
            self.line_stops[line_ref] = stop_ids

    def print_summary(self):
        print(f"Loaded {len(self.lines_df)} lines and {len(self.stops_df)} stops")
        print(f"{len(self.stops_at_node)} unique nodes with stops")
