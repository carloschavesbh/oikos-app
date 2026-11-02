# -*- coding: utf-8 -*-
"""
Módulo de Serviço para Objetivos Financeiros e Finalidades dos Cofrinhos — Oikos Pessoal
Gerencia CRUD de objetivos, vínculos com cofrinhos e dívidas, e classificação de finalidade dos cofrinhos.
Regras fundamentais:
- Dinheiro de cofrinhos já pertence à conta de origem (não duplica ativos nem patrimônio).
- Cofrinho vinculado a dívida separa 'dinheiro reservado' de 'dívida paga' (não reduz passivo até liquidação real).
- Objetivos que atingem valor-alvo exibem 'valor-alvo alcançado' sem fechar ou considerar gasto automaticamente.
"""

import sqlite3
import datetime
from typing import Dict, List, Optional, Any

TIPOS_OBJETIVO = {
    "viagem": {"nome": "Viagem", "icone": "✈️"},
    "compra_bem": {"nome": "Compra de Bem", "icone": "🛍️"},
    "estudos": {"nome": "Estudos & Capacitação", "icone": "📚"},
    "reserva_seguranca": {"nome": "Reserva de Segurança", "icone": "🛡️"},
    "quitacao_divida": {"nome": "Quitação de Dívida", "icone": "🤝"},
    "aposentadoria": {"nome": "Aposentadoria / Futuro", "icone": "🏖️"},
    "outro": {"nome": "Outro Projeto", "icone": "🎯"}
}

FINALIDADES_COFRINHO = {
    "envelope": {
        "codigo": "envelope",
        "nome": "Envelope de Despesas",
        "descricao": "Despesas previstas ou recorrentes (mercado, contas, IPVA)",
        "icone": "✉️"
    },
    "reserva_seguranca": {
        "codigo": "reserva_seguranca",
        "nome": "Reserva de Segurança",
        "descricao": "Proteção para imprevistos e emergências",
        "icone": "🛡️"
    },
    "objetivo": {
        "codigo": "objetivo",
        "nome": "Objetivo / Acumulação",
        "descricao": "Acumulação para realização de projetos e sonhos",
        "icone": "🎯"
    },
    "outro": {
        "codigo": "outro",
        "nome": "Outro / Não Definida",
        "descricao": "Finalidade ainda não classificada",
        "icone": "📦"
    }
}


def inicializar_tabelas_objetivos(conn: sqlite3.Connection):
    """Cria a tabela objetivos e migra cofrinhos com a coluna finalidade."""
    cur = conn.cursor()

    # 1. Adicionar coluna finalidade em cofrinhos se não existir
    cur.execute("PRAGMA table_info(cofrinhos)")
    colunas_cof = [c[1] for c in cur.fetchall()]
    if "finalidade" not in colunas_cof:
        try:
            cur.execute("ALTER TABLE cofrinhos ADD COLUMN finalidade TEXT DEFAULT 'outro'")
        except Exception:
            pass

    # 2. Criar tabela objetivos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'outro',
            responsavel TEXT NOT NULL DEFAULT 'Carlos',
            valor_alvo REAL,
            prazo DATE,
            prioridade TEXT NOT NULL DEFAULT 'media',
            observacoes TEXT,
            cofrinho_id INTEGER REFERENCES cofrinhos(id) ON DELETE SET NULL,
            divida_id INTEGER REFERENCES dividas_gerenciamento(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'ativo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()


def listar_cofrinhos(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retorna a lista de cofrinhos com a finalidade classificada."""
    inicializar_tabelas_objetivos(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nome, saldo_confirmado, meta_valor, objetivo, finalidade, conta_pai_id
        FROM cofrinhos
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    cofrinhos = []
    for r in rows:
        fin_cod = (r[5] or "outro").strip().lower()
        if fin_cod not in FINALIDADES_COFRINHO:
            fin_cod = "outro"
        fin_info = FINALIDADES_COFRINHO[fin_cod]

        cofrinhos.append({
            "id": r[0],
            "nome": r[1],
            "saldo_confirmado": float(r[2] or 0.0),
            "meta_valor": float(r[3] or 0.0),
            "objetivo": r[4] or "",
            "finalidade": fin_cod,
            "finalidade_nome": fin_info["nome"],
            "finalidade_icone": fin_info["icone"],
            "finalidade_desc": fin_info["descricao"],
            "conta_pai_id": r[6]
        })
    return cofrinhos


def atualizar_finalidade_cofrinho(conn: sqlite3.Connection, cofrinho_id: int, finalidade: str):
    """Atualiza a finalidade de um cofrinho."""
    inicializar_tabelas_objetivos(conn)
    fin = (finalidade or "outro").strip().lower()
    if fin not in FINALIDADES_COFRINHO:
        fin = "outro"
    cur = conn.cursor()
    cur.execute("UPDATE cofrinhos SET finalidade = ? WHERE id = ?", (fin, cofrinho_id))
    conn.commit()


def listar_dividas_disponiveis(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retorna dívidas ativas para vínculo em objetivos."""
    cur = conn.cursor()
    cur.execute("SELECT id, credor, descricao, saldo_atual, status FROM dividas_gerenciamento WHERE status = 'ativa' ORDER BY id ASC")
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "credor": r[1],
            "descricao": r[2] or "",
            "saldo_atual": float(r[3] or 0.0),
            "status": r[4]
        }
        for r in rows
    ]


