import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3

conn_bkp = sqlite3.connect('financas_casa_backup_20261020_pre_integracao.db')
cur_bkp = conn_bkp.cursor()

conn_prod = sqlite3.connect('financas_casa.db')
cur_prod = conn_prod.cursor()

print("=== 1. COMPARAÇÃO DE TABELAS (BACKUP VS PRODUÇÃO) ===")
cur_bkp.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables_bkp = set(r[0] for r in cur_bkp.fetchall())

cur_prod.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables_prod = set(r[0] for r in cur_prod.fetchall())

novas_tabelas = sorted(list(tables_prod - tables_bkp))
print(f"Tabelas no backup ({len(tables_bkp)}):", sorted(list(tables_bkp)))
print(f"Tabelas em produção ({len(tables_prod)}):", sorted(list(tables_prod)))
print(f"Tabelas EFETIVAMENTE CRIADAS ({len(novas_tabelas)}):", novas_tabelas)

print("\n=== 2. COMPARAÇÃO DE COLUNAS EM 'TRANSACOES' ===")
cur_bkp.execute("PRAGMA table_info(transacoes)")
cols_bkp = [r[1] for r in cur_bkp.fetchall()]

cur_prod.execute("PRAGMA table_info(transacoes)")
cols_prod = [r[1] for r in cur_prod.fetchall()]

novas_colunas = [c for c in cols_prod if c not in cols_bkp]
print(f"Colunas no backup ({len(cols_bkp)}):", cols_bkp)
print(f"Colunas em produção ({len(cols_prod)}):", cols_prod)
print(f"Colunas EFETIVAMENTE ADICIONADAS ({len(novas_colunas)}):", novas_colunas)

print("\n=== 3. CONTAGEM E INTEGRIDADE DE REGISTROS ===")
cur_prod.execute("SELECT COUNT(*) FROM transacoes")
cnt_t = cur_prod.fetchone()[0]
cur_prod.execute("SELECT COUNT(*) FROM pagamentos_despesas")
cnt_p = cur_prod.fetchone()[0]
cur_prod.execute("SELECT COUNT(*) FROM turnos")
cnt_turno = cur_prod.fetchone()[0]
print(f"Transações: {cnt_t} (esperado 32)")
print(f"Pagamentos auditados: {cnt_p} (esperado 14)")
print(f"Turnos: {cnt_turno} (esperado 1)")

print("\n=== 4. VÍNCULO DOS 14 PAGAMENTOS COM CONTAS E TRANSAÇÕES ===")
cur_prod.execute("""
    SELECT p.id, p.transacao_id, t.descricao, p.conta_id, c.nome, p.valor_pago, p.data_pagamento
    FROM pagamentos_despesas p
    LEFT JOIN transacoes t ON p.transacao_id = t.id
    LEFT JOIN contas_config c ON p.conta_id = c.id
    ORDER BY p.id ASC
""")
pags = cur_prod.fetchall()
desvinculados_t = [p for p in pags if p[2] is None]
desvinculados_c = [p for p in pags if p[4] is None]
print(f"Total de pagamentos auditados: {len(pags)}")
print(f"Pagamentos sem transação vinculada: {len(desvinculados_t)}")
print(f"Pagamentos sem conta vinculada: {len(desvinculados_c)}")
for p in pags:
    print(f"  • Pagamento #{p[0]}: R$ {p[5]:.2f} em {p[6]} -> Conta: '{p[4]}' (ID {p[3]}) -> Transação #{p[1]}: '{p[2]}'")

print("\n=== 5. ANÁLISE DE IDEMPOTÊNCIA DA MIGRAÇÃO ===")
with open('scratch/migration_production.py', 'r', encoding='utf-8') as f:
    mig_code = f.read()

ddl_if_not_exists = "CREATE TABLE IF NOT EXISTS" in mig_code
print(f"Usa CREATE TABLE IF NOT EXISTS: {ddl_if_not_exists}")
print(f"Verifica colunas existentes antes de ALTER TABLE: {'PRAGMA table_info' in mig_code}")
print(f"Usa INSERT OR IGNORE nos grupos/subcategorias/contas: {'INSERT OR IGNORE' in mig_code}")

conn_bkp.close()
conn_prod.close()
