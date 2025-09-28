### Code structure:


MBA_Optimization/  
│  
├── data/
|   ├──bus_lines/  
|   |   └── bus_line_creation_lines.py      # (1) creazione corse con linee
|   |   └── bus_line_creation_grid.py       # (2) creazione corse con grid
|   |   └── bus_line_creation_graph.py      # (3) creazione corse su grafo di una città
|   |   # lines: bus, n°linea, nome, geometry:percorso linea (coordinate metriche)
|   |   # stops: id, nome, tipo, nodo, coordinate metriche
│   └──demand/
|       └── demand_creation.py  # creazione della domanda (prendendo le bus_lines e gli stop in input)
|
├── models/  
│   └── mba_ilp.py          # definizione modello ILP   
│  
├── utils/  
│   └── data_loader.py      # caricamento dati 
│                           # lines,  grid,  city  
|
├── results/  
│   └── solutions.csv            # output dei risultati dell’ottimizzazione  
│  
│── main_lines.py                # script principale per lines
│── main_grid.py                 # script principale per grid
│── main_graph.py                 # script principale per city      

