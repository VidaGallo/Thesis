import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch
import os
import json



def plot_bus_network(G_lines, w_sol, x_sol=None, show_passengers=False, show_length=False):
    """
    Disegna la rete direttamente dal grafo G_lines.
    - Usa coordinate x,y dei nodi
    - Due archi distinti per direzioni opposte
    - Colori random (uno per ogni linea)
    - Etichette multi-linea sopra/sotto correttamente distanziate
    """

    # === Genera colori dinamici per linee ===
    line_refs = sorted(set(str(data.get("ref")) for _, _, data in G_lines.edges(data=True) if "ref" in data))
    cmap = cm.get_cmap("tab20", len(line_refs))  # palette fino a 20 linee
    line_colors = {l: cmap(i) for i, l in enumerate(line_refs)}

    # Posizioni dai nodi (coordinate cartesiane vere)
    pos = {n: (G_lines.nodes[n]["x"], G_lines.nodes[n]["y"]) for n in G_lines.nodes()}

    # Disegna nodi
    nx.draw_networkx_nodes(G_lines, pos, node_size=600, node_color="lightblue")
    nx.draw_networkx_labels(G_lines, pos, font_size=10, font_color="black")

    # Disegna archi e prepara etichette
    for u, v, k, data in G_lines.edges(keys=True, data=True):
        line = str(data.get("ref", "?"))
        color = line_colors.get(line, "gray")

        # Rad positivo per una direzione, negativo per l'altra
        rad = 0.2 if (u < v) else -0.2

        # Disegna arco direzionale singolo
        nx.draw_networkx_edges(
            G_lines, pos, edgelist=[(u, v)],
            edge_color=color,
            width=1.5,
            arrows=True,
            arrowsize=15,
            connectionstyle=f"arc3,rad={rad}"
        )

        # === Etichetta multi-linea ===
        l = data.get("ref")
        h = data.get("segment")
        n_bus = w_sol.get((l, h), 0) if l is not None and h is not None else 0

        label = f"Linea {l}\n{n_bus} mod"
        if show_passengers and "pax" in data:
            label += f"\n{int(data['pax'])} pax"
        if show_length and "length" in data:
            label += f"\nlen={data['length']:.1f}"

        # Posizione etichetta: spostata sopra o sotto
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
        offset = 0.25 if rad > 0 else -0.25

        plt.text(xm, ym + offset, label,
                 fontsize=8, color="black",
                 ha="center", va="center",
                 bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"))

    # Legenda colori linee
    legend_elements = [Patch(facecolor=color, label=f"Linea {l}") for l, color in line_colors.items()]
    plt.legend(handles=legend_elements, loc="upper left", fontsize=8)

    plt.title("Rete bus", color="black")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.5)
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