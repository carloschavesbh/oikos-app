"""
Sistema Financeiro Personalizado - Core SQLite
Inclui criação de tabelas e gerador de parcelas quinzenais (ex: Pagaleve / Pix 4x).
"""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def conectar_banco(nome_banco: Optional[str] = None) -> sqlite3.Connection:
    """Cria a conexão e ativa chaves estrangeiras."""
    caminho = nome_banco or os.environ.get("OIKOS_DB_PATH", "financas.db")
    conn = sqlite3.connect(caminho)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def inicializar_banco(conn: sqlite3.Connection) -> None:
    """Cria a estrutura de tabelas do sistema."""
    cursor = conn.cursor()

    # 1. Contas financeiras
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('corrente', 'dinheiro', 'cartao_credito', 'poupanca'))
    );
    """)

    # 2. Turnos de Trabalho (para motoristas e autônomos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos_trabalho (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        horas_trabalhadas REAL NOT NULL,
        km_rodados REAL,
        ganho_bruto REAL NOT NULL,
        despesa_combustivel REAL DEFAULT 0.0,
        meta_dia REAL,
        observacoes TEXT
    );
    """)

    # 3. Transações financeiras com suporte a grupos de parcelamento
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('receita', 'despesa', 'transferencia')),
        categoria TEXT NOT NULL,
        conta_id INTEGER,
        status TEXT NOT NULL CHECK(status IN ('efetivado', 'pendente')),
        grupo_parcelamento_id TEXT,
        numero_parcela INTEGER,
        total_parcelas INTEGER,
        FOREIGN KEY (conta_id) REFERENCES contas(id)
    );
    """)

    # 4. Faturas de Cartão de Crédito
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faturas_cartao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_cartao_id INTEGER NOT NULL,
        mes_referencia TEXT NOT NULL,
        data_fechamento DATE NOT NULL,
        data_vencimento DATE NOT NULL,
        status TEXT DEFAULT 'aberta' CHECK(status IN ('aberta', 'fechada', 'paga')),
        FOREIGN KEY (conta_cartao_id) REFERENCES contas(id)
    );
    """)

    conn.commit()


def registrar_compra_pagaleve(
    conn: sqlite3.Connection,
    descricao: str,
    valor_total: float,
    conta_id: int,
    categoria: str = "Compras Parceladas",
    data_compra: str = None
) -> List[Dict[str, Any]]:
    """
    Registra compra no modelo Pagaleve / Pix 4x:
    - 4 parcelas quinzenais (intervalo de 14 dias).
    - Parcela 1: Vence na hora (D+0) com status 'efetivado'.
    - Parcelas 2, 3 e 4: Vencem em D+14, D+28 e D+42 com status 'pendente'.
    - Ajusta centavos na primeira parcela para fechar o valor exato.
    """
    if data_compra is None:
        data_base = datetime.now().date()
    else:
        data_base = datetime.strptime(data_compra, "%Y-%m-%d").date()

    # Divisão com centavos exatos
    valor_base_parcela = round(valor_total / 4, 2)
    diferenca_centavos = round(valor_total - (valor_base_parcela * 4), 2)

    grupo_id = str(uuid.uuid4())
    parcelas_geradas = []

    cursor = conn.cursor()

    for n in range(1, 5):
        # Dias de acréscimo: 0, 14, 28, 42
        dias_offset = (n - 1) * 14
        data_vencimento = data_base + timedelta(days=dias_offset)

        # Ajuste de eventual arredondamento na 1ª parcela
        valor_parcela = valor_base_parcela + (diferenca_centavos if n == 1 else 0.0)
        status_parcela = "efetivado" if n == 1 else "pendente"
        desc_parcela = f"{descricao} ({n}/4 - Pix Parcelado)"

        cursor.execute("""
        INSERT INTO transacoes (
            data, descricao, valor, tipo, categoria, conta_id, status,
            grupo_parcelamento_id, numero_parcela, total_parcelas
        ) VALUES (?, ?, ?, 'despesa', ?, ?, ?, ?, ?, 4)
        """, (
            data_vencimento.strftime("%Y-%m-%d"),
            desc_parcela,
            valor_parcela,
            categoria,
            conta_id,
            status_parcela,
            grupo_id,
            n
        ))

        parcelas_geradas.append({
            "parcela": f"{n}/4",
            "data": data_vencimento.strftime("%Y-%m-%d"),
            "valor": valor_parcela,
            "status": status_parcela
        })

    conn.commit()
    return parcelas_geradas


if __name__ == "__main__":
    # Teste de execução rápida
    conexao = conectar_banco("financas_teste.db")
    inicializar_banco(conexao)

    # Insere conta padrão para teste
    cur = conexao.cursor()
    cur.execute("INSERT OR IGNORE INTO contas (id, nome, tipo) VALUES (1, 'Conta Corrente Principal', 'corrente')")
    conexao.commit()

    # Simulação: Compra de R$ 250,00 no Pagaleve
    parcelas = registrar_compra_pagaleve(
        conn=conexao,
        descricao="Tênis Corrida",
        valor_total=250.00,
        conta_id=1,
        data_compra="2026-10-17"
    )

    print("=== BANCO CRIADO COM SUCESSO ===")
    print("Parcelas registradas:")
    for p in parcelas:
        print(f"Parcela {p['parcela']} | Data: {p['data']} | Valor: R$ {p['valor']:.2f} | Status: {p['status']}")

    conexao.close()
