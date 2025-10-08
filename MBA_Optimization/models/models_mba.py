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
        self.x = {}
        self.w = {}
        self.z = {}



    # === COSTRUZIONE MODELLO ===
    def build(self):
        d = self.data
        K, p, Pk, Pkl, Blk = d["K"], d["p"], d["Pk"], d["Pkl"], d["Blk"]
        L, A, S, J, T, Nl = d["L"], d["A"], d["S"], d["J"], d["T"], d["Nl"]
        Delta_plus, Delta_minus = d["Delta_plus"], d["Delta_minus"]
        t, Q = d["t"], d["Q"]
    

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
        obj += quicksum(p[k] * self.z[k, j] for (k, j) in self.z)
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

        # (3) Continuità su J con z
        """ VERSIONE PAPER:
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
        """ PICCOLA MODIFICA: """
        #  Caso                           | Significato fisico                                  | Effetto sul modello
        # ---------------------------------------------------------------------------------------------------------
        #  y_in_l = 1 , y_out_l = 1       → la richiesta arriva e riparte sulla stessa linea     → z_kj può restare 0
        #  y_in_l = 1 , y_out_l = 0       → la richiesta scende da quella linea in j             → forza z_kj = 1
        #  y_in_l = 0 , y_out_l = 1       → la richiesta sale su quella linea in j               → forza z_kj = 1
        #  y_in_l = 0 , y_out_l = 0       → la richiesta non passa su quella linea               → nessun effetto
        # Fix cross-line: attiva z_kj anche per cambi linea inter-linea
        for k in K:
            pairs_k = set(zip(Pk[k][:-1], Pk[k][1:]))   # Crea l’elenco degli archi effettivamente percorsi dalla richiesta k
            for j in J:
                for l in L:
                    #Costruisce la somma degli archi (i,j) della linea l che entrano/escono nel nodo j nel percorso di k.
                    y_in_l  = quicksum(self.x[k, i, jj, l]
                                    for (i, jj, ll) in A
                                    if jj==j and ll==l and (i, jj) in pairs_k and (k,i,jj,l) in self.x)
                    y_out_l = quicksum(self.x[k, jj, m, l]
                                    for (jj, m, ll) in A
                                    if jj==j and ll==l and (jj, m) in pairs_k and (k,jj,m,l) in self.x)
                    self.model.addConstr(y_in_l - y_out_l <= self.z[k, j])
                    self.model.addConstr(y_out_l - y_in_l <= self.z[k, j])

        
        
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
        # (4) Capacità per segmento h della linea ℓ
        for l, segs in Nl.items():
            for h, seg in enumerate(segs):
                arcs_h = [(seg[i], seg[i+1]) for i in range(len(seg) - 1)]
                self.model.addConstr(
                    quicksum(
                        p[k] * self.x[k, i, j, l]
                        for k in K
                        for (i, j) in arcs_h
                    ) <= Q * self.w[l, h],
                    name=f"capacity_{l}_{h}"
                )
        """

    
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
    





