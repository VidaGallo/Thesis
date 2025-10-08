import pandas as pd
import random
import pickle
import networkx as nx
import numpy as np
import json

random.seed(123)
np.random.seed(123)






# === EXAMPLE TO USE IN MAIN ===
### Cross
with open("data/bus_lines/cross/cross_Gbar_graph.gpickle", "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/cross/cross_bus_stops.csv")
generate_requests_graph(
    df_stops, G_bar,
    n_requests=5,
    output_csv="data/demands/cross_mobility_requests.csv"
)

"""
### Grid
with open("data/bus_lines/grid/grid_Gbar_graph.gpickle", "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv("data/bus_lines/grid/grid_bus_stops.csv")
generate_requests_graph(
    df_stops, G_bar,
    n_requests=5,
    output_csv="data/demands/grid_mobility_requests.csv"
)
"""
"""
### City
city_name = "Turin, Italy"
city_clean = city_name.split(",")[0].strip()
graph_file = f"data/bus_lines/city/city_{city_clean}_Gbar_graph.gpickle"
with open(graph_file, "rb") as f:
    G_bar = pickle.load(f)
df_stops = pd.read_csv(f"data/bus_lines/city/city_{city_clean}_bus_stops.csv")
generate_requests_graph(
    df_stops, G_bar,
    n_requests=5,
    output_csv=f"data/demands/city_{city_clean}_mobility_requests.csv"
)

"""