"""
Validação prévia de migração e preservação estrita de dados em banco de teste isolado.
"""
import sqlite3
import shutil
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.abspath("."))
import saldo_service
import planejamento_service

test_db = 'financas_teste_visual.db'
if os.path.exists(test_db):
    os.remove(test_db)
shutil.copy2('financas_casa.db', test_db)

conn = sqlite3.connect(test_db)
conn.row_factory = sqlite3.Row

# Saldo e contagens antes
s_antes = saldo_service.calcular_saldo_consolidado(conn)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM transacoes')
t_antes = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM pagamentos_despesas')
p_antes = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM turnos')
u_antes = cur.fetchone()[0]
cur.execute("SELECT valor FROM transacoes WHERE descricao LIKE '%Acordo BV%'")
bv_val_antes = cur.fetchone()[0]

# Executa migracao
planejamento_service.inicializar_esquema_planejamento(conn)
cur.execute("UPDATE transacoes SET status_conciliacao_fatura = 'pendente_confirmacao' WHERE (descricao LIKE '%Acordo BV%' OR categoria LIKE '%Acordo BV%') AND (status_conciliacao_fatura IS NULL OR status_conciliacao_fatura = 'normal')")
conn.commit()

# Saldo e contagens depois
s_depois = saldo_service.calcular_saldo_consolidado(conn)
cur.execute('SELECT COUNT(*) FROM transacoes')
t_depois = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM pagamentos_despesas')
p_depois = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM turnos')
u_depois = cur.fetchone()[0]
cur.execute("SELECT valor, status_conciliacao_fatura FROM transacoes WHERE descricao LIKE '%Acordo BV%'")
bv_row_depois = cur.fetchone()

print(f"Transacoes: {t_antes} -> {t_depois}")
print(f"Pagamentos: {p_antes} -> {p_depois}")
print(f"Turnos: {u_antes} -> {u_depois}")
print(f"Saldo: R$ {s_antes['saldo_consolidado']} -> R$ {s_depois['saldo_consolidado']}")
print(f"Acordo BV valor: {bv_val_antes} -> {bv_row_depois[0]} (Status: {bv_row_depois[1]})")

assert t_antes == t_depois == 32
assert p_antes == p_depois == 14
assert u_antes == u_depois == 1
assert s_antes['saldo_consolidado'] == s_depois['saldo_consolidado'] == Decimal('86.33')
assert bv_val_antes == bv_row_depois[0] == 1428.82
assert bv_row_depois[1] == 'pendente_confirmacao'

conn.close()
if os.path.exists(test_db):
    os.remove(test_db)
print("[VALIDACAO EM BANCO DE TESTE BEM-SUCEDIDA COM 100% DE EXATIDAO!]")
