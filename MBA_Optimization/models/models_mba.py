### Versione BASE ###
### Solo assegnazione delle richieste alle tratte dei bus:
###  - senza ribilanciamento (no variabili v)
###  - senza deviazioni/vambi di linea (no variabili z)

from gurobipy import Model, GRB, quicksum





class MBA_ILP_RIGID:
    def __init__(self, data):
        """
        Modello BASE (solo x e v, no z e w)
        data_sets: dizionario con set e parametri dal data loader
        Es: data_sets['L'], data_sets['N'], data_sets['K'], ecc.
        """
        self.data = data
        self.model = Model("MBA_ILP_RIGID")
        self.x = {}
        self.w = {}
        self.z = {}



    # === COSTRUZIONE MODELLO ===
    def build(self):
        d = self.data
        K, p, Pk, Akl, Blk = d["K"], d["p"], d["Pk"], d["Akl"], d["Blk"]
        L, A, S, J, T, Nl = d["L"], d["A"], d["S"], d["J"], d["T"], d["Nl"]
        Delta_plus, Delta_minus = d["Delta_plus"], d["Delta_minus"]
        t, Q = d["t"], d["Q"]
        alpha = d["alpha"]

        # === Variabili ===
        # x_{k,i,j,l}
        for k in K:
            for (i, j, l) in A:
                self.x[k, i, j, l] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}"
                )
        # w_{l,h}
        for l, segs in Nl.items():
            for h in range(len(segs)):
                self.w[l, h] = self.model.addVar(
                    vtype=GRB.INTEGER, lb=0, name=f"w_{l}_{h}"
                )
        # z_{k,j}
        for k in K:
            for j in (J):  
                self.z[k, j] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"z_{k}_{j}"
                )

        self.model.update()

        # === Funzione Obiettivo ===
        obj = quicksum(t[l, h] * self.w[l, h] for (l, h) in self.w)
        obj += alpha * quicksum(p[k] * self.z[k, j] for (k, j) in self.z)
        self.model.setObjective(obj, GRB.MINIMIZE)


        # === Vincoli ===
        # (1) Assegnazione: ogni arco del path della richiesta k deve essere servito da una sola linea
        for k in K:
            path = Pk[k]
            for (i, j) in zip(path[:-1], path[1:]):
                # Linee che servono questo arco
                valid_lines = [l for (ii, jj, l) in A if (ii, jj) == (i, j)]

                # Crea variabili x solo per le linee compatibili
                for l in valid_lines:
                    if (k, i, j, l) not in self.x:
                        self.x[k, i, j, l] = self.model.addVar(vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}")

                # Vincolo di assegnazione: somma delle x deve essere 1
                if valid_lines:
                    expr = quicksum(self.x[k, i, j, l] for l in valid_lines)
                    self.model.addConstr(expr == 1, name=f"assign_{k}_{i}_{j}")
                else:
                    print(f"⚠️ Nessuna linea collega ({i},{j}) per la richiesta {k} → vincolo saltato")


        
        # (2) Continuità su S
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in S:
                    self.model.addConstr(
                        self.x[k, i, j, l] == self.x[k, j, m, l],
                        name=f"contS_{k}_{l}_{i}_{j}_{m}"
                    )


        # (3) Continuità su J
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in J:
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] <= self.z[k, j],
                        name=f"contJ_plus_{k}_{l}_{i}_{j}_{m}"
                    )
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] >= -self.z[k, j],
                        name=f"contJ_minus_{k}_{l}_{i}_{j}_{m}"
                    )

        """
        # (4) Capacità per segmento h della linea l — DIREZIONALE
        for l, segs in Nl.items():
            for h, seg in enumerate(segs):
                arcs_h = [(seg[i], seg[i+1]) for i in range(len(seg) - 1)]
                self.model.addConstr(
                    quicksum(
                        p[k] * self.x[k, i, j, l]
                        for k in K
                        for (i, j) in arcs_h
                        if (k, i, j, l) in self.x        # evita key error
                    ) <= Q * self.w[l, h],
                    name=f"capacity_{l}_{h}"
                )
        """
        # (4) Capacità per segmento h della linea l — PER ARCO
        for l, segs in Nl.items():
            for h, seg in enumerate(segs):
                arcs_h = [(seg[ii], seg[ii+1]) for ii in range(len(seg) - 1)]
                for (i, j) in arcs_h:
                    self.model.addConstr(
                        quicksum(p[k] * self.x[k, i, j, l] for k in K) <= Q * self.w[l, h],
                        name=f"cap_l{l}_h{h}_{i}_{j}"
                    )            

        

        # (5) Moduli/bus COSTANTI per linea: w[l,h] = w[l,0] per ogni h
        for l, segs in Nl.items():
            for h in range(1, len(segs)):
                self.model.addConstr(self.w[l, h] == self.w[l, 0], name=f"constW_{l}_{h}")

        """    
        # (5) Conservazione flussi ai nodi speciali (T e J)
        for j in (set(J) | set(T)):
            incoming = [self.w[ell, h] for (ell, h) in Delta_minus.get(j, [])]   # Se j non è presente, ritorna la lista vuota []
            outgoing = [self.w[ell, h] for (ell, h) in Delta_plus.get(j, [])]    # Se j non è presente, ritorna la lista vuota []
            self.model.addConstr(quicksum(incoming) == quicksum(outgoing),
                                 name=f"w_flow_{j}")
        """

        

    # === RISOLUIZONE MODELLO ===
    def solve(self):
        self.model.optimize()
        print(f"Optimization status: {self.model.Status}")
        if self.model.Status == GRB.INFEASIBLE:
            print("⚠️ Modello infeasible, calcolo IIS...")
            # Gurobi cerca di individuare quali vincoli (o bounds) creano l’infeasibilità.
            # model.ilp.iis file che contiene solo quei vincoli
            self.model.computeIIS()
            self.model.write("results/cross/model.ilp")     # modello completo
            self.model.write("results/cross/model.iis.ilp")  # vincoli che creano conflitto e rendono il modello unfeasable




    # === ESTRAZIONE SOLUZIONE ===
    def get_solution(self):
        x_sol, w_sol, z_sol = {}, {}, {}

        if self.model.Status != GRB.OPTIMAL:   # Se non c’è soluzione ottima, ritorna vuoto
            return x_sol, w_sol, z_sol

        for v in self.model.getVars():
            if v.VarName.startswith("x") and v.X > 1e-6:
                _, k, i, j, ell = v.VarName.split("_")
                k, i, j = int(k), int(i), int(j)
                x_sol[(k, i, j, ell)] = 1
            elif v.VarName.startswith("w") and v.X > 1e-6:
                _, ell, h = v.VarName.split("_")
                h = int(h)
                w_sol[(ell, h)] = int(round(v.X))
            elif v.VarName.startswith("z") and v.X > 1e-6:
                _, k, j = v.VarName.split("_")
                k, j = int(k), int(j)
                z_sol[(k, j)] = 1
        return x_sol, w_sol, z_sol
    




