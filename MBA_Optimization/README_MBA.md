### Code structure:



MBA_Optimization/  
│  
├── data/  
│   └── input_data_city-name.xlsx   # dati in input (of a selected city (ex. Turin)) 
│  
├── models/  
│   └── mba_ilp.py               # definizione modello ILP   
│  
├── utils/  
│   └── data_loader.py           # caricamento dati (da data) 
|   └── transit_data_city.py     # estrazione corse bus/tram con OSM (creazione di input_data_city-name.xlsx)
│  
├── results/  
│   └── solutions.csv            # output dei risultati dell’ottimizzazione  
│  
└── main_city.py                 # script principale        

