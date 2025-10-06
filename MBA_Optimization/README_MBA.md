### 3 settings:
- (1) 2 Bus lines forming a cross
- (2) Bus lines on a grid
- (3) Bus lines on a city graph (not real lines, but generated randomply to test a more realistic setting)




### Optimization:
- (A) BASE MODEL: no rebalancing
- (B) FULL MODEL: with both rebalancing an line changes




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
|   |      └── bus_line_creation_city.py        # (3) creazione corse su grafo di una città
│   └──demands/
|       └── demand_creation.py  # creazione della domanda (prendendo le bus_lines e gli stop in input)
|                               # le linee degli autobus sono un grafo e si cerca lo shortest path
|
├── models/  
│   └── models_mba.py          # definizione modello ILP   
│  
├── utils/  
│   │── f_for_data.py      # caricamento dati  (lines,  grid,  city)
│   └── f_for_results.py   # salvataggio e plot delle soluzioni                      
|
├── results/                # output dei risultati dell’ottimizzazione  
│   │── cross           
|   │── grid                
|   └── city
|
│── main_lines.py                # script principale per lines
│── main_grid.py                 # script principale per grid
└── main_graph.py                # script principale per city      







### Additional Comments:
- 2 graphs: 1 for bus lines, 1 for rebalancing archs
- Graphs are saved as MultiDiGraphs() => multigraphs, directional and each arch has a unique key = "bus line" 
- The input info is saved usually as csv, the outputs instead as json