class MBA_ILP_SEMI:
    def __init__(self, data):
        """
        Modello BASE (solo x e v, no z e w)
        data_sets: dizionario con set e parametri dal data loader
        Es: data_sets['L'], data_sets['N'], data_sets['K'], ecc.
        """
        self.data = data
        self.model = Model("MBA_ILP_SEMI")
        self.x = {}
        self.w = {}
        self.z = {}



    # === COSTRUZIONE MODELLO ===
    def build(self):
        d = self.data
        K, p, Pk, Akl, Blk = d["K"], d["p"], d["Pk"], d["Akl"], d["Blk"]
        L, A, S, J, T, Nl = d["L"], d["A"], d["S"], d["J"], d["T"], d["Nl"]
        Delta_plus, Delta_minus = d["Delta_plus"], d["Delta_minus"]
        t, Q = d["t"], d["Q"]
        alpha = d["alpha"]

        # === Variabili ===
        # x_{k,i,j,l}
        for k in K:
            for (i, j, l) in A:
                self.x[k, i, j, l] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}"
                )
        # w_{l,h}
        for l, segs in Nl.items():
            for h in range(len(segs)):
                self.w[l, h] = self.model.addVar(
                    vtype=GRB.INTEGER, lb=0, name=f"w_{l}_{h}"
                )
        # z_{k,j}
        for k in K:
            for j in (J):  
                self.z[k, j] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"z_{k}_{j}"
                )

        self.model.update()

        # === Funzione Obiettivo ===
        obj = quicksum(t[l, h] * self.w[l, h] for (l, h) in self.w)
        obj += alpha * quicksum(p[k] * self.z[k, j] for (k, j) in self.z)
        self.model.setObjective(obj, GRB.MINIMIZE)


        # === Vincoli ===
        # (1) Assegnazione: ogni arco del path della richiesta k deve essere servito da una sola linea
        for k in K:
            path = Pk[k]
            for (i, j) in zip(path[:-1], path[1:]):
                # Linee che servono questo arco
                valid_lines = [l for (ii, jj, l) in A if (ii, jj) == (i, j)]

                # Crea variabili x solo per le linee compatibili
                for l in valid_lines:
                    if (k, i, j, l) not in self.x:
                        self.x[k, i, j, l] = self.model.addVar(vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}")

                # Vincolo di assegnazione: somma delle x deve essere 1
                if valid_lines:
                    expr = quicksum(self.x[k, i, j, l] for l in valid_lines)
                    self.model.addConstr(expr == 1, name=f"assign_{k}_{i}_{j}")
                else:
                    print(f"⚠️ Nessuna linea collega ({i},{j}) per la richiesta {k} → vincolo saltato")


        
        # (2) Continuità su S
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in S:
                    self.model.addConstr(
                        self.x[k, i, j, l] == self.x[k, j, m, l],
                        name=f"contS_{k}_{l}_{i}_{j}_{m}"
                    )


        # (3) Continuità su J
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in J:
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] <= self.z[k, j],
                        name=f"contJ_plus_{k}_{l}_{i}_{j}_{m}"
                    )
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] >= -self.z[k, j],
                        name=f"contJ_minus_{k}_{l}_{i}_{j}_{m}"
                    )

                    
        
        # (4) Capacità per segmento h della linea l — DIREZIONALE
        for l, segs in Nl.items():
            for h, seg in enumerate(segs):
                arcs_h = [(seg[i], seg[i+1]) for i in range(len(seg) - 1)]
                self.model.addConstr(
                    quicksum(
                        p[k] * self.x[k, i, j, l]
                        for k in K
                        for (i, j) in arcs_h
                        if (k, i, j, l) in self.x        # evita key error
                    ) <= Q * self.w[l, h],
                    name=f"capacity_{l}_{h}"
                )

    
        # (5) Conservazione moduli ai nodi speciali (T e J)
        for j in (set(J) | set(T)):
            incoming = [self.w[ell, h] for (ell, h) in Delta_minus.get(j, [])]   # Se j non è presente, ritorna la lista vuota []
            outgoing = [self.w[ell, h] for (ell, h) in Delta_plus.get(j, [])]    # Se j non è presente, ritorna la lista vuota []
            self.model.addConstr(quicksum(incoming) == quicksum(outgoing),
                                 name=f"w_flow_{j}")


        

    # === RISOLUIZONE MODELLO ===
    def solve(self):
        self.model.optimize()
        print(f"Optimization status: {self.model.Status}")
        if self.model.Status == GRB.INFEASIBLE:
            print("⚠️ Modello infeasible, calcolo IIS...")
            # Gurobi cerca di individuare quali vincoli (o bounds) creano l’infeasibilità.
            # model.ilp.iis file che contiene solo quei vincoli
            self.model.computeIIS()
            self.model.write("results/cross/model.ilp")     # modello completo
            self.model.write("results/cross/model.iis.ilp")  # vincoli che creano conflitto e rendono il modello unfeasable




    # === ESTRAZIONE SOLUZIONE ===
    def get_solution(self):
        x_sol, w_sol, z_sol = {}, {}, {}

        if self.model.Status != GRB.OPTIMAL:   # Se non c’è soluzione ottima, ritorna vuoto
            return x_sol, w_sol, z_sol

        for v in self.model.getVars():
            if v.VarName.startswith("x") and v.X > 1e-6:
                _, k, i, j, ell = v.VarName.split("_")
                k, i, j = int(k), int(i), int(j)
                x_sol[(k, i, j, ell)] = 1
            elif v.VarName.startswith("w") and v.X > 1e-6:
                _, ell, h = v.VarName.split("_")
                h = int(h)
                w_sol[(ell, h)] = int(round(v.X))
            elif v.VarName.startswith("z") and v.X > 1e-6:
                _, k, j = v.VarName.split("_")
                k, j = int(k), int(j)
                z_sol[(k, j)] = 1
        return x_sol, w_sol, z_sol
    




