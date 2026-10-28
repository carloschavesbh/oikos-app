import sqlite3
import json
import re
from datetime import datetime

conn = sqlite3.connect('scratch/financas_casa_teste_migracao.db')
cursor = conn.cursor()

# Adicionar coluna de rastreamento de origem se não existir
try:
    cursor.execute("ALTER TABLE transacoes ADD COLUMN organizze_id TEXT")
except:
    pass

try:
    cursor.execute("ALTER TABLE transacoes ADD COLUMN natureza_operacao TEXT")
except:
    pass

conn.commit()

# Carregar transações do Organizze
with open('scratch/organizze_lancamentos_extracted.json', 'r', encoding='utf-8') as f:
    org_txs = json.load(f)

# Carregar transações do DB
cursor.execute("SELECT id, data, descricao, valor, tipo, conta_id FROM transacoes")
db_txs = cursor.fetchall()

print(f"Total no banco de teste antes: {len(db_txs)}")

matched_count = 0
unmatched_org = []
ambiguous = []

for ot in org_txs:
    lines = ot['lines']
    tx_id = ot['id']
    val_str = ot['valor']
    try:
        val_float = abs(float(val_str.replace('.', '').replace(',', '.')))
    except:
        val_float = 0.0
        
    tipo = 'receita' if not val_str.startswith('-') else 'despesa'
    
    # Extrair data
    dt = None
    for l in lines:
        if re.match(r'^\d{2}/\d{2}/\d{2}$', l):
            # converter 01/10/26 para 2026-10-01
            parts = l.split('/')
            dt = f"20{parts[2]}-{parts[1]}-{parts[0]}"
            break
            
    skip_words = {'Mercado Pago', 'Conta vencida', 'Saldo no dia', 'Saldo no dia anterior', 'Receita realizada', 'Receita prevista', 'Despesa realizada', 'Despesa prevista', 'Hoje'}
    cand_desc = [l for l in lines if l not in skip_words and not l.startswith('-') and not l.startswith('+') and '/' not in l]
    desc = cand_desc[0] if cand_desc else lines[0]
    
    # Buscar no DB por valor idêntico e mesmo tipo
    candidates = [d for d in db_txs if abs(d[3] - val_float) < 0.01 and d[4] == tipo]
    
    if len(candidates) == 1:
        # Match direto!
        matched_db_id = candidates[0][0]
        cursor.execute("UPDATE transacoes SET organizze_id = ? WHERE id = ?", (f"org_{tx_id}", matched_db_id))
        matched_count += 1
    elif len(candidates) > 1:
        # Múltiplos candidatos: checar data ou descrição
        best_match = None
        for c in candidates:
            # comparar descrição
            if any(w.lower() in c[2].lower() for w in desc.split() if len(w) > 3):
                best_match = c
                break
        if best_match:
            cursor.execute("UPDATE transacoes SET organizze_id = ? WHERE id = ?", (f"org_{tx_id}", best_match[0]))
            matched_count += 1
        else:
            ambiguous.append((tx_id, desc, val_float, candidates))
    else:
        unmatched_org.append((tx_id, dt, desc, val_float, tipo))

conn.commit()
print(f"Vinculados com sucesso sem duplicação: {matched_count}")
print(f"Casos ambíguos para revisão manual: {len(ambiguous)}")
for a in ambiguous:
    print(f"  Ambíguo: Org ID {a[0]} | {a[1]} | R$ {a[2]} | Candidatos DB: {[c[0] for c in a[3]]}")

print(f"Transações Organizze não encontradas no DB: {len(unmatched_org)}")
for u in unmatched_org:
    print(f"  Não encontrada: Org ID {u[0]} | Data: {u[1]} | {u[2]} | R$ {u[3]} ({u[4]})")

conn.close()
