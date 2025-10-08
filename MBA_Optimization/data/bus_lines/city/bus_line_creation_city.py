import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pickle
import random
from collections import defaultdict
import math
import numpy as np
import os

random.seed(123)
np.random.seed(123)


# === GENERATE CITY DATA ON REAL MAP ===
def create_test_data_city_real(city="Turin, Italy", n_lines=5, n_stops_line=10):
    """
    Genera linee bus fittizie sopra la rete stradale reale di Torino.
    - Mantiene stop_id numerici (per compatibilità col modello)
    - Salva anche lon/lat per visualizzare sul grafo reale
    """
    os.makedirs("data/bus_lines/city", exist_ok=True)

    # === GRAFO STRADALE REALE ===
    print(f"📍 Scarico rete stradale di {city}...")
    G_city = ox.graph_from_place(city, network_type="drive")
    G_proj = ox.project_graph(G_city)

    # HUB principali (Porta Susa e Porta Nuova)
    hubs_lonlat = {
        "Porta Susa": (7.6696, 45.0703),
        "Porta Nuova": (7.6787, 45.0626)
    }

    # Trovo i nodi OSM più vicini agli hub
    hub_nodes = {
        name: ox.distance.nearest_nodes(G_city, lon, lat)
        for name, (lon, lat) in hubs_lonlat.items()
    }
    print(f"✅ Hub nodes: {hub_nodes}")

    df_routes_list = []
    df_stops_list = []
    stop_id = 0

    # === Genera linee tra i due hub con deviazioni casuali ===
    for line_idx in range(1, n_lines + 1):
        # partenza e arrivo hub alternati
        start_hub = "Porta Susa" if line_idx % 2 == 0 else "Porta Nuova"
        end_hub = "Porta Nuova" if start_hub == "Porta Susa" else "Porta Susa"
        start_node = hub_nodes[start_hub]
        end_node = hub_nodes[end_hub]

        # trova cammino più breve sulla rete stradale
        path = ox.shortest_path(G_city, start_node, end_node, weight="length")

        # scegli un sottoinsieme casuale di nodi lungo il percorso come fermate
        sampled_nodes = sorted(random.sample(path, min(n_stops_line, len(path))))
        geometry_closed = sampled_nodes + sampled_nodes[-2::-1]

        # salva fermate
        for n in sampled_nodes:
            x = G_city.nodes[n]["x"]
            y = G_city.nodes[n]["y"]
            lat = G_city.nodes[n]["y"]
            lon = G_city.nodes[n]["x"]
            df_stops_list.append({
                "stop_id": stop_id,
                "name": f"Stop_{stop_id}",
                "osm_node": n,
                "x": x, "y": y,
                "lon": lon, "lat": lat,
                "type": "bus_stop"
            })
            stop_id += 1

        df_routes_list.append({
            "route": "bus",
            "ref": str(line_idx),
            "name": f"Line {line_idx}",
            "geometry": list(range(stop_id - len(sampled_nodes), stop_id))
                        + list(range(stop_id - 2, stop_id - len(sampled_nodes) - 1, -1))
        })

    df_routes = pd.DataFrame(df_routes_list)
    df_stops = pd.DataFrame(df_stops_list)
    print(f"💾 Linee create: {len(df_routes)}, fermate: {len(df_stops)}")

    return df_routes, df_stops, G_city


# === CREA GRAFI ===
def create_lines_graph(df_routes, df_stops):
    G = nx.MultiDiGraph()
    for _, row in df_stops.iterrows():
        G.add_node(int(row['stop_id']), x=row['x'], y=row['y'], lon=row['lon'], lat=row['lat'])
    for _, row in df_routes.iterrows():
        stops = row['geometry']
        for u, v in zip(stops[:-1], stops[1:]):
            x1, y1 = df_stops.loc[df_stops['stop_id'] == u, ['x', 'y']].values[0]
            x2, y2 = df_stops.loc[df_stops['stop_id'] == v, ['x', 'y']].values[0]
            length = math.dist((x1, y1), (x2, y2))
            G.add_edge(u, v, weight=1, length=length, ref=row['ref'])
            G.add_edge(v, u, weight=1, length=length, ref=row['ref'])
    print("✅ G_lines creato.")
    return G


def create_rebalancing_graph(G_lines, df_routes, df_stops):
    line_nodes = {row['ref']: row['geometry'] for _, row in df_routes.iterrows()}

    T_nodes = set()
    for nodes in line_nodes.values():
        counts = defaultdict(int)
        for n in nodes:
            counts[n] += 1
        terminals_line = [nodes[0]]
        terminals_line += [n for n, c in counts.items() if c == 1 and n != nodes[0]]
        T_nodes.update(terminals_line)

    node_in_lines = defaultdict(set)
    for line_ref, nodes in line_nodes.items():
        for n in set(nodes):
            node_in_lines[n].add(line_ref)
    J_nodes = {n for n, lines in node_in_lines.items() if len(lines) >= 2}

    special_nodes = T_nodes.union(J_nodes)
    G_reb = nx.MultiDiGraph()
    for n in special_nodes:
        stop = df_stops.loc[df_stops['stop_id'] == n].iloc[0]
        G_reb.add_node(n, x=stop['x'], y=stop['y'], lon=stop['lon'], lat=stop['lat'])
    for u in special_nodes:
        for v in special_nodes:
            if u != v:
                x1, y1 = G_reb.nodes[u]['x'], G_reb.nodes[u]['y']
                x2, y2 = G_reb.nodes[v]['x'], G_reb.nodes[v]['y']
                length = math.dist((x1, y1), (x2, y2))
                G_reb.add_edge(u, v, weight=1, length=length)
    print(f"🔁 Nodi rebalancing: {len(special_nodes)}")
    return G_reb


# === PLOT ===
def plot_transit_graph_on_city(G_city, df_routes, df_stops, G_reb, title="Bus + Rebalancing on Torino"):
    fig, ax = ox.plot_graph(G_city, show=False, close=False, node_size=0, edge_color="lightgray", edge_linewidth=0.5)

    colors = plt.colormaps.get_cmap("tab10", len(df_routes))
    for idx, row in df_routes.iterrows():
        stops = row["geometry"]
        coords = [(df_stops.loc[df_stops['stop_id'] == s, 'lon'].values[0],
                   df_stops.loc[df_stops['stop_id'] == s, 'lat'].values[0]) for s in stops]
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color=colors(idx), linewidth=2, label=row['name'])
    ax.scatter(df_stops["lon"], df_stops["lat"], color="red", s=20, zorder=5, label="Stops")

    # rebalancing edges
    for u, v, _ in G_reb.edges(keys=True):
        x1, y1 = G_reb.nodes[u]['lon'], G_reb.nodes[u]['lat']
        x2, y2 = G_reb.nodes[v]['lon'], G_reb.nodes[v]['lat']
        ax.arrow(x1, y1, x2 - x1, y2 - y1, color="green", alpha=0.25, length_includes_head=True, head_width=0.0004)

    ax.set_title(title)
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    plt.show()


# === MAIN ===
if __name__ == "__main__":
    df_routes, df_stops, G_city = create_test_data_city_real("Turin, Italy", n_lines=6, n_stops_line=15)
    G_lines = create_lines_graph(df_routes, df_stops)
    G_reb = create_rebalancing_graph(G_lines, df_routes, df_stops)
    plot_transit_graph_on_city(G_city, df_routes, df_stops, G_reb)
