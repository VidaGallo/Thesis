import os
import json
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch
import random


# === DISPLAY FUNCTION ===
def display_results(model_obj, name_prefix, data):
    """
    Mostra i risultati del modello (x, w, z, v se presente).
    Funziona per entrambi i casi: BASE e FULL.
    """
    print(f"\n\n######## DISPLAY RESULTS: {name_prefix} ########")

    # === DISPLAY: x ===
    print("\n === x_k_i_j_l (arcs used by requests) ===")
    found_x = False
    for var in model_obj.model.getVars():
        if var.VarName.startswith("x") and var.X > 1e-6:
            print(var.VarName, var.X)
            found_x = True
    if not found_x:
        print("Nessuna variabile x attiva.")

    # === DISPLAY: w ===
    print("\n=== w_l_h (modules per segment) ===")
    found_w = False
    for l, segs in data["Nl"].items():
        for h, seg in enumerate(segs):
            var_name = f"w_{l}_{h}"
            var = model_obj.model.getVarByName(var_name)
            if var and var.X > 1e-6:
                print(f"Linea {l}, segmento {h}, seg={seg}, w={var.X}, t={data['t'].get((l,h))}")
                found_w = True
    if not found_w:
        print("Nessuna variabile w attiva.")

    # === DISPLAY: z ===
    print("\n=== z_k_j (line changes) ===")
    found_z = False
    for k in range(len(data["K"])):
        for j in data["J"]:
            var_name = f"z_{k}_{j}"
            var = model_obj.model.getVarByName(var_name)
            if var and var.X > 1e-6:
                print(f"Richiesta {k}, nodo j={j}: z={var.X}")
                found_z = True
    if not found_z:
        print("Nessuna variabile z attiva.")

    # === DISPLAY: v ===
    print("\n=== v_i_j (rebalance flows) ===")
    found_v = False
    for var in model_obj.model.getVars():
        if var.VarName.startswith("v") and var.X > 1e-6:
            print(var.VarName, var.X)
            found_v = True
    if not found_v:
        print("Nessun flusso di riequilibrio attivo (v).")


# === SAVE FUNCTION ===
def save_results_model(model_obj, name_prefix, data, G_lines):
    """
    Estrae le soluzioni dal modello e le salva nei file JSON/ILP.
    - Compatibile con BASE (x,w,z) e FULL (x,w,z,v)
    - Ritorna solo le variabili effettivamente presenti
    """
    # === Estrazione soluzioni dal modello ===
    get_sol = model_obj.get_solution()
    if len(get_sol) == 3:
        x_sol, w_sol, z_sol = get_sol
        v_sol = None
    elif len(get_sol) == 4:
        x_sol, w_sol, z_sol, v_sol = get_sol
    else:
        raise ValueError("Formato della soluzione non riconosciuto: attesi 3 o 4 elementi.")

    data["model"] = model_obj.model

    # === Salvataggio su file ===
    save_results("results", name_prefix, x_sol, w_sol, data,
                 G_lines=G_lines, z_sol=z_sol, v_sol=v_sol)
    print(f"✅ Results saved for {name_prefix}")

    # === Return dinamico ===
    if v_sol is not None:
        return x_sol, w_sol, z_sol, v_sol
    else:
        return x_sol, w_sol, z_sol


