### Versione BASE ###
### Solo assegnazione delle richieste alle tratte dei bus:
###  - senza ribilanciamento (no variabili v)
###  - senza deviazioni/vambi di linea (no variabili z)

from gurobipy import Model, GRB, quicksum



class MBA_ILP_BASE:
    def __init__(self, data):
        """
        Modello BASE (solo x e v, no z e w)
        data_sets: dizionario con set e parametri dal data loader
        Es: data_sets['L'], data_sets['N'], data_sets['K'], ecc.
        """
        self.data = data
        self.model = Model("MBA_ILP_BASE")


    # === COSTRUZIONE MODELLO ===
    def build(self):
        d = self.data
        L, N, K, Pk, p, Q, t = d["L"], d["N"], d["K"], d["Pk"], d["p"], d["Q"], d["t"]

        # === Variabili ===
        x = {}  # x_{kijℓ}
        for k in K:
            for (i, j, l, h) in Pk[k]:  # Pk[k] contiene archi con sezione associata
                x[k, i, j, l, h] = self.model.addVar(vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}_{h}")

        w = {}  # w_{ℓh}
        for l in L:
            for h, seg in enumerate(N[l]):
                w[l, h] = self.model.addVar(vtype=GRB.INTEGER, lb=0, name=f"w_{l}_{h}")

        self.model.update()

        # === Obiettivo ===
        self.model.setObjective(
            quicksum(t[l, h] * w[l, h] for l in L for h, seg in enumerate(N[l])),
            GRB.MINIMIZE
        )

        # === Vincoli: ogni richiesta deve scegliere un percorso ===
        for k in K:
            for (i, j) in {(i, j) for (i, j, l, h) in Pk[k]}:
                self.model.addConstr(
                    quicksum(x[k, i, j, l, h] for (ii, jj, l, h) in Pk[k] if (ii, jj) == (i, j)) == 1,
                    name=f"path_{k}_{i}_{j}"
                )

        # === Vincoli: capacità moduli ===
        for l in L:
            for h, seg in enumerate(N[l]):
                self.model.addConstr(
                    quicksum(p[k] * x[k, i, j, l, h] 
                            for k in K 
                            for (i, j, ll, hh) in Pk[k] if ll == l and hh == h) 
                    <= Q * w[l, h],
                    name=f"capacity_{l}_{h}"
                )

        self.model.update()


    def solve(self):
        self.model.optimize()
        if self.model.status == GRB.OPTIMAL:
            print("Optimal solution found")
            for v in self.model.getVars():
                if v.X > 1e-6:
                    print(f"{v.VarName} = {v.X}")


    def get_solution(self):
        x_sol = {}
        w_sol = {}

        for v in self.model.getVars():
            if v.VarName.startswith("x") and v.X > 1e-6:
                # x_{k}_{i}_{j}_{l}_{h} → estrai le chiavi
                parts = v.VarName.split("_")
                k, i, j, l, h = map(int, parts[1:])
                x_sol[k, i, j, l, h] = v.X
            elif v.VarName.startswith("w") and v.X > 1e-6:
                l, h = map(int, v.VarName.split("_")[1:])
                w_sol[l, h] = int(v.X)

        return x_sol, w_sol