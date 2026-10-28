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

def render_painel_prioridades_operacional_simulated():
    conn = sqlite3.connect('financas_casa.db')
    hoje = date(2026, 10, 20)
    hoje_str = hoje.strftime("%Y-%m-%d")
    limite_7d = hoje + timedelta(days=7)
    limite_7d_str = limite_7d.strftime("%Y-%m-%d")
    fim_mes = date(2026, 10, 31)
    fim_mes_str = fim_mes.strftime("%Y-%m-%d")

    # 1. Saldos
    contas = saldo_service.obter_contas(conn)
    saldos_dict = {}
    for c in contas:
        s = saldo_service.calcular_saldo_conta(conn, c['id'])
        saldos_dict[c['nome']] = float(s['saldo_atual'])
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

    bv_row = df_caixa[df_caixa['descricao'].str.contains('BV', case=False, na=False)]
    val_bv_nominal = float(bv_row['valor'].iloc[0]) if not bv_row.empty else 0.0
    val_bv_ref = 1921.22
    tot_7d_sem_bv = tot_7d - val_bv_nominal

    # Simulação
    dias_restantes_mes = (fim_mes - hoje).days + 1
    dias_trab = 8
    margem_liq = 0.65

    # Testar os 3 cenários de meta
    falta_com_bv_nom = max(0.0, tot_caixa - saldo_cons)
    falta_com_bv_ref = max(0.0, (tot_caixa - val_bv_nominal + val_bv_ref) - saldo_cons)
    falta_sem_bv = max(0.0, (tot_caixa - val_bv_nominal) - saldo_cons)

    print("=== DADOS VALIDADOS COM SUCESSO ===")
    print(f"Saldo Consolidado: R$ {saldo_cons:,.2f}")
    print(f"Mercado Pago: R$ {saldos_dict.get('Mercado Pago', 0.0):,.2f}")
    print(f"Dinheiro / Carteira: R$ {saldos_dict.get('Carteira - Dinheiro Físico', 0.0):,.2f}")
    print(f"Vencidas ({len(vencidas)}): R$ {tot_vencidas:,.2f}")
    print(f"Vencem hoje ({len(vencem_hoje)}): R$ {tot_hoje:,.2f}")
    print(f"7 dias (com BV): R$ {tot_7d:,.2f} | Sem BV: R$ {tot_7d_sem_bv:,.2f}")
    print(f"Restante mês (IPVA): R$ {tot_restante:,.2f}")
    print(f"Total Caixa de Outubro: R$ {tot_caixa:,.2f}")
    print(f"Descontos em Folha (Plano Saúde): R$ {df_folha['valor'].sum():,.2f}")
    print(f"\nCenário 1 (Tudo com BV nominal R$ 1.428,82): Falta R$ {falta_com_bv_nom:,.2f} -> Meta líq: R$ {falta_com_bv_nom/dias_trab:,.2f}/dia -> Bruto: R$ {(falta_com_bv_nom/dias_trab)/margem_liq:,.2f}/dia")
    print(f"Cenário 2 (Tudo com BV referência R$ 1.921,22): Falta R$ {falta_com_bv_ref:,.2f} -> Meta líq: R$ {falta_com_bv_ref/dias_trab:,.2f}/dia -> Bruto: R$ {(falta_com_bv_ref/dias_trab)/margem_liq:,.2f}/dia")
    print(f"Cenário 3 (Essenciais + IPVA sem BV): Falta R$ {falta_sem_bv:,.2f} -> Meta líq: R$ {falta_sem_bv/dias_trab:,.2f}/dia -> Bruto: R$ {(falta_sem_bv/dias_trab)/margem_liq:,.2f}/dia")

    conn.close()

render_painel_prioridades_operacional_simulated()
