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
def save_results_model(model_obj, name_prefix, data, G_lines, type_f="cross"):
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
                 G_lines=G_lines, z_sol=z_sol, v_sol=v_sol, type_f=type_f)
    print(f"✅ Results saved for {name_prefix}")

    # === Return dinamico ===
    if v_sol is not None:
        return x_sol, w_sol, z_sol, v_sol
    else:
        return x_sol, w_sol, z_sol


# === CORE SAVE FUNCTION ===
def save_results(results_folder, prefix, x_sol, w_sol, data,
                 G_lines=None, z_sol=None, v_sol=None, type_f="cross"):
    """
    Salva tutte le informazioni del modello (BASE o FULL)
    in formato JSON e .ILP/.SOL.
    """
    if type_f == "cross":
        folder = os.path.join(results_folder, "cross")
        os.makedirs(folder, exist_ok=True)
    if type_f == "grid":
        folder = os.path.join(results_folder, "grid")
        os.makedirs(folder, exist_ok=True)

    # === x ===
    with open(os.path.join(folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump(
            [{"k": k, "i": i, "j": j, "l": l, "value": v}
             for (k, i, j, l), v in x_sol.items()],
            f, indent=2
        )

    # === w ===
    with open(os.path.join(folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump(
            [{"l": l, "h": h, "value": v}
             for (l, h), v in w_sol.items()],
            f, indent=2
        )

    # === z (se presente) ===
    if z_sol:
        with open(os.path.join(folder, f"{prefix}_solution_z.json"), "w") as f:
            json.dump(
                [{"k": k, "j": j, "value": v}
                 for (k, j), v in z_sol.items()],
                f, indent=2
            )

    # === v (se presente, solo nel modello FULL) ===
    if v_sol:
        with open(os.path.join(folder, f"{prefix}_solution_v.json"), "w") as f:
            json.dump(
                [{"i": i, "j": j, "value": v}
                 for (i, j), v in v_sol.items()],
                f, indent=2
            )

    # === Salva dati principali ===
    def stringify_keys(d):
        return {str(k): v for k, v in d.items()}

    with open(os.path.join(folder, f"{prefix}_data.json"), "w") as f:
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
        with open(os.path.join(folder, f"{prefix}_graph_edges.json"), "w") as f:
            json.dump(
                [
                    {"u": u, "v": v, "key": k, **attrs}
                    for u, v, k, attrs in G_lines.edges(keys=True, data=True)
                ],
                f, indent=2
            )

    # === Salva modello e soluzione Gurobi ===
    if "model" in data:
        ilp_path = os.path.join(folder, f"{prefix}_model.ilp")
        sol_path = os.path.join(folder, f"{prefix}_solution.sol")

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

    print(f"✅ Tutti i risultati salvati in: {folder}")







import json

def compute_VOS_VOR(data, w_rigid, w_semi, w_flex, v_flex=None, save_path="results/grid_VOS_VOR.json"):

    Q = data["Q"]

    # === CAPACITÀ TOTALE DISPONIBILE (TCAP) ===
    # Rigid: w_l costante lungo tutta la linea → somma su tutti gli archi della linea
    TCAP_rigid = Q * sum(
        sum(val for (l_, h_), val in data["t"].items() if l_ == int(l)) * w
        for l, w in w_rigid.items()
        )
    
    # Semi: somma sui segmenti
    TCAP_semi = Q * sum(data["t"][(int(l), h)] * w for (l, h), w in w_semi.items())

    # Flex: somma segmenti + archi di rebalancing
    TCAP_flex = Q * sum(data["t"][(int(l), h)] * w for (l, h), w in w_flex.items())
    if v_flex is not None:
        TCAP_flex += Q * sum(data["tr"][(i, j)] * v for (i, j), v in v_flex.items())

    # === INDICATORI ===
    VOS = (TCAP_rigid - TCAP_semi) / TCAP_rigid if TCAP_rigid else 0
    VOR = (TCAP_semi - TCAP_flex) / TCAP_semi if TCAP_semi else 0
    VOF = (TCAP_rigid - TCAP_flex) / TCAP_rigid if TCAP_rigid else 0

    results = {
        "TCAP_rigid": TCAP_rigid,
        "TCAP_semi": TCAP_semi,
        "TCAP_flex": TCAP_flex,
        "VOS": VOS,
        "VOR": VOR,
        "VOF": VOF
    }

    with open(save_path, "w") as f:
        json.dump(results, f, indent=4)

    print("\n===== FLEXIBILITY INDICATORS =====")
    print(f"TCAP rigid : {TCAP_rigid:.2f}")
    print(f"TCAP semi  : {TCAP_semi:.2f}")
    print(f"TCAP flex  : {TCAP_flex:.2f}")
    print(f"VOS (sharing): {VOS*100:.2f}%")
    print(f"VOR (rebal.): {VOR*100:.2f}%")
    print(f"VOF (total) : {VOF*100:.2f}%")
    print(f"Results saved to {save_path}")

    return results
