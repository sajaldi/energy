
import pandas as pd
import json

file_path = "Sig_Solicitudes_Seguimiento.xlsx"
try:
    df = pd.read_excel(file_path)
    info = {
        "columns": df.columns.tolist(),
        "head": df.head(5).to_dict(orient='records'),
        "dtypes": df.dtypes.astype(str).to_dict()
    }
    print(json.dumps(info, indent=2))
except Exception as e:
    print(f"Error reading file: {e}")
