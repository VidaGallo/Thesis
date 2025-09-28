### Code structure:


MBA_Optimization/  
│  
├── data/  
|   └── buse_line_creation_lines.py      # (1) creazione corse con linee
|   └── buse_line_creation_grid.py       # (2) creazione corse con grid
|   └── buse_line_creation_graph.py      # (3) creazione corse su grafo di una città
|       # lines: bus, n°linea, nome, geometry:percorso linea (coordinate metriche)
|       # stops: id, nome, tipo, nodo, coordinate metriche
│  
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

