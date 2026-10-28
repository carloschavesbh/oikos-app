import sqlite3
import json
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
df_db = pd.read_sql_query("SELECT id, data, descricao, valor, tipo, pago, conta_id FROM transacoes", conn)
conn.close()

with open('scratch/organizze_lancamentos_extracted.json', 'r', encoding='utf-8') as f:
    org_txs = json.load(f)

print(f"Total Organizze Lancamentos: {len(org_txs)}")
print(f"Total DB Lancamentos: {len(df_db)}")

print("\n=== COMPARATIVO DIRETO ===")
for ot in org_txs:
    lines = ot['lines']
    dt = None
    val = ot['valor']
    
    for l in lines:
        if '/' in l and len(l) <= 10:
            dt = l
    skip_words = {'Mercado Pago', 'Conta vencida', 'Saldo no dia', 'Saldo no dia anterior', 'Receita realizada', 'Receita prevista', 'Despesa realizada', 'Despesa prevista', 'Hoje'}
    cand_desc = [l for l in lines if l not in skip_words and not l.startswith('-') and not l.startswith('+') and '/' not in l]
    desc = cand_desc[0] if cand_desc else lines[0]
    
    try:
        val_float = abs(float(val.replace('.', '').replace(',', '.')))
    except:
        val_float = 0.0
        
    matches = df_db[abs(df_db['valor'] - val_float) < 0.01]
    
    match_status = "[AUSENTE NO BANCO]"
    if len(matches) > 0:
        db_ids = matches['id'].tolist()
        match_status = f"[MATCH DB IDs: {db_ids} | {matches.iloc[0]['descricao']}]"
        
    print(f"Org ID: {ot['id']} | Data: {dt or 'sem data'} | Valor: {val:>9} | Desc: {desc[:35]:<35} -> {match_status}")

print("\n=== TRANSAÇÕES NO BANCO QUE NÃO FORAM VISTAS EM ORGANZZE LANÇAMENTOS ===")
# Checar o inverso
for _, r in df_db.iterrows():
    # buscar se o valor existe em org_txs
    found = False
    for ot in org_txs:
        try:
            val_float = abs(float(ot['valor'].replace('.', '').replace(',', '.')))
            if abs(r['valor'] - val_float) < 0.01:
                found = True
                break
        except:
            pass
    if not found:
        print(f"DB ID {r['id']} | Data: {r['data']} | Valor: R$ {r['valor']:.2f} | Desc: {r['descricao']} | Conta: {r['conta_id']}")
