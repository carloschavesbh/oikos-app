import json
import sqlite3
import pandas as pd
from datetime import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/all_5_xls_records.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

conn = sqlite3.connect('financas_casa.db')
df_db = pd.read_sql_query("SELECT id, data, descricao, valor, tipo, pago, conta_id, grupo_id, subcategoria_id FROM transacoes", conn)
conn.close()

print(f"Total registros no banco atual: {len(df_db)}")

all_classified = []

# Marco de conciliação
MARCO_CONCILIACAO = "2026-10-19"

for fname, records in data.items():
    print(f"\n=======================================================")
    print(f"PROCESSANDO: {fname} ({len(records)} registros)")
    print(f"=======================================================")
    
    for r in records:
        raw_date = str(r['Data'])[:10] # ex: '01.10.2026' ou '2026-10-01'
        if '.' in raw_date:
            parts = raw_date.split('.')
            iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            iso_date = raw_date
            
        desc = str(r['Descrição']).strip()
        cat = str(r['Categoria']).strip()
        val = float(r['Valor'])
        sit = str(r['Situação']).strip() # 'Pago' ou 'Não pago'
        tipo = 'receita' if val > 0 else 'despesa'
        val_abs = abs(val)
        
        # Classificação inicial
        classificacao = None
        motivo = ""
        matched_id = None
        
        # 1. Checar se já existe no banco
        # Critério: mesmo valor absoluto e tipo
        cands = df_db[(abs(df_db['valor'] - val_abs) < 0.01) & (df_db['tipo'] == tipo)]
        
        # Refinar por data e descrição
        best_cand = None
        for _, c in cands.iterrows():
            c_desc = str(c['descricao']).lower()
            d_desc = desc.lower()
            # Checar overlap de palavras
            words_match = any(w in c_desc for w in d_desc.split() if len(w) > 3)
            # Checar data próxima (+/- 5 dias)
            try:
                d1 = datetime.strptime(iso_date, "%Y-%m-%d")
                d2 = datetime.strptime(str(c['data'])[:10], "%Y-%m-%d")
                days_diff = abs((d1 - d2).days)
            except:
                days_diff = 999
                
            if words_match and days_diff <= 7:
                best_cand = c
                break
                
        if best_cand is not None:
            classificacao = "Já existente no aplicativo"
            motivo = f"Coincide com transação DB ID {best_cand['id']} ({best_cand['descricao']} em {best_cand['data']})"
            matched_id = int(best_cand['id'])
        else:
            # Não está no DB
            if iso_date <= MARCO_CONCILIACAO:
                if sit == 'Pago':
                    classificacao = "Histórico anterior ao marco de conciliação"
                    motivo = f"Ocorrido e pago em {iso_date} (antes de 19/10/2026). Não pode afetar saldo atual."
                else:
                    classificacao = "Incompleto, exigindo confirmação"
                    motivo = f"Vencimento anterior ao marco ({iso_date}), mas consta 'Não pago' no Organizze (atrasado pendente)."
            else:
                # Posterior a 19/10/2026
                # Checar se é fatura de cartão
                if "fatura" in desc.lower():
                    classificacao = "Novo e importável (Fatura Cartão Inter)"
                    motivo = f"Projeção de fatura futura do Cartão Inter Aparecida (Total consolidado: R$ {val_abs:.2f})"
                elif any(p in desc.lower() for p in ['crediserv', 'acordo bv', 'paga leve', 'ipva']):
                    classificacao = "Novo e importável (Parcela / Dívida futura)"
                    motivo = f"Parcelamento futuro identificado: {desc} (R$ {val_abs:.2f})"
                elif val > 0:
                    classificacao = "Novo e importável (Receita futura programada)"
                    motivo = f"Receita futura: {desc} (R$ {val_abs:.2f})"
                else:
                    classificacao = "Novo e importável (Despesa fixa / Recorrência futura)"
                    motivo = f"Despesa futura: {desc} (R$ {val_abs:.2f})"
                    
        all_classified.append({
            'arquivo': fname,
            'data': iso_date,
            'descricao': desc,
            'categoria': cat,
            'valor': val,
            'situacao': sit,
            'classificacao': classificacao,
            'motivo': motivo,
            'matched_db_id': matched_id
        })

df_all = pd.DataFrame(all_classified)
print("\n=== RESUMO GERAL DAS CLASSIFICAÇÕES ===")
print(df_all['classificacao'].value_counts().to_string())

with open('scratch/classified_all_113.json', 'w', encoding='utf-8') as fp:
    json.dump(all_classified, fp, indent=2, ensure_ascii=False)
