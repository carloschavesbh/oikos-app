import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=" * 60)
print("INVENTÁRIO E AUDITORIA DE LIMITES, PARÂMETROS E ORIGENS")
print("=" * 60)

# 1. Cartões de Crédito
print("\n--- 1. TABELA CARTOES ---")
cur.execute("SELECT * FROM cartoes")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 2. Limites de Categoria (limites_categoria)
print("\n--- 2. TABELA LIMITES_CATEGORIA ---")
cur.execute("SELECT * FROM limites_categoria")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 3. Contas Paga Leve (pagaleve_contas)
print("\n--- 3. TABELA PAGALEVE_CONTAS ---")
cur.execute("SELECT * FROM pagaleve_contas")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 4. Ajustes e Marcos de Saldo (ajustes_saldo)
print("\n--- 4. TABELA AJUSTES_SALDO ---")
cur.execute("SELECT a.*, c.nome as conta_nome FROM ajustes_saldo a LEFT JOIN contas_config c ON a.conta_id = c.id")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 5. Planejamento Metas e Previsões (planejamento_metas e planejamento_previsao_variaveis)
print("\n--- 5. TABELA PLANEJAMENTO_METAS ---")
cur.execute("SELECT * FROM planejamento_metas")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

print("\n--- 6. TABELA PLANEJAMENTO_PREVISAO_VARIAVEIS ---")
cur.execute("SELECT * FROM planejamento_previsao_variaveis")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 7. Config Dashboard (config_dashboard)
print("\n--- 7. TABELA CONFIG_DASHBOARD ---")
cur.execute("SELECT * FROM config_dashboard")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

# 8. Transações Especiais / Pendentes de Confirmação (Acordo BV, Cartão, etc.)
print("\n--- 8. TRANSAÇÕES ESPECIAIS / CONCILIAÇÃO / STATUS FATURA ---")
cur.execute("""
    SELECT id, data, descricao, valor, categoria, conta, pago, status_conciliacao_fatura, status_rateio, grupo_parcelamento
    FROM transacoes
    WHERE descricao LIKE '%BV%' OR descricao LIKE '%fatura%' OR descricao LIKE '%Saldo%' OR status_conciliacao_fatura != 'normal' OR status_rateio != 'normal'
    ORDER BY id ASC
""")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

conn.close()
