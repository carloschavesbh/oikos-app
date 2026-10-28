import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
from decimal import Decimal
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
import saldo_service

conn = sqlite3.connect('financas_casa.db')
hoje = date(2026, 10, 20)
hoje_str = hoje.strftime("%Y-%m-%d")
limite_7d = hoje + timedelta(days=7)
limite_7d_str = limite_7d.strftime("%Y-%m-%d")
fim_mes = date(2026, 10, 31)
fim_mes_str = fim_mes.strftime("%Y-%m-%d")

# 1. Saldos reais
contas = saldo_service.obter_contas(conn)
print("=== 1. SALDOS REAIS POR CONTA ===")
for c in contas:
    s = saldo_service.calcular_saldo_conta(conn, c['id'])
    print(f"  [{c['id']}] {c['nome']}: R$ {s['saldo_atual']}")

saldo_cons = saldo_service.calcular_saldo_consolidado(conn)
print(f"  Total Consolidado: R$ {saldo_cons['saldo_consolidado']}")

# 2. Despesas pendentes
df_desp = pd.read_sql_query("""
    SELECT id, data, descricao, valor, categoria, conta, conta_id,
           COALESCE(afeta_saldo_bancario, 1) as afeta_banco,
           COALESCE(status_pagamento, 'pendente') as status_pag,
           COALESCE(status_conciliacao_fatura, 'normal') as status_fatura
    FROM transacoes
    WHERE tipo = 'despesa' AND (pago IS NULL OR pago != 1)
    ORDER BY data, id
""", conn)

df_folha = df_desp[df_desp['afeta_banco'] == 0]
df_caixa = df_desp[df_desp['afeta_banco'] == 1]

df_vencidas = df_caixa[df_caixa['data'] < hoje_str]
df_hoje = df_caixa[df_caixa['data'] == hoje_str]
df_7d = df_caixa[(df_caixa['data'] > hoje_str) & (df_caixa['data'] <= limite_7d_str)]
df_restante = df_caixa[(df_caixa['data'] > limite_7d_str) & (df_caixa['data'] <= fim_mes_str)]

print("\n=== 2. DIVISÃO TEMPORAL ===")
print(f"Vencidas ({len(df_vencidas)}): R$ {df_vencidas['valor'].sum():.2f}")
print(f"Vencem Hoje ({len(df_hoje)}): R$ {df_hoje['valor'].sum():.2f}")
print(f"Próximos 7 dias ({len(df_7d)}): R$ {df_7d['valor'].sum():.2f}")
print(f"Restante do Mês ({len(df_restante)}): R$ {df_restante['valor'].sum():.2f}")
print(f"Total Caixa Pendente: R$ {df_caixa['valor'].sum():.2f}")

conn.close()