# === CORE SAVE FUNCTION ===
def save_results(results_folder, prefix, x_sol, w_sol, data,
                 G_lines=None, z_sol=None, v_sol=None):
    """
    Salva tutte le informazioni del modello (BASE o FULL)
    in formato JSON e .ILP/.SOL.
    """
    cross_folder = os.path.join(results_folder, "cross")
    os.makedirs(cross_folder, exist_ok=True)

    # === x ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump(
            [{"k": k, "i": i, "j": j, "l": l, "value": v}
             for (k, i, j, l), v in x_sol.items()],
            f, indent=2
        )

    # === w ===
    with open(os.path.join(cross_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump(
            [{"l": l, "h": h, "value": v}
             for (l, h), v in w_sol.items()],
            f, indent=2
        )

    # === z (se presente) ===
    if z_sol:
        with open(os.path.join(cross_folder, f"{prefix}_solution_z.json"), "w") as f:
            json.dump(
                [{"k": k, "j": j, "value": v}
                 for (k, j), v in z_sol.items()],
                f, indent=2
            )

    # === v (se presente, solo nel modello FULL) ===
    if v_sol:
        with open(os.path.join(cross_folder, f"{prefix}_solution_v.json"), "w") as f:
            json.dump(
                [{"i": i, "j": j, "value": v}
                 for (i, j), v in v_sol.items()],
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

    # === Salva il grafo (solo se presente) ===
    if G_lines:
        with open(os.path.join(cross_folder, f"{prefix}_graph_edges.json"), "w") as f:
            json.dump(
                [
                    {"u": u, "v": v, "key": k, **attrs}
                    for u, v, k, attrs in G_lines.edges(keys=True, data=True)
                ],
                f, indent=2
            )

    # === Salva modello e soluzione Gurobi ===
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



import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.cm as cm
from matplotlib.patches import Patch
import random

def plot_comparison_base_full(G_lines, G_reb, w_base, w_full, v_full):
    """
    Confronta visualmente il modello BASE e FULL:
    - BASE: solo archi delle linee bus (etichette w)
    - FULL: include anche archi di rebalance (etichette w e v)
    - Ogni arco direzionale (i→j) è disegnato separatamente.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    titles = ["BASE (senza riequilibrio)", "FULL (con riequilibrio)"]
    cmap = cm.get_cmap("tab20")

    pos = {n: (G_lines.nodes[n]['x'], G_lines.nodes[n]['y']) for n in G_lines.nodes()}

    for ax_idx, ax in enumerate(axes):
        plt.sca(ax)
        ax.set_title(titles[ax_idx], fontsize=13, fontweight="bold")
        ax.axis("off")

        # Disegna nodi
        nx.draw_networkx_nodes(G_lines, pos, node_size=450, node_color="lightblue", ax=ax)
        nx.draw_networkx_labels(G_lines, pos, font_size=9, font_color="black", ax=ax)

        # --- Disegna archi direzionali delle linee bus
        for u, v, key, data in G_lines.edges(keys=True, data=True):
            l = data.get("ref")
            color = cmap(int(l) % 20)

            # offset curvo in base alla direzione per distinguere 0→1 e 1→0
            rad = 0.25 if u < v else -0.25

            nx.draw_networkx_edges(G_lines, pos, edgelist=[(u, v)],
                                   edge_color=color, width=2.0,
                                   connectionstyle=f"arc3,rad={rad}",
                                   arrows=True, arrowsize=14, ax=ax)

            # Etichetta w su ciascun arco
            for h in range(10):
                w_dict = w_full if ax_idx else w_base
                if (l, h) in w_dict and w_dict[(l, h)] > 0:
                    w_val = w_dict[(l, h)]
                    x1, y1 = pos[u]
                    x2, y2 = pos[v]
                    xm, ym = (x1 + x2)/2, (y1 + y2)/2

                    # offset differenziato per direzioni opposte
                    offset_y = (0.25 if rad > 0 else -0.25) + random.uniform(-0.05, 0.05)
                    offset_x = random.uniform(-0.1, 0.1)

                    ax.text(xm + offset_x, ym + offset_y, f"w={w_val}",
                            fontsize=8, color="black", ha="center",
                            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))

        # --- SOLO FULL: archi di rebalance
        if ax_idx == 1 and v_full:
            for (i, j), val in v_full.items():
                if val > 1e-6:
                    rad = 0.15 if i < j else -0.15
                    nx.draw_networkx_edges(G_reb, pos, edgelist=[(i, j)],
                                           edge_color="red", width=2,
                                           style="dashed", arrows=True,
                                           connectionstyle=f"arc3,rad={rad}",
                                           arrowsize=12, ax=ax)
                    x1, y1 = pos[i]
                    x2, y2 = pos[j]
                    xm, ym = (x1 + x2)/2, (y1 + y2)/2

                    # offset visivo
                    offset_y = (0.15 if rad > 0 else -0.15)
                    offset_x = random.uniform(-0.05, 0.05)

                    ax.text(xm + offset_x, ym + offset_y, f"v={val:.1f}",
                            fontsize=8, color="red", ha="center",
                            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))

    # --- Legenda
    legend_elements = [
        Patch(facecolor='lightblue', label='Nodi'),
        Patch(facecolor='red', label='Rebalance (v)', edgecolor='red')
    ]
    plt.legend(handles=legend_elements, loc='upper center', ncol=2, fontsize=9)
    plt.tight_layout()
    plt.show()
