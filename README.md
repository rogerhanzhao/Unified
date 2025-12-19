# CALB ESS Sizing Tool

This repository contains a Streamlit application for sizing energy storage systems across Stage 1–4 and lightweight unit tests for the Stage 4 interface helpers.

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Run the app

Launch the Streamlit application from the repository root:

```bash
streamlit run DC_Block_Sizing.py
```

Ensure the Excel data files (for example, `ess_sizing_data_dictionary_v13_dc_autofit.xlsx`) are present in the same directory before running.

## Run tests

Execute the test suite with:

```bash
pytest -q
```
