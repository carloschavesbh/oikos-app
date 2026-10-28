import os
import glob
from pathlib import Path
import pandas as pd
import json

export_dir = Path("Organizze") / "Exportações"
files = sorted(list(export_dir.glob("*.xls")))

print(f"Encontrados {len(files)} arquivos .xls:")

for f in files:
    print(f"\n==========================================")
    print(f"ARQUIVO: {f.name}")
    print(f"==========================================")
    try:
        # ler com xlrd
        df = pd.read_excel(f, engine='xlrd')
        print(f"Dimensões: {df.shape[0]} linhas x {df.shape[1]} colunas")
        print(f"Colunas: {list(df.columns)}")
        print("\nPrimeiras 5 linhas:")
        print(df.head(5).to_string())
    except Exception as e:
        print(f"Erro ao ler com xlrd: {e}")