def listar_objetivos(conn: sqlite3.Connection, status_filtro: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna objetivos detalhados com cálculos de progresso e informações de vínculos."""
    inicializar_tabelas_objetivos(conn)
    cur = conn.cursor()

    query = """
        SELECT o.id, o.nome, o.tipo, o.responsavel, o.valor_alvo, o.prazo,
               o.prioridade, o.observacoes, o.cofrinho_id, o.divida_id,
               o.status, o.created_at, o.updated_at,
               c.nome as cofrinho_nome, c.saldo_confirmado as cofrinho_saldo, c.finalidade as cofrinho_finalidade,
               d.credor as divida_credor, d.descricao as divida_desc, d.saldo_atual as divida_saldo
        FROM objetivos o
        LEFT JOIN cofrinhos c ON o.cofrinho_id = c.id
        LEFT JOIN dividas_gerenciamento d ON o.divida_id = d.id
    """
    params = []
    if status_filtro:
        query += " WHERE o.status = ?"
        params.append(status_filtro)
    query += " ORDER BY CASE o.prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, o.id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()

    objetivos = []
    for r in rows:
        val_alvo = float(r[4]) if r[4] is not None else None
        saldo_cof = float(r[14] or 0.0) if r[8] else 0.0
        saldo_div = float(r[18] or 0.0) if r[9] else 0.0

        # Progresso em relação ao valor-alvo
        progresso_pct = None
        falta_acumular = None
        atingiu_alvo = False
        if val_alvo is not None and val_alvo > 0:
            progresso_pct = min(100.0, round((saldo_cof / val_alvo) * 100.0, 1))
            falta_acumular = max(0.0, round(val_alvo - saldo_cof, 2))
            atingiu_alvo = bool(saldo_cof >= val_alvo)

        # Progresso em relação à dívida (se houver dívida vinculada)
        divida_cobertura_pct = None
        if r[9] and saldo_div > 0:
            divida_cobertura_pct = min(100.0, round((saldo_cof / saldo_div) * 100.0, 1))

        tipo_info = TIPOS_OBJETIVO.get(r[2], TIPOS_OBJETIVO["outro"])

        objetivos.append({
            "id": r[0],
            "nome": r[1],
            "tipo": r[2],
            "tipo_nome": tipo_info["nome"],
            "tipo_icone": tipo_info["icone"],
            "responsavel": r[3],
            "valor_alvo": val_alvo,
            "prazo": str(r[5]) if r[5] else None,
            "prioridade": r[6],
            "observacoes": r[7] or "",
            "cofrinho_id": r[8],
            "cofrinho_nome": r[13],
            "cofrinho_saldo": saldo_cof,
            "cofrinho_finalidade": r[15] or "outro",
            "divida_id": r[9],
            "divida_credor": r[16],
            "divida_desc": r[17],
            "divida_saldo": saldo_div,
            "divida_cobertura_pct": divida_cobertura_pct,
            "status": r[10],
            "created_at": str(r[11]),
            "updated_at": str(r[12]),
            # Métricas calculadas
            "saldo_destinado": saldo_cof,
            "progresso_pct": progresso_pct,
            "falta_acumular": falta_acumular,
            "atingiu_alvo": atingiu_alvo
        })

    return objetivos


def obter_objetivo(conn: sqlite3.Connection, objetivo_id: int) -> Optional[Dict[str, Any]]:
    """Retorna detalhes de um objetivo específico."""
    objetivos = listar_objetivos(conn)
    return next((o for o in objetivos if o["id"] == objetivo_id), None)


def criar_objetivo(conn: sqlite3.Connection, dados: Dict[str, Any]) -> int:
    """Cadastra um novo objetivo."""
    inicializar_tabelas_objetivos(conn)
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do objetivo é obrigatório.")

    tipo = (dados.get("tipo") or "outro").strip().lower()
    if tipo not in TIPOS_OBJETIVO:
        tipo = "outro"

    responsavel = (dados.get("responsavel") or "Carlos").strip()
    prioridade = (dados.get("prioridade") or "media").strip().lower()
    if prioridade not in ["baixa", "media", "alta"]:
        prioridade = "media"

    val_alvo_raw = dados.get("valor_alvo")
    valor_alvo = float(val_alvo_raw) if (val_alvo_raw is not None and str(val_alvo_raw).strip() != "") else None

    prazo_raw = dados.get("prazo")
    prazo = str(prazo_raw).strip() if (prazo_raw and str(prazo_raw).strip() != "") else None

    observacoes = (dados.get("observacoes") or "").strip()

    cofrinho_id_raw = dados.get("cofrinho_id")
    cofrinho_id = int(cofrinho_id_raw) if (cofrinho_id_raw and str(cofrinho_id_raw).strip() != "") else None

    divida_id_raw = dados.get("divida_id")
    divida_id = int(divida_id_raw) if (divida_id_raw and str(divida_id_raw).strip() != "") else None

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO objetivos (nome, tipo, responsavel, valor_alvo, prazo, prioridade, observacoes, cofrinho_id, divida_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ativo')
    """, (nome, tipo, responsavel, valor_alvo, prazo, prioridade, observacoes, cofrinho_id, divida_id))
    novo_id = cur.lastrowid
    conn.commit()
    return novo_id


