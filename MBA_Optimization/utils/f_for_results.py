import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch
import os
import json




def plot_bus_network(G_lines, w_sol, x_sol=None, z_sol=None,
                     show_passengers=False, show_length=False):
    """
    Disegna la rete direttamente dal grafo G_lines.
    - w_sol: moduli assegnati alle sezioni (dict {(l,h): val})
    - x_sol: assegnamento richieste su archi (opzionale, dict {(k,i,j,l,h): val})
    - z_sol: cambi linea ai nodi (opzionale, dict {(k,j): val})
    - show_passengers: mostra il numero di passeggeri sugli archi se presente in G_lines
    - show_length: mostra la lunghezza degli archi
    """

    # === Colori per linee ===
    line_refs = sorted(set(str(data.get("ref")) for _, _, data in G_lines.edges(data=True) if "ref" in data))
    cmap = cm.get_cmap("tab20", len(line_refs))
    line_colors = {l: cmap(i) for i, l in enumerate(line_refs)}

    # Posizioni dei nodi
    pos = {n: (G_lines.nodes[n]["x"], G_lines.nodes[n]["y"]) for n in G_lines.nodes()}

    # Disegna nodi
    nx.draw_networkx_nodes(G_lines, pos, node_size=600, node_color="lightblue")
    nx.draw_networkx_labels(G_lines, pos, font_size=10, font_color="black")

    # Disegna archi
    for u, v, k, data in G_lines.edges(keys=True, data=True):
        line = str(data.get("ref", "?"))
        color = line_colors.get(line, "gray")

        # Rad positivo/negativo per distinguere direzioni
        rad = 0.2 if (u < v) else -0.2

        nx.draw_networkx_edges(
            G_lines, pos, edgelist=[(u, v)],
            edge_color=color,
            width=1.5,
            arrows=True,
            arrowsize=15,
            connectionstyle=f"arc3,rad={rad}"
        )

        # === Etichetta su arco ===
        l = data.get("ref")
        h = data.get("segment")
        n_bus = w_sol.get((l, h), 0) if l is not None and h is not None else 0

        label = f"Linea {l}\n{n_bus} mod"
        if show_passengers and "pax" in data:
            label += f"\n{int(data['pax'])} pax"
        if show_length and "length" in data:
            label += f"\nlen={data['length']:.1f}"

        # posizione etichetta a metà arco
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
        offset = 0.25 if rad > 0 else -0.25

        plt.text(xm, ym + offset, label,
                 fontsize=8, color="black",
                 ha="center", va="center",
                 bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"))

    # Evidenzia cambi linea (z_sol)
    if z_sol:
        for (k, j), val in z_sol.items():
            if val > 0.5 and j in pos:
                x, y = pos[j]
                plt.scatter([x], [y], color="red", s=200,
                            marker="x", linewidths=2, zorder=10)

    # Legenda
    legend_elements = [Patch(facecolor=color, label=f"Linea {l}") for l, color in line_colors.items()]
    if z_sol:
        legend_elements.append(Patch(facecolor="red", label="Cambio linea", edgecolor="red"))
    plt.legend(handles=legend_elements, loc="upper left", fontsize=8)

    plt.title("Rete bus", color="black")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.show()





def save_results(results_folder, prefix, x_sol, w_sol, data,
                 G_lines=None, z_sol=None):
    # === Crea le cartelle se non esistono ===
    cross_folder = os.path.join(results_folder, "cross")
    os.makedirs(cross_folder, exist_ok=True)

    # === Salva variabili x ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump(
            [
                {"k": k, "i": i, "j": j, "l": l, "value": v}
                for (k, i, j, l), v in x_sol.items()
            ],
            f, indent=2
        )

    # === Salva variabili w ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump(
            [
                {"l": l, "h": h, "value": v}
                for (l, h), v in w_sol.items()
            ],
            f, indent=2
        )

    # === Salva z se presente ===
    if z_sol:
        with open(os.path.join(cross_folder, f"{prefix}_solution_z.json"), "w") as f:
            json.dump(
                [
                    {"k": k, "j": j, "value": v}
                    for (k, j), v in z_sol.items()
                ],
                f, indent=2
            )

    # === Salva dati principali ===
    def stringify_keys(d):
        return {str(k): v for k, v in d.items()}

    with open(os.path.join(cross_folder, f"{prefix}_data.json"), "w") as f:
        json.dump(
            {
                "t": stringify_keys(data["t"]),
                "Q": data["Q"],
                "K": data["K"]
            },
            f, indent=2
        )

    # === Salva info sul grafo se richiesto ===
    if G_lines:
        with open(os.path.join(cross_folder, f"{prefix}_graph_edges.json"), "w") as f:
            json.dump(
                [
                    {"u": u, "v": v, "key": k, **attrs}
                    for u, v, k, attrs in G_lines.edges(keys=True, data=True)
                ],
                f, indent=2
            )

    # === Salva il modello Gurobi in formato ILP (se presente in data) ===
    if "model" in data:
        ilp_path = os.path.join(cross_folder, f"{prefix}_model.ilp")
        try:
            data["model"].write(ilp_path)
            print(f"✅ Modello salvato in formato ILP: {ilp_path}")
        except Exception as e:
            print(f"⚠️ Errore nel salvataggio del modello ILP: {e}")

        # (Facoltativo) salva anche la soluzione .sol di Gurobi
        try:
            sol_path = os.path.join(cross_folder, f"{prefix}_solution.sol")
            data["model"].write(sol_path)
            print(f"✅ Soluzione salvata in formato .sol: {sol_path}")
        except Exception as e:
            print(f"⚠️ Errore nel salvataggio del file .sol: {e}")

    print(f"✅ Tutti i risultati salvati in: {cross_folder}")
