import os
import json
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch



# === DISPLAY FUNCTION ===
def display_results(model_obj, name_prefix, data):
    """
    Mostra i risultati del modello (x, z, w) per debug o analisi.
    Non salva nulla su file.
    """
    print(f"\n\n######## DISPLAY RESULTS: {name_prefix} ########")

    # === DISPLAY: x ===
    print("\n === x_k_i_j_l (arcs used by requests) ===")
    for v in model_obj.model.getVars():
        if v.VarName.startswith("x") and v.X > 1e-6:
            print(v.VarName, v.X)

    # === DISPLAY: z ===
    print("\n=== z_k_j (line changes) ===")
    for k in range(len(data["K"])):
        for j in data["J"]:
            var_name = f"z_{k}_{j}"
            var = model_obj.model.getVarByName(var_name)
            val = var.X if var is not None else None
            print(f"Richiesta {k}, nodo j={j}: z={val}")

    # === DISPLAY: w ===
    print("\n=== w_l_h (modules per segment) ===")
    for l, segs in data["Nl"].items():
        for h, seg in enumerate(segs):
            var_name = f"w_{l}_{h}"
            var = model_obj.model.getVarByName(var_name)
            val = var.X if var is not None else None
            print(f"Linea {l}, segmento {h}, seg={seg}, w={val}, t={data['t'].get((l,h))}")


# === SAVE FUNCTION ===
def save_results_model(model_obj, name_prefix, data, G_lines):
    """
    Estrae le soluzioni dal modello e le salva nei file JSON/ILP.
    Non stampa nulla a schermo.
    """
    # Estrai soluzioni
    x_sol, w_sol, z_sol = model_obj.get_solution()
    data["model"] = model_obj.model

    # Salva su file
    save_results("results", name_prefix, x_sol, w_sol, data,
                 G_lines=G_lines, z_sol=z_sol)
    print(f"✅ Results saved for {name_prefix}")

    return x_sol, w_sol, z_sol


# === CORE SAVE FUNCTION ===
def save_results(results_folder, prefix, x_sol, w_sol, data,
                 G_lines=None, z_sol=None):
    """
    Salva tutte le informazioni del modello in formato JSON e .ILP/.SOL.
    """
    cross_folder = os.path.join(results_folder, "cross")
    os.makedirs(cross_folder, exist_ok=True)

    # === Salva variabili x ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump(
            [{"k": k, "i": i, "j": j, "l": l, "value": v} for (k, i, j, l), v in x_sol.items()],
            f, indent=2
        )

    # === Salva variabili w ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump(
            [{"l": l, "h": h, "value": v} for (l, h), v in w_sol.items()],
            f, indent=2
        )

    # === Salva z se presente ===
    if z_sol:
        with open(os.path.join(cross_folder, f"{prefix}_solution_z.json"), "w") as f:
            json.dump(
                [{"k": k, "j": j, "value": v} for (k, j), v in z_sol.items()],
                f, indent=2
            )

    # === Salva dati principali ===
    def stringify_keys(d):
        return {str(k): v for k, v in d.items()}

    with open(os.path.join(cross_folder, f"{prefix}_data.json"), "w") as f:
        json.dump(
            {"t": stringify_keys(data["t"]), "Q": data["Q"], "K": data["K"]},
            f, indent=2
        )

    # === Salva info sul grafo se richiesto ===
    if G_lines:
        with open(os.path.join(cross_folder, f"{prefix}_graph_edges.json"), "w") as f:
            json.dump(
                [{"u": u, "v": v, "key": k, **attrs} for u, v, k, attrs in G_lines.edges(keys=True, data=True)],
                f, indent=2
            )

    # === Salva il modello Gurobi in formato ILP e .SOL ===
    if "model" in data:
        ilp_path = os.path.join(cross_folder, f"{prefix}_model.ilp")
        sol_path = os.path.join(cross_folder, f"{prefix}_solution.sol")
        try:
            data["model"].write(ilp_path)
            print(f"✅ Modello salvato in formato ILP: {ilp_path}")
        except Exception as e:
            print(f"⚠️ Errore nel salvataggio ILP: {e}")
        try:
            data["model"].write(sol_path)
            print(f"✅ Soluzione salvata in formato .sol: {sol_path}")
        except Exception as e:
            print(f"⚠️ Errore nel salvataggio SOL: {e}")

    print(f"✅ Tutti i risultati salvati in: {cross_folder}")




