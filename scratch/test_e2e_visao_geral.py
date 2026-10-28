import sqlite3
import pandas as pd
from datetime import date
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))

import app
import saldo_service

print("=== TESTE E2E DA VISÃO GERAL OPERACIONAL ===")

conn = app.conectar()
df_tx = pd.read_sql_query("SELECT * FROM transacoes", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)
conn.close()

print(f"Transações carregadas: {len(df_tx)}")
print(f"Turnos carregados: {len(df_turnos)}")

# Verificar integridade do banco de produção
conn_check = sqlite3.connect('financas_casa.db')
c = conn_check.cursor()
c.execute("PRAGMA integrity_check")
res = c.fetchone()[0]
print(f"Integridade do banco: {res}")
assert res == 'ok'

# Verificar saldos
saldos = saldo_service.calcular_saldo_consolidado(conn_check)
print(f"Saldo consolidado: R$ {saldos['saldo_consolidado']}")
assert float(saldos['saldo_consolidado']) == 86.33, f"Esperado 86.33, obteve {saldos['saldo_consolidado']}"

conn_check.close()
print("Teste E2E finalizado com sucesso!")
