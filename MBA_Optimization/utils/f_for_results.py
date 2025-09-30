import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import os
import json

def plot_bus_network(N, w_sol, x_sol=None, show_passengers=False):
    """
    Visualizza la rete dei bus con numero di bus assegnati (w_sol) e opzionalmente flusso passeggeri (x_sol).
    Gestisce più linee distinte.

    Parameters:
    - N : dict, line_ref -> lista segmenti (tuple di nodi)
    - w_sol : dict, (l,h) -> numero di bus assegnati
    - x_sol : dict, (k,i,j,l,h) -> flusso passeggeri (opzionale)
    - show_passengers : bool, se True mostra anche flusso passeggeri sugli archi
    """

    G_vis = nx.DiGraph()

    # Colori per linee
    line_list = list(N.keys())
    color_map = cm.get_cmap('tab10', len(line_list))
    line_colors = {l: color_map(i) for i,l in enumerate(line_list)}

    edge_labels = {}
    edge_colors = []
    edge_widths = []

    # Costruisci archi linea-specifici
    for l, seg_list in N.items():
        color = line_colors[l]
        for h, seg in enumerate(seg_list):
            n_bus = w_sol.get((l,h), 0)
            n_pass = 0
            if show_passengers and x_sol is not None:
                for (k,i,j,ll,hh), val in x_sol.items():
                    if ll==l and hh==h and val>0:
                        if (i,j) in [(seg[x], seg[x+1]) for x in range(len(seg)-1)]:
                            n_pass += val
            for i in range(len(seg)-1):
                u, v = seg[i], seg[i+1]
                # arco linea-specifico
                G_vis.add_edge(u, v, line=l, segment=h)
                # etichetta
                label = f"L{l}: {n_bus} mod"
                if n_pass > 0:
                    label += f"\n{int(n_pass)} pax"
                edge_labels[(u,v,l)] = label
                edge_colors.append(color)
                edge_widths.append(1 + n_bus/3)  # spessore proporzionale a w

    # Posizione nodi
    pos = nx.spring_layout(G_vis, seed=42)

    # Disegna nodi
    nx.draw(G_vis, pos, with_labels=True, node_size=500, node_color='lightblue')

    # Disegna archi linea-specifici
    for u,v,l in edge_labels.keys():
        nx.draw_networkx_edges(
            G_vis, pos, edgelist=[(u,v)],
            width=edge_widths.pop(0),
            edge_color=[edge_colors.pop(0)]
        )

    # Etichette archi
    nx.draw_networkx_edge_labels(
        G_vis, pos,
        edge_labels={ (u,v): lbl for (u,v,l), lbl in edge_labels.items() },
        font_color='red', font_size=8
    )

    plt.title("Rete bus: numero di bus per segmento" + (" + flusso passeggeri" if show_passengers else ""))
    plt.show()






def save_results(results_folder, prefix, x_sol, w_sol, data):
    """
    Salva le soluzioni e i parametri principali in JSON.
    
    Parameters:
    - results_folder: cartella dove salvare i file
    - prefix: stringa per distinguere i file (es: 'cross_BASE')
    - x_sol: dizionario variabili x {(k,i,j,l,h): valore}
    - w_sol: dizionario variabili w {(l,h): valore}
    - data: dizionario contenente almeno data['t'], data['Q'], data['K']
    """
    os.makedirs(results_folder, exist_ok=True)

    # Salva x
    with open(os.path.join(results_folder, f"{prefix}_solution_x.json"), "w") as f:
        json.dump([{"k": k, "i": i, "j": j, "l": l, "h": h, "value": v} 
                for (k,i,j,l,h), v in x_sol.items()], f, indent=2)

    # Salva w
    with open(os.path.join(results_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump([{"l": l, "h": h, "value": v} 
                for (l,h), v in w_sol.items()], f, indent=2)



    # Salva dati principali
    with open(os.path.join(results_folder, f"{prefix}_data.json"), "w") as f:
        json.dump({
            "t": data["t"],
            "Q": data["Q"],
            "K": data["K"]
        }, f, indent=2)
