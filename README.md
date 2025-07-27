# Singapore Preschool Demand Forecasting - Streamlit Application

This Streamlit application provides an interactive interface for forecasting preschool demand across Singapore subzones using fertility data, BTO housing completions, current demographics and existing preschool locations.

# Repository Contents
```
├── data
│   └── data_sources.txt                  # link to data sources
├── notebooks
│   └── ecda.ipynb                        # exploratory analysis
├── README.md
├── requirements.txt
├── src                                   # backend pipeline
│   ├── __init__.py
│   ├── forecast.py
│   ├── process_bto.py
│   ├── process_existing_residents.py
│   ├── process_fertility.py
│   ├── process_preschools.py
│   └── visualizations.py
├── streamlit_app.py                      # frontend GUI
└── tests
```

## Quick Start
1. Download the files in `data/data_sources.txt`, and place them as-is in the `data/` folder.
2. Install dependencies using `pip install -r requirements.txt`
3. Run `streamlit run streamlit_app.py`
4. The app will auto-detect sample data files
5. Click "Run Forecast" to generate predictions
6. Explore results tabs with the interactive year slider