def plot_bus_network(G_lines, data, w_sol=None, x_sol=None, z_sol=None,
                     show_passengers=False, show_length=False, title="Rete bus"):
    """
    Disegna la rete dei bus a partire dal grafo multilinea.
    Parametri:
      - G_lines: grafo MultiDiGraph con attributi 'ref' (linea) e coordinate (x, y)
      - data: dizionario dati del modello (serve per Nl e t)
      - w_sol: dict {(l,h): n_moduli}
      - x_sol: dict opzionale {(k,i,j,l): 1 se arco usato}
      - z_sol: dict opzionale {(k,j): 1 se cambio linea}
      - show_passengers: se True mostra eventuali pax su archi
      - show_length: se True mostra la lunghezza archi
    """

    w_sol = w_sol or {}
    x_sol = x_sol or {}
    z_sol = z_sol or {}

    # === 1. Colori per linee ===
    line_refs = sorted({str(data.get("ref")) for _, _, data in G_lines.edges(data=True) if "ref" in data})
    cmap = cm.get_cmap("tab10", len(line_refs))
    line_colors = {l: cmap(i) for i, l in enumerate(line_refs)}

    # === 2. Coordinate nodi (x,y)
    pos = {n: (G_lines.nodes[n]["x"], G_lines.nodes[n]["y"]) for n in G_lines.nodes()}

    # === 3. Disegna nodi base ===
    nx.draw_networkx_nodes(G_lines, pos, node_size=500, node_color="lightblue", edgecolors="black", linewidths=0.8)
    nx.draw_networkx_labels(G_lines, pos, font_size=9, font_color="black")

    # === 4. Disegna archi colorati per linea ===
    for u, v, k, attr in G_lines.edges(keys=True, data=True):
        l = str(attr.get("ref", "?"))
        color = line_colors.get(l, "gray")
        rad = 0.15 if u < v else -0.15

        nx.draw_networkx_edges(
            G_lines, pos, edgelist=[(u, v)],
            edge_color=color, width=1.8, arrows=True, arrowsize=12,
            connectionstyle=f"arc3,rad={rad}"
        )

        # Etichetta moduli
        h = attr.get("segment")
        n_bus = w_sol.get((l, h), 0)
        label = f"L{l}: {n_bus} mod"

        if show_passengers and "pax" in attr:
            label += f"\n{int(attr['pax'])} pax"
        if show_length and "length" in attr:
            label += f"\nlen={attr['length']:.1f}"

        # posizione testo al centro arco
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
        plt.text(xm, ym + (0.15 if rad > 0 else -0.15), label,
                 fontsize=7, color="black",
                 ha="center", va="center",
                 bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"))

    # === 5. Evidenzia cambi linea (z_sol) ===
    if z_sol:
        for (k, j), val in z_sol.items():
            if val > 0.5 and j in pos:
                x, y = pos[j]
                plt.scatter([x], [y], color="red", s=180, marker="x", linewidths=2.2, zorder=10)

    # === 6. Legenda ===
    legend_elements = [Patch(facecolor=c, label=f"Linea {l}") for l, c in line_colors.items()]
    if z_sol:
        legend_elements.append(Patch(facecolor="none", edgecolor="red", label="Cambio linea", linewidth=2))
    plt.legend(handles=legend_elements, loc="upper left", fontsize=8)

    # === 7. Aspetto grafico ===
    plt.title(title, fontsize=12, color="black")
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.show()