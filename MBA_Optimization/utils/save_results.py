import os
import json

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
        json.dump({str(k): v for k, v in x_sol.items()}, f, indent=2)

    # Salva w
    with open(os.path.join(results_folder, f"{prefix}_solution_w.json"), "w") as f:
        json.dump({str(k): v for k, v in w_sol.items()}, f, indent=2)

    # Salva dati principali
    with open(os.path.join(results_folder, f"{prefix}_data.json"), "w") as f:
        json.dump({
            "t": data["t"],
            "Q": data["Q"],
            "K": data["K"]
        }, f, indent=2)
