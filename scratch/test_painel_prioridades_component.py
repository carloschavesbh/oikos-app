import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
from decimal import Decimal
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))

import saldo_service
import planejamento_service

def test_component_logic():
    conn = sqlite3.connect('financas_casa.db')
    hoje = date(2026, 10, 20)
    hoje_str = hoje.strftime("%Y-%m-%d")
    limite_7d = hoje + timedelta(days=7)
    limite_7d_str = limite_7d.strftime("%Y-%m-%d")
    fim_mes = date(2026, 10, 31)
    fim_mes_str = fim_mes.strftime("%Y-%m-%d")

    # 1. Saldos
    contas = saldo_service.obter_contas(conn)
    saldos = []
    for c in contas:
        s = saldo_service.calcular_saldo_conta(conn, c['id'])
        saldos.append({'id': c['id'], 'nome': c['nome'], 'saldo': float(s['saldo_atual'])})
    saldo_cons = float(saldo_service.calcular_saldo_consolidado(conn)['saldo_consolidado'])

    # 2. Despesas
    df_desp = pd.read_sql_query("""
        SELECT id, data, descricao, valor, categoria, conta, conta_id,
               COALESCE(afeta_saldo_bancario, 1) as afeta_banco,
               COALESCE(status_pagamento, 'pendente') as status_pag,
               COALESCE(status_conciliacao_fatura, 'normal') as status_fatura
        FROM transacoes
        WHERE tipo = 'despesa' AND (pago IS NULL OR pago != 1)
        ORDER BY data, id
    """, conn)

    df_caixa = df_desp[df_desp['afeta_banco'] == 1]
    df_folha = df_desp[df_desp['afeta_banco'] == 0]

    vencidas = df_caixa[df_caixa['data'] < hoje_str]
    vencem_hoje = df_caixa[df_caixa['data'] == hoje_str]
    prox_7d = df_caixa[(df_caixa['data'] > hoje_str) & (df_caixa['data'] <= limite_7d_str)]
    restante = df_caixa[(df_caixa['data'] > limite_7d_str) & (df_caixa['data'] <= fim_mes_str)]

    tot_vencidas = float(vencidas['valor'].sum())
    tot_hoje = float(vencem_hoje['valor'].sum())
    tot_7d = float(prox_7d['valor'].sum())
    tot_restante = float(restante['valor'].sum())
    tot_caixa = float(df_caixa['valor'].sum())

    # BV específico
    bv_row = df_caixa[df_caixa['descricao'].str.contains('BV', case=False, na=False)]
    val_bv_nominal = float(bv_row['valor'].iloc[0]) if not bv_row.empty else 0.0
    val_bv_ref = 1921.22

    # IPVA específico
    ipva_row = df_caixa[df_caixa['descricao'].str.contains('IPVA', case=False, na=False)]
    val_ipva = float(ipva_row['valor'].iloc[0]) if not ipva_row.empty else 0.0

    # 7 dias sem BV
    tot_7d_sem_bv = tot_7d - val_bv_nominal

    # Simulação 99
    dias_restantes_mes = (fim_mes - hoje).days + 1
    dias_trab = 8
    margem_liq = 0.65

    # Cenário 1: Tudo (com BV nominal)
    falta_tudo_nominal = max(0.0, tot_caixa - saldo_cons)
    meta_liq_dia_tudo = falta_tudo_nominal / dias_trab
    meta_bruta_dia_tudo = meta_liq_dia_tudo / margem_liq

    # Cenário 2: Tudo (com BV ref)
    tot_caixa_ref = tot_caixa - val_bv_nominal + val_bv_ref
    falta_tudo_ref = max(0.0, tot_caixa_ref - saldo_cons)
    meta_liq_dia_ref = falta_tudo_ref / dias_trab
    meta_bruta_dia_ref = meta_liq_dia_ref / margem_liq

    # Cenário 3: Essenciais + IPVA (sem BV)
    tot_essenciais = tot_caixa - val_bv_nominal
    falta_essenciais = max(0.0, tot_essenciais - saldo_cons)
    meta_liq_dia_essenciais = falta_essenciais / dias_trab
    meta_bruta_dia_essenciais = meta_liq_dia_essenciais / margem_liq

    print("Component logic executed successfully!")
    print(f"Saldo Consolidado: R$ {saldo_cons:.2f}")
    print(f"Total Vencidas: R$ {tot_vencidas:.2f} ({len(vencidas)} contas)")
    print(f"Total 7 dias (com BV nominal): R$ {tot_7d:.2f} | Sem BV: R$ {tot_7d_sem_bv:.2f}")
    print(f"Total Restante (IPVA): R$ {tot_restante:.2f}")
    print(f"Falta para o mês (com BV nominal): R$ {falta_tudo_nominal:.2f} -> Meta líq/dia ({dias_trab}d): R$ {meta_liq_dia_tudo:.2f} (Bruto: R$ {meta_bruta_dia_tudo:.2f})")
    print(f"Falta para o mês (sem BV): R$ {falta_essenciais:.2f} -> Meta líq/dia ({dias_trab}d): R$ {meta_liq_dia_essenciais:.2f} (Bruto: R$ {meta_bruta_dia_essenciais:.2f})")

    conn.close()

test_component_logic()
