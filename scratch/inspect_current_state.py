import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import pandas as pd
import saldo_service

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== INSPEÇÃO GERAL DO BANCO ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tabelas:", tables)

print("\n=== TURNOS ===")
cur.execute("PRAGMA table_info(turnos)")
print("Colunas turnos:", [r[1] for r in cur.fetchall()])
cur.execute("SELECT * FROM turnos")
for row in cur.fetchall():
    print(row)

print("\n=== COFRINHOS ===")
if "cofrinhos" in tables:
    cur.execute("PRAGMA table_info(cofrinhos)")
    print("Colunas cofrinhos:", [r[1] for r in cur.fetchall()])
    cur.execute("SELECT * FROM cofrinhos")
    for row in cur.fetchall():
        print(row)
else:
    print("Tabela cofrinhos não existe.")

print("\n=== CONTAS_CONFIG ===")
if "contas_config" in tables:
    cur.execute("PRAGMA table_info(contas_config)")
    print("Colunas contas_config:", [r[1] for r in cur.fetchall()])
    cur.execute("SELECT * FROM contas_config")
    for row in cur.fetchall():
        print(row)

print("\n=== TRANSACOES DE TRANSFERENCIA OU CONTAS ===")
cur.execute("PRAGMA table_info(transacoes)")
print("Colunas transacoes:", [r[1] for r in cur.fetchall()])
cur.execute("SELECT DISTINCT tipo FROM transacoes")
print("Tipos de transação:", [r[0] for r in cur.fetchall()])
cur.execute("SELECT DISTINCT conta FROM transacoes")
print("Contas em transações:", [r[0] for r in cur.fetchall()])

print("\n=== SALDO MERCADO PAGO E CARTEIRA ===")
res_saldo = saldo_service.calcular_saldo_consolidado(conn)
print("Saldo Consolidado:", res_saldo)

print("\n=== AJUSTES_SALDO ===")
cur.execute("SELECT * FROM ajustes_saldo")
for r in cur.fetchall():
    print(r)

print("\n=== TODAS TRANSACOES MERCADO PAGO ===")
cur.execute("SELECT id, data, descricao, valor, tipo, pago, afeta_saldo_bancario FROM transacoes WHERE conta LIKE '%Mercado%' ORDER BY data ASC, id ASC")
for r in cur.fetchall():
    print(r)

print("\n=== MISSÃO IPVA STATUS ===")
import planejamento_service
missao = planejamento_service.obter_status_missao_ipva(conn)
print("Status Missão IPVA:", missao)

conn.close()
