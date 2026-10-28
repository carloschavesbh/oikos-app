import json
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/all_5_xls_records.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for fname in ['movimentacoes_carlos_20261001_20261031.xls', 'movimentacoes_carlos_20261101_20261130.xls']:
    records = data[fname]
    df = pd.DataFrame(records)
    print(f"\n{'='*70}")
    print(f"ARQUIVO: {fname} ({len(df)} registros)")
    print(f"{'='*70}")
    print("Situação:", df['Situação'].value_counts(dropna=False).to_dict())
    rec = df[df['Valor'] > 0]['Valor'].sum()
    desp = df[df['Valor'] < 0]['Valor'].sum()
    print(f"Total Receitas: R$ {rec:.2f} ({len(df[df['Valor'] > 0])} lançamentos)")
    print(f"Total Despesas: R$ {desp:.2f} ({len(df[df['Valor'] < 0])} lançamentos)")
    print(f"Saldo Mensal: R$ {rec + desp:.2f}")
    
    print("\nLançamentos detalhados:")
    for idx, r in df.iterrows():
        dt = str(r['Data'])[:10]
        desc = str(r['Descrição'])
        cat = str(r['Categoria'])
        val = r['Valor']
        sit = str(r['Situação'])
        info = str(r['Informações adicionais']) if pd.notna(r['Informações adicionais']) else ""
        print(f"  {idx+1:2d}. {dt} | {val:>10.2f} | {sit:<10} | {desc[:35]:<35} | {cat[:25]:<25} | {info}")
