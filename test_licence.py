import gurobipy
print("Messaggio di test", flush=True)
try:
    # Prova a leggere la versione di Gurobi
    version = gurobipy.gurobi.version()
    print(f"Gurobi è installato correttamente! Versione: {version}")
    
    # Prova a creare un semplice modello
    model = gurobipy.Model("test")
    x = model.addVar(name="x")
    y = model.addVar(name="y")
    
    # Funzione obiettivo semplice
    model.setObjective(x + y, gurobipy.GRB.MAXIMIZE)
    
    # Vincolo semplice
    model.addConstr(x + 2*y <= 4, "c0")
    
    # Ottimizza
    model.optimize()
    
    print("Modello risolto con successo!")
    for v in model.getVars():
        print(f"{v.varName} = {v.x}")

except gurobipy.GurobiError as e:
    print("Errore Gurobi:", e)
except Exception as e:
    print("Altro errore:", e)
