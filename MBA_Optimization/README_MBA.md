### Code structure:


MBA_Optimization/  
│  
├── data/
|   ├──bus_lines/  
|   |   ├──cross/
|   |   |   └── bus_line_creation_cross.py      # (1) creazione corse con 2 linee incrociate
|   |   ├──grid/
|   |   |   └── bus_line_creation_grid.py       # (2) creazione corse con grid
|   |   └──city/
|   |      └── bus_line_creation_city.py      # (3) creazione corse su grafo di una città
│   └──demands/
|       └── demand_creation.py  # creazione della domanda (prendendo le bus_lines e gli stop in input)
|                               # le linee degli autobus sono un grafo e si cerca lo shortest path
|
├── models/  
│   └── model_mba_BASE.py          # definizione modello ILP   
│  
├── utils/  
│   │── data_loader.py      # caricamento dati  (lines,  grid,  city)
│   └── save_results.py                          
|
├── results/                # output dei risultati dell’ottimizzazione  
│  
│── main_lines.py                # script principale per lines
│── main_grid.py                 # script principale per grid
│── main_graph.py                 # script principale per city      

