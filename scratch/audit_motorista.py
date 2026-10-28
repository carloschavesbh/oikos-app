import sqlite3
import pandas as pd
from decimal import Decimal
import saldo_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 1. TABELA AJUSTES_SALDO ===")
cur.execute("SELECT * FROM ajustes_saldo")
for r in cur.fetchall():
    print(dict(r))

print("\n=== 2. TABELA TURNOS ===")
cur.execute("SELECT * FROM turnos")
for r in cur.fetchall():
    print(dict(r))

print("\n=== 3. TRANSACOES RECENTES (>= 2026-10-18 OU COM TURNO_ID OU MOTORISTA/99/COMBUSTIVEL) ===")
cur.execute("""
    SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id
    FROM transacoes
    WHERE data >= '2026-10-18' 
       OR turno_id IS NOT NULL 
       OR descricao LIKE '%turno%' 
       OR descricao LIKE '%99%' 
       OR descricao LIKE '%combust%'
       OR categoria LIKE '%combust%'
       OR categoria LIKE '%corrida%'
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=== 4. SALDOS POR CONTA CONFORME SALDO_SERVICE ===")
cur.execute("SELECT id, nome FROM contas_config")
contas = cur.fetchall()
for c in contas:
    cid, cnome = c["id"], c["nome"]
    saldo_info = saldo_service.calcular_saldo_conta(conn, cid)
    print(f"Conta '{cnome}' (id={cid}):")
    for k, v in saldo_info.items():
        print(f"  {k}: {v}")

print("\n=== 5. DESPESAS_VEICULO ===")
cur.execute("SELECT * FROM despesas_veiculo")
for r in cur.fetchall():
    print(dict(r))

conn.close()
