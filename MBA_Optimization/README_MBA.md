### Code structure:



MBA_Optimization/  
│  
├── data/  
|   └── data_creation_test.py       # (1) test semplice con solo 2 linee (creazione di input_data_test.xlsx)
|   └── data_creation_city-name.py  # (2) estrazione corse bus/tram con OSM (creazione di input_data_city-name.xlsx)
│   └── input_data_city-name.xlsx   # dati in input (of a selected city (ex. Turin)) 
│   └── input_data_test.xlsx        # dati in input semplici (per test)
│  
├── models/  
│   └── mba_ilp.py          # definizione modello ILP   
│  
├── utils/  
│   └── data_loader_test.py           # caricamento dati (test data) 
│   └── data_loader_city.py      # caricamento dati (city data) 
│  
├── results/  
│   └── solutions.csv            # output dei risultati dell’ottimizzazione  
│  
└── main_city.py                 # script principale        

