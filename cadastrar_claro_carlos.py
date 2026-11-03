#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para registrar as contas da Claro Móvel Carlos e configurar despesa fixa recorrente:
1. Faturas específicas:
   - 2026-08-19: R$ 37,16 (Pendente)
   - 2026-09-19: R$ 67,80 (Pendente)
   - 2026-10-19: R$ 33,97 (Pendente)
2. Despesa Fixa Recorrente:
   - Valor base: R$ 33,97
   - Dia 19 de cada mês
   - A partir de 2026-11-19 (12 ocorrências projetadas)
"""

import sqlite3
import os
from datetime import date
import calendar

DB_PATH = os.environ.get(
    "OIKOS_DB_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "financas_casa.db"))
)

def cadastrar_claro():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Obter ou criar subcategoria 'Telefone (Carlos)' no grupo 1 (Habitação)
    cur.execute("SELECT id FROM subcategorias WHERE LOWER(TRIM(nome)) = 'telefone (carlos)' AND grupo_id = 1")
    row_sub = cur.fetchone()
    if row_sub:
        subcat_id = row_sub[0]
        print(f"[OK] Subcategoria 'Telefone (Carlos)' encontrada (ID: {subcat_id}).")
    else:
        cur.execute("""
            INSERT INTO subcategorias (grupo_id, nome, icone, natureza_padrao, finalidade, ativo)
            VALUES (1, 'Telefone (Carlos)', '📱', 'fixa', 'familiar', 1)
        """)
        subcat_id = cur.lastrowid
        print(f"[OK] Subcategoria 'Telefone (Carlos)' criada com sucesso (ID: {subcat_id}).")

    grupo_id = 1
    categoria = "HABITAÇÃO"
    conta = "Mercado Pago"
    conta_id = 1
    titular = "Carlos"
    grp_fixa = "fixa_claro_carlos"

    # 2. As 3 faturas específicas (Agosto, Setembro e Outubro de 2026)
    faturas_reais = [
        ("2026-08-19", 37.16),
        ("2026-09-19", 67.80),
        ("2026-10-19", 33.97),
    ]

    print("\n--- Inserindo / Verificando faturas passadas e atual ---")
    for dt_venc, val in faturas_reais:
        cur.execute("""
            SELECT id, valor, pago FROM transacoes 
            WHERE data = ? AND LOWER(TRIM(descricao)) = 'claro móvel carlos'
        """, (dt_venc,))
        existente = cur.fetchone()
        if existente:
            print(f"[-] Fatura de {dt_venc} (R$ {val:.2f}) já existe no banco (ID {existente[0]}).")
        else:
            cur.execute("""
                INSERT INTO transacoes (
                    data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                    status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                    status_rateio, natureza_gasto, titular, grupo_id, subcategoria_id
                ) VALUES (?, 'Claro Móvel Carlos', ?, 'despesa', ?, ?, ?, 0, 'pendente', 1, ?, 'fixa_recorrente', 'fixa', ?, ?, ?)
            """, (dt_venc, val, categoria, conta, conta_id, grp_fixa, titular, grupo_id, subcat_id))
            novo_id = cur.lastrowid
            print(f"[+] Fatura de {dt_venc} (R$ {val:.2f}) inserida com sucesso (ID {novo_id}).")

    # 3. Gerar ocorrências recorrentes a partir de 2026-11-19 (12 meses)
    print("\n--- Inserindo / Verificando recorrências futuras (2026-11-19 em diante) ---")
    val_base = 33.97
    start_year = 2026
    start_month = 11
    qtd_meses = 12

    for i in range(qtd_meses):
        m = ((start_month - 1 + i) % 12) + 1
        y = start_year + ((start_month - 1 + i) // 12)
        max_d = calendar.monthrange(y, m)[1]
        dia = min(19, max_d)
        dt_venc = f"{y}-{m:02d}-{dia:02d}"

        cur.execute("""
            SELECT id FROM transacoes 
            WHERE data = ? AND LOWER(TRIM(descricao)) = 'claro móvel carlos'
        """, (dt_venc,))
        existente = cur.fetchone()
        if existente:
            print(f"[-] Ocorrência {i+1}/{qtd_meses} de {dt_venc} (R$ {val_base:.2f}) já existe (ID {existente[0]}).")
        else:
            cur.execute("""
                INSERT INTO transacoes (
                    data, descricao, valor, tipo, categoria, conta, conta_id, pago,
                    status_pagamento, afeta_saldo_bancario, grupo_parcelamento,
                    numero_parcela, total_parcelas_compra,
                    status_rateio, natureza_gasto, titular, grupo_id, subcategoria_id
                ) VALUES (?, 'Claro Móvel Carlos', ?, 'despesa', ?, ?, ?, 0, 'pendente', 1, ?, ?, ?, 'fixa_recorrente', 'fixa', ?, ?, ?)
            """, (dt_venc, val_base, categoria, conta, conta_id, grp_fixa, i + 1, qtd_meses, titular, grupo_id, subcat_id))
            novo_id = cur.lastrowid
            print(f"[+] Ocorrência {i+1}/{qtd_meses} de {dt_venc} (R$ {val_base:.2f}) inserida (ID {novo_id}).")

    conn.commit()

    # Consulta final de conferência
    cur.execute("""
        SELECT id, data, descricao, valor, pago, status_pagamento, categoria, conta, grupo_parcelamento
        FROM transacoes
        WHERE LOWER(TRIM(descricao)) = 'claro móvel carlos'
        ORDER BY data ASC
    """)
    rows = cur.fetchall()
    print(f"\nTotal de registros 'Claro Móvel Carlos' no banco: {len(rows)}")
    for r in rows:
        print(f"ID {r[0]}: Data {r[1]} | R$ {r[3]:.2f} | Pago: {r[4]} ({r[5]}) | Conta: {r[7]} | Grupo: {r[8]}")

    conn.close()

if __name__ == "__main__":
    cadastrar_claro()