class MBA_ILP_FLEX:
    """
    Modello FULL (con ribilanciamento moduli)
    - Variabili: x, w, z, v
    - Considera il tempo di rebalancing tr[(i,j)]
    """

    def __init__(self, data):
        self.data = data
        self.model = Model("MBA_ILP_FLEX")
        self.x = {}
        self.w = {}
        self.z = {}
        self.v = {}

    def build(self):
        d = self.data
        K, p, Pk, Blk = d["K"], d["p"], d["Pk"], d["Blk"]
        L, A, S, J, T, Nl = d["L"], d["A"], d["S"], d["J"], d["T"], d["Nl"]
        Delta_plus, Delta_minus = d["Delta_plus"], d["Delta_minus"]
        t, tr, Q = d["t"], d["tr"], d["Q"]
        R = d["R"]
        alpha = d["alpha"]

        # === VARIABILI ===
        for k in K:
            for (i, j, l) in A:
                self.x[k, i, j, l] = self.model.addVar(vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}")

        for l, segs in Nl.items():
            for h in range(len(segs)):
                self.w[l, h] = self.model.addVar(vtype=GRB.INTEGER, lb=0, name=f"w_{l}_{h}")

        for k in K:
            for j in J:
                self.z[k, j] = self.model.addVar(vtype=GRB.BINARY, name=f"z_{k}_{j}")

        for (i, j) in R:
            self.v[i, j] = self.model.addVar(vtype=GRB.INTEGER, lb=0, name=f"v_{i}_{j}")

        self.model.update()

        # === OBIETTIVO ===
        obj = quicksum(t[l, h] * self.w[l, h] for (l, h) in self.w)
        obj += quicksum(tr[i, j] * self.v[i, j] for (i, j) in self.v)
        obj += alpha * quicksum(p[k] * self.z[k, j] for (k, j) in self.z)
        self.model.setObjective(obj, GRB.MINIMIZE)

        # === VINCOLI ===
        # (1) assegnazione x
        for k in K:
            path = Pk[k]
            for (i, j) in zip(path[:-1], path[1:]):
                valid_lines = [l for (ii, jj, l) in A if (ii, jj) == (i, j)]
                if valid_lines:
                    self.model.addConstr(quicksum(self.x[k, i, j, l] for l in valid_lines) == 1,
                                         name=f"assign_{k}_{i}_{j}")

        # (2) continuità su S
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in S:
                    self.model.addConstr(self.x[k, i, j, l] == self.x[k, j, m, l],
                                         name=f"contS_{k}_{l}_{i}_{j}_{m}")

        # (3) Continuità su J
        for (l, k), triples in Blk.items():
            for (i, j, m) in triples:
                if j in J:
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] <= self.z[k, j],
                        name=f"contJ_plus_{k}_{l}_{i}_{j}_{m}"
                    )
                    self.model.addConstr(
                        self.x[k, i, j, l] - self.x[k, j, m, l] >= -self.z[k, j],
                        name=f"contJ_minus_{k}_{l}_{i}_{j}_{m}"
                    )
                    
        # (4) capacità
        for l, segs in Nl.items():
            for h, seg in enumerate(segs):
                arcs_h = [(seg[i], seg[i + 1]) for i in range(len(seg) - 1)]
                self.model.addConstr(
                    quicksum(p[k] * self.x[k, i, j, l]
                             for k in K for (i, j) in arcs_h
                             if (k, i, j, l) in self.x) <= Q * self.w[l, h],
                    name=f"capacity_{l}_{h}")

        # (5) conservazione moduli (T e J)
        for j in (set(J) | set(T)):
            incoming = [self.w[ell, h] for (ell, h) in Delta_minus.get(j, [])]
            outgoing = [self.w[ell, h] for (ell, h) in Delta_plus.get(j, [])]
            v_in  = [self.v[i, j] for (i, j2) in self.v if j2 == j]
            v_out = [self.v[j, h] for (j2, h) in self.v if j2 == j]
            self.model.addConstr(quicksum(incoming + v_in) == quicksum(outgoing + v_out),
                                 name=f"flow_balance_{j}")

    # === RISOLUZIONE E ESTRAZIONE ===
    def solve(self):
        self.model.optimize()
        print(f"Optimization status: {self.model.Status}")

    def get_solution(self):
        x_sol, w_sol, z_sol, v_sol = {}, {}, {}, {}
        if self.model.Status != GRB.OPTIMAL:
            return x_sol, w_sol, z_sol, v_sol

        for v in self.model.getVars():
            if v.VarName.startswith("x") and v.X > 1e-6:
                _, k, i, j, l = v.VarName.split("_")
                x_sol[(int(k), int(i), int(j), l)] = 1
            elif v.VarName.startswith("w") and v.X > 1e-6:
                _, l, h = v.VarName.split("_")
                w_sol[(l, int(h))] = int(round(v.X))
            elif v.VarName.startswith("z") and v.X > 1e-6:
                _, k, j = v.VarName.split("_")
                z_sol[(int(k), int(j))] = 1
            elif v.VarName.startswith("v") and v.X > 1e-6:
                _, i, j = v.VarName.split("_")
                v_sol[(int(i), int(j))] = int(round(v.X))
        return x_sol, w_sol, z_sol, v_sol
