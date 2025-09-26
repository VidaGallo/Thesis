### Code structure:


MBA_Optimization/  
│  
├── data/  
|   └── data_creation_lines.py      # (1) test semplice con solo 2 linee (creazione di input_data_lines.xlsx)
|   └── data_creation_grid.py       # (2) test semplice con solo 2 linee (creazione di input_data_grid.xlsx)
|   └── data_creation_city-name.py  # (3) estrazione corse bus/tram con OSM (creazione di input_data_city-name.xlsx)
│   └── input_data_lines.xlsx       # (1) dati in input 2 linee
│   └── input_data_grid.xlsx        # (2) dati in input grid
│   └── input_data_city-name.xlsx   # (3) dati in input di una città (es. Torino)
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
│── main_city.py                 # script principale per city      

