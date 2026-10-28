import sys
import os
from pathlib import Path
import pandas as pd
import json

sys.stdout.reconfigure(encoding='utf-8')

export_dir = Path("Organizze") / "Exportações"
files = sorted(list(export_dir.glob("*.xls")))

all_data = {}

for f in files:
    df = pd.read_excel(f, engine='xlrd')
    month_key = f.name.replace('movimentacoes_carlos_', '').replace('.xls', '')
    records = df.to_dict(orient='records')
    all_data[f.name] = records
    
    print(f"\n{'='*70}")
    print(f"ARQUIVO: {f.name} ({len(df)} registros)")
    print(f"{'='*70}")
    print(f"Colunas: {list(df.columns)}")
    
    # Análise de Situação
    print("\n--- Situação ---")
    print(df['Situação'].value_counts(dropna=False).to_dict())
    
    # Análise de Valores
    rec = df[df['Valor'] > 0]['Valor'].sum()
    desp = df[df['Valor'] < 0]['Valor'].sum()
    print(f"Total Receitas: R$ {rec:.2f} ({len(df[df['Valor'] > 0])} lançamentos)")
    print(f"Total Despesas: R$ {desp:.2f} ({len(df[df['Valor'] < 0])} lançamentos)")
    print(f"Saldo Mensal: R$ {rec + desp:.2f}")
    
    # Listar todos os registros de forma tabular resumida
    print("\n--- Lançamentos ---")
    for idx, r in df.iterrows():
        dt = str(r['Data'])[:10]
        desc = str(r['Descrição'])
        cat = str(r['Categoria'])
        val = r['Valor']
        sit = str(r['Situação'])
        tags = str(r['Tags']) if pd.notna(r['Tags']) else ""
        info = str(r['Informações adicionais']) if pd.notna(r['Informações adicionais']) else ""
        print(f"  {idx+1:2d}. {dt} | {val:>10.2f} | {sit:<10} | {desc[:35]:<35} | {cat[:25]:<25} | {info}")

with open('scratch/all_5_xls_records.json', 'w', encoding='utf-8') as fp:
    json.dump(all_data, fp, indent=2, ensure_ascii=False, default=str)

print("\n\nDados completos salvos em scratch/all_5_xls_records.json")
