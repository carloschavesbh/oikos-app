import sqlite3
import pandas as pd
import re
from datetime import date, datetime

conn = sqlite3.connect('financas_casa.db')
df = pd.read_sql_query('SELECT * FROM transacoes', conn)
conn.close()

df_pl = df[(df['grupo_parcelamento'].str.startswith('pagaleve', na=False)) | (df['descricao'].str.contains('Paga Leve', case=False, na=False))].copy()

grupos = {}
for _, row in df_pl.iterrows():
    grp = row['grupo_parcelamento']
    if not grp or pd.isna(grp):
        grp = re.sub(r' - Paga Leve.*', '', row['descricao'], flags=re.I).strip()
    if grp not in grupos:
        grupos[grp] = []
    grupos[grp].append(row)

compras = []
for g_id, itens in grupos.items():
    itens_sorted = sorted(itens, key=lambda x: (x['data'], x['id']))
    
    # Nome base
    desc_base = re.sub(r' - Paga Leve.*', '', itens_sorted[0]['descricao'], flags=re.I).strip()
    
    tot_val = sum(r['valor'] for r in itens_sorted)
    tot_pago = sum(r['valor'] for r in itens_sorted if r['pago'] == 1)
    tot_aberto = sum(r['valor'] for r in itens_sorted if r['pago'] != 1)
    
    # Determina quantas parcelas conhecidas e qual o total esperado (normalmente 4)
    # Procura número da parcela nos textos (ex: 3/4)
    max_num_parc = 4
    for it in itens_sorted:
        m = re.search(r'(\d+)/(\d+)', it['descricao'])
        if m:
            max_num_parc = max(max_num_parc, int(m.group(2)))
            
    is_quitada = (tot_aberto <= 0.001)
    
    # Próximo vencimento
    pendentes = [r for r in itens_sorted if r['pago'] != 1]
    prox_venc = min((r['data'] for r in pendentes), default=None)
    
    compras.append({
        'grupo_id': g_id,
        'nome': desc_base,
        'categoria': itens_sorted[0]['categoria'],
        'conta': itens_sorted[0]['conta'],
        'total_compra': tot_val,
        'total_pago': tot_pago,
        'total_aberto': tot_aberto,
        'status': 'Quitada' if is_quitada else 'Ativa',
        'itens': itens_sorted,
        'total_parcelas': max_num_parc,
        'prox_venc': prox_venc
    })

print(f"Total de compras agrupadas: {len(compras)}")
for c in compras:
    print(f"Compra: {c['nome']} | Status: {c['status']} | Aberto: R$ {c['total_aberto']:.2f} | Próx: {c['prox_venc']}")
    for it in c['itens']:
        st_txt = "Paga" if it['pago'] == 1 else "Pendente"
        print(f"   {it['descricao']} - {it['data']} - R$ {it['valor']:.2f} [{st_txt}]")
