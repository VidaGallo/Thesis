import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import os
import json

def plot_bus_network(N, w_sol, x_sol=None, show_passengers=False, show_length=False, G_lines=None):
    """
    Visualizza la rete dei bus con numero di bus assegnati (w_sol) e opzionalmente flusso passeggeri (x_sol).
    Gestisce più linee distinte.

    Parameters:
    - N : dict, line_ref -> lista segmenti (tuple di nodi)
    - w_sol : dict, (l,h) -> numero di bus assegnati
    - x_sol : dict, (k,i,j,l,h) -> flusso passeggeri (opzionale)
    - show_passengers : bool, se True mostra anche flusso passeggeri sugli archi
    - show_length : bool, se True aggiunge la lunghezza dell’arco nelle etichette
    - G_lines : MultiDiGraph opzionale, se fornito permette di leggere attributi come length/travel_time
    """

    G_vis = nx.MultiDiGraph()

    # Colori per linee
    line_list = list(N.keys())
    color_map = cm.get_cmap('tab10', len(line_list))
    line_colors = {l: color_map(i) for i, l in enumerate(line_list)}

    edge_labels = {}
    edge_styles = []

    for l, seg_list in N.items():
        color = line_colors[l]
        for h, seg in enumerate(seg_list):
            n_bus = w_sol.get((l, h), 0)
            n_pass = 0
            if show_passengers and x_sol is not None:
                for (k, i, j, ll, hh), val in x_sol.items():
                    if ll == l and hh == h and val > 0:
                        if (i, j) in [(seg[x], seg[x+1]) for x in range(len(seg)-1)]:
                            n_pass += val

            for i in range(len(seg)-1):
                u, v = seg[i], seg[i+1]
                attrs = {"line": l, "segment": h, "n_bus": n_bus}

                # se disponibile aggiungo la length dal grafo delle linee
                if G_lines and G_lines.has_edge(u, v):
                    first_key = list(G_lines[u][v].keys())[0]
                    attrs["length"] = G_lines[u][v][first_key].get("length", None)

                # aggiungi entrambi i versi
                G_vis.add_edge(u, v, **attrs)
                G_vis.add_edge(v, u, **attrs)

                # costruisci etichetta (solo per u→v per non duplicare)
                label = f"L{l}: {n_bus} mod"
                if n_pass > 0:
                    label += f"\n{int(n_pass)} pax"
                if show_length and "length" in attrs and attrs["length"] is not None:
                    label += f"\nlen={attrs['length']:.1f}"
                edge_labels[(u, v, l, h)] = label
                edge_styles.append((color, 1 + n_bus/3))

    # layout nodi
    pos = nx.spring_layout(G_vis, seed=42)

    # Disegna nodi
    nx.draw(G_vis, pos, with_labels=True, node_size=500, node_color='lightblue')

    # Disegna archi con colori/spessori salvati
    for (u, v, l, h), (col, width) in zip(edge_labels.keys(), edge_styles):
        nx.draw_networkx_edges(
            G_vis, pos, edgelist=[(u, v)],
            width=width, edge_color=[col],
            connectionstyle="arc3,rad=0.1"  # incurva archi per differenziare le direzioni
        )

    # Etichette archi
    nx.draw_networkx_edge_labels(
        G_vis, pos,
        edge_labels={(u, v): lbl for (u, v, l, h), lbl in edge_labels.items()},
        font_color='red', font_size=8
    )

    plt.title("Rete bus: numero di bus per segmento"
              + (" + flusso passeggeri" if show_passengers else "")
              + (" + length" if show_length else ""))
    plt.show()




def save_results(results_folder, prefix, x_sol, w_sol, data, G_lines=None):
    """
    Salva le soluzioni e i parametri principali in JSON.

    Parameters:
    - results_folder: cartella dove salvare i file
    - prefix: stringa per distinguere i file (es: 'cross_BASE')
    - x_sol: dizionario variabili x {(k,i,j,l,h): valore}
    - w_sol: dizionario variabili w {(l,h): valore}
    - data: dizionario contenente almeno data['t'], data['Q'], data['K']
    - G_lines: grafo opzionale per serializzare attributi degli archi (length/travel_time)
    """
    os.makedirs(results_folder, exist_ok=True)

    # === Salva x ===
    with open(os.path.join(results_folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump(
            [
                {"k": k, "i": i, "j": j, "l": l, "h": h, "value": v}
                for (k, i, j, l, h), v in x_sol.items()
            ],
            f,
            indent=2
        )

    # === Salva w ===
    with open(os.path.join(results_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump(
            [
                {"l": l, "h": h, "value": v}
                for (l, h), v in w_sol.items()
            ],
            f,
            indent=2
        )

    # === Salva dati principali (convertendo chiavi tuple) ===
    def stringify_keys(d):
        return {str(k): v for k, v in d.items()}

    with open(os.path.join(results_folder, f"{prefix}_data.json"), "w") as f:
        json.dump(
            {
                "t": stringify_keys(data["t"]),
                "Q": data["Q"],
                "K": data["K"]
            },
            f,
            indent=2
        )

    # === Salva info sul grafo se richiesto ===
    if G_lines:
        with open(os.path.join(results_folder, f"{prefix}_graph_edges.json"), "w") as f:
            json.dump(
                [
                    {"u": u, "v": v, "key": k, **attrs}
                    for u, v, k, attrs in G_lines.edges(keys=True, data=True)
                ],
                f,
                indent=2
            )