def atualizar_objetivo(conn: sqlite3.Connection, objetivo_id: int, dados: Dict[str, Any]):
    """Atualiza os dados de um objetivo."""
    inicializar_tabelas_objetivos(conn)
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do objetivo é obrigatório.")

    tipo = (dados.get("tipo") or "outro").strip().lower()
    responsavel = (dados.get("responsavel") or "Carlos").strip()
    prioridade = (dados.get("prioridade") or "media").strip().lower()

    val_alvo_raw = dados.get("valor_alvo")
    valor_alvo = float(val_alvo_raw) if (val_alvo_raw is not None and str(val_alvo_raw).strip() != "") else None

    prazo_raw = dados.get("prazo")
    prazo = str(prazo_raw).strip() if (prazo_raw and str(prazo_raw).strip() != "") else None

    observacoes = (dados.get("observacoes") or "").strip()

    cofrinho_id_raw = dados.get("cofrinho_id")
    cofrinho_id = int(cofrinho_id_raw) if (cofrinho_id_raw and str(cofrinho_id_raw).strip() != "") else None

    divida_id_raw = dados.get("divida_id")
    divida_id = int(divida_id_raw) if (divida_id_raw and str(divida_id_raw).strip() != "") else None

    cur = conn.cursor()
    cur.execute("""
        UPDATE objetivos
        SET nome = ?, tipo = ?, responsavel = ?, valor_alvo = ?, prazo = ?,
            prioridade = ?, observacoes = ?, cofrinho_id = ?, divida_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (nome, tipo, responsavel, valor_alvo, prazo, prioridade, observacoes, cofrinho_id, divida_id, objetivo_id))
    conn.commit()


def alterar_status_objetivo(conn: sqlite3.Connection, objetivo_id: int, novo_status: str):
    """Altera o status de um objetivo (ativo, pausado, alcancado, concluido, arquivado)."""
    status_validos = ["ativo", "pausado", "alcancado", "concluido", "arquivado"]
    st = (novo_status or "ativo").strip().lower()
    if st not in status_validos:
        raise ValueError(f"Status inválido: {novo_status}")

    cur = conn.cursor()
    cur.execute("UPDATE objetivos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (st, objetivo_id))
    conn.commit()


def excluir_objetivo(conn: sqlite3.Connection, objetivo_id: int):
    """Exclui um objetivo sem afetar cofrinhos ou transações financeiras."""
    cur = conn.cursor()
    cur.execute("DELETE FROM objetivos WHERE id = ?", (objetivo_id,))
    conn.commit()
