"""
Módulo de Serviço para Patrimônio e Bens — Oikos Pessoal
Gerencia cadastro, reavaliação histórica, dívidas associadas e cálculo de Patrimônio Líquido.
Regra fundamental: Alterações patrimoniais NUNCA afetam o caixa (transações).
"""

import sqlite3
import datetime
from typing import Dict, List, Optional, Any
from dateutil.parser import parse as parse_date


def inicializar_tabelas_patrimonio(conn: sqlite3.Connection):
    """Cria as tabelas de bens e avaliações se não existirem, preservando integridade."""
    cur = conn.cursor()
    
    # 1. Tabela de Bens
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            proprietario TEXT NOT NULL DEFAULT 'Carlos',
            valor_aquisicao REAL,
            data_aquisicao DATE,
            valor_atual_estimado REAL NOT NULL DEFAULT 0.0,
            data_avaliacao DATE NOT NULL,
            observacoes TEXT,
            status TEXT NOT NULL DEFAULT 'ativo',
            is_veiculo_drive INTEGER NOT NULL DEFAULT 0,
            divida_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Tabela de Histórico de Avaliações
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bens_avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bem_id INTEGER NOT NULL,
            valor_estimado REAL NOT NULL,
            data_avaliacao DATE NOT NULL,
            observacoes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bem_id) REFERENCES bens(id) ON DELETE CASCADE
        );
    """)

    # 3. Adicionar coluna bem_id em dividas_gerenciamento caso não exista
    cur.execute("PRAGMA table_info(dividas_gerenciamento)")
    colunas_div = [c[1] for c in cur.fetchall()]
    if "bem_id" not in colunas_div:
        try:
            cur.execute("ALTER TABLE dividas_gerenciamento ADD COLUMN bem_id INTEGER REFERENCES bens(id)")
        except Exception:
            pass

    conn.commit()


def listar_bens(conn: sqlite3.Connection, incluir_arquivados: bool = False) -> List[Dict[str, Any]]:
    """Retorna a lista de bens com informações da dívida associada e histórico básico."""
    inicializar_tabelas_patrimonio(conn)
    cur = conn.cursor()
    
    query = """
        SELECT b.id, b.nome, b.tipo, b.proprietario, b.valor_aquisicao, b.data_aquisicao,
               b.valor_atual_estimado, b.data_avaliacao, b.observacoes, b.status,
               b.is_veiculo_drive, b.divida_id, b.created_at, b.updated_at,
               d.credor as divida_credor, d.descricao as divida_desc, d.saldo_atual as divida_saldo
        FROM bens b
        LEFT JOIN dividas_gerenciamento d ON b.divida_id = d.id OR d.bem_id = b.id
    """
    if not incluir_arquivados:
        query += " WHERE b.status = 'ativo'"
    query += " ORDER BY b.status ASC, b.valor_atual_estimado DESC, b.id DESC"

    cur.execute(query)
    rows = cur.fetchall()
    
    bens = []
    for r in rows:
        val_est = float(r[6] or 0.0)
        val_aq = float(r[4]) if r[4] is not None else None
        
        # Variação histórica em relação à aquisição (se houver)
        var_aq = None
        var_aq_pct = None
        if val_aq is not None and val_aq > 0:
            var_aq = round(val_est - val_aq, 2)
            var_aq_pct = round((var_aq / val_aq) * 100.0, 1)

        bens.append({
            "id": r[0],
            "nome": r[1],
            "tipo": r[2],
            "proprietario": r[3],
            "valor_aquisicao": val_aq,
            "data_aquisicao": str(r[5]) if r[5] else None,
            "valor_atual_estimado": val_est,
            "data_avaliacao": str(r[7]),
            "observacoes": r[8] or "",
            "status": r[9],
            "is_veiculo_drive": bool(r[10]),
            "divida_id": r[11],
            "created_at": str(r[12]),
            "updated_at": str(r[13]),
            "divida_credor": r[14],
            "divida_desc": r[15],
            "divida_saldo": float(r[16]) if r[16] is not None else 0.0,
            "variacao_aquisicao": var_aq,
            "variacao_aquisicao_pct": var_aq_pct
        })
    return bens


def obter_bem(conn: sqlite3.Connection, bem_id: int) -> Optional[Dict[str, Any]]:
    """Retorna detalhes de um bem específico e seu histórico de reavaliações."""
    bens = listar_bens(conn, incluir_arquivados=True)
    bem = next((b for b in bens if b["id"] == bem_id), None)
    if not bem:
        return None
    
    bem["avaliacoes"] = listar_historico_avaliacoes(conn, bem_id)
    return bem


def criar_bem(conn: sqlite3.Connection, dados: Dict[str, Any]) -> int:
    """
    Cadastra um novo bem e registra sua primeira avaliação no histórico.
    Campos opcionais: valor_aquisicao, data_aquisicao, observacoes, divida_id.
    """
    inicializar_tabelas_patrimonio(conn)
    cur = conn.cursor()

    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do bem é obrigatório.")

    tipo = dados.get("tipo") or "Outro"
    proprietario = dados.get("proprietario") or "Carlos"
    
    # Tratamento de campos opcionais de aquisição
    val_aq_raw = dados.get("valor_aquisicao")
    valor_aquisicao = float(val_aq_raw) if (val_aq_raw is not None and str(val_aq_raw).strip() != "") else None
    
    dt_aq_raw = dados.get("data_aquisicao")
    data_aquisicao = str(dt_aq_raw).strip() if (dt_aq_raw and str(dt_aq_raw).strip() != "") else None

    # Valor atual estimado (aceita 'valor_atual_estimado' ou 'valor_atual')
    val_est_raw = dados.get("valor_atual_estimado")
    if val_est_raw is None or str(val_est_raw).strip() == "":
        val_est_raw = dados.get("valor_atual", 0.0)
    valor_atual_estimado = float(val_est_raw or 0.0)

    # Data da avaliação
    dt_av_raw = dados.get("data_avaliacao")
    data_avaliacao = str(dt_av_raw).strip() if dt_av_raw else datetime.date.today().strftime("%Y-%m-%d")

    observacoes = dados.get("observacoes") or ""
    is_veiculo_drive = 1 if dados.get("is_veiculo_drive") in (1, True, "1", "true") else 0
    divida_id = dados.get("divida_id")
    if divida_id in ("", None, "null"):
        divida_id = None
    else:
        divida_id = int(divida_id)

    # Se este bem for marcado como veículo do Drive, remove a marcação de outros veículos
    if is_veiculo_drive:
        cur.execute("UPDATE bens SET is_veiculo_drive = 0 WHERE is_veiculo_drive = 1")

    cur.execute("""
        INSERT INTO bens (
            nome, tipo, proprietario, valor_aquisicao, data_aquisicao,
            valor_atual_estimado, data_avaliacao, observacoes, status,
            is_veiculo_drive, divida_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ativo', ?, ?, CURRENT_TIMESTAMP)
    """, (
        nome, tipo, proprietario, valor_aquisicao, data_aquisicao,
        valor_atual_estimado, data_avaliacao, observacoes,
        is_veiculo_drive, divida_id
    ))
    bem_id = cur.lastrowid

    # Registra no histórico de avaliações inicial
    cur.execute("""
        INSERT INTO bens_avaliacoes (bem_id, valor_estimado, data_avaliacao, observacoes)
        VALUES (?, ?, ?, ?)
    """, (bem_id, valor_atual_estimado, data_avaliacao, observacoes or "Avaliação inicial de cadastro"))

    # Se informou dívida, atualiza bem_id na dividas_gerenciamento
    if divida_id:
        cur.execute("UPDATE dividas_gerenciamento SET bem_id = ? WHERE id = ?", (bem_id, divida_id))

    conn.commit()
    return bem_id


def atualizar_bem(conn: sqlite3.Connection, bem_id: int, dados: Dict[str, Any]) -> bool:
    """
    Atualiza os dados de um bem. Se o valor_atual_estimado mudar,
    registra automaticamente uma nova linha no histórico de avaliações.
    NÃO toca na tabela transacoes (sem impacto no caixa).
    """
    cur = conn.cursor()
    cur.execute("SELECT valor_atual_estimado, data_avaliacao FROM bens WHERE id = ?", (bem_id,))
    row = cur.fetchone()
    if not row:
        return False
    
    val_antigo = float(row[0] or 0.0)

    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("O nome do bem é obrigatório.")

    tipo = dados.get("tipo") or "Outro"
    proprietario = dados.get("proprietario") or "Carlos"
    
    val_aq_raw = dados.get("valor_aquisicao")
    valor_aquisicao = float(val_aq_raw) if (val_aq_raw is not None and str(val_aq_raw).strip() != "") else None
    
    dt_aq_raw = dados.get("data_aquisicao")
    data_aquisicao = str(dt_aq_raw).strip() if (dt_aq_raw and str(dt_aq_raw).strip() != "") else None

    valor_atual_estimado = float(dados.get("valor_atual_estimado", val_antigo))
    dt_av_raw = dados.get("data_avaliacao")
    data_avaliacao = str(dt_av_raw).strip() if dt_av_raw else datetime.date.today().strftime("%Y-%m-%d")
    observacoes = dados.get("observacoes") or ""
    is_veiculo_drive = 1 if dados.get("is_veiculo_drive") in (1, True, "1", "true") else 0
    
    divida_id = dados.get("divida_id")
    if divida_id in ("", None, "null"):
        divida_id = None
    else:
        divida_id = int(divida_id)

    if is_veiculo_drive:
        cur.execute("UPDATE bens SET is_veiculo_drive = 0 WHERE is_veiculo_drive = 1 AND id != ?", (bem_id,))

    cur.execute("""
        UPDATE bens
        SET nome = ?, tipo = ?, proprietario = ?, valor_aquisicao = ?,
            data_aquisicao = ?, valor_atual_estimado = ?, data_avaliacao = ?,
            observacoes = ?, is_veiculo_drive = ?, divida_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        nome, tipo, proprietario, valor_aquisicao, data_aquisicao,
        valor_atual_estimado, data_avaliacao, observacoes,
        is_veiculo_drive, divida_id, bem_id
    ))

    # Se o valor mudou significativamente (diferença > R$ 0,01), registra no histórico
    if abs(valor_atual_estimado - val_antigo) >= 0.01:
        obs_reaval = dados.get("motivo_reavaliacao") or "Atualização de valor estimado do bem"
        cur.execute("""
            INSERT INTO bens_avaliacoes (bem_id, valor_estimado, data_avaliacao, observacoes)
            VALUES (?, ?, ?, ?)
        """, (bem_id, valor_atual_estimado, data_avaliacao, obs_reaval))

    if divida_id:
        cur.execute("UPDATE dividas_gerenciamento SET bem_id = ? WHERE id = ?", (bem_id, divida_id))

    conn.commit()
    return True


def registrar_nova_avaliacao(
    conn: sqlite3.Connection,
    bem_id: int,
    valor_estimado: float,
    data_avaliacao: str,
    observacoes: Optional[str] = None
) -> bool:
    """Registra uma nova reavaliação periódica do bem no histórico e atualiza seu valor vigente."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM bens WHERE id = ?", (bem_id,))
    if not cur.fetchone():
        return False

    dt_av = str(data_avaliacao).strip() if data_avaliacao else datetime.date.today().strftime("%Y-%m-%d")
    obs = observacoes or "Reavaliação periódica de mercado"

    cur.execute("""
        INSERT INTO bens_avaliacoes (bem_id, valor_estimado, data_avaliacao, observacoes)
        VALUES (?, ?, ?, ?)
    """, (bem_id, float(valor_estimado), dt_av, obs))

    cur.execute("""
        UPDATE bens
        SET valor_atual_estimado = ?, data_avaliacao = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (float(valor_estimado), dt_av, bem_id))

    conn.commit()
    return True


def alterar_status_bem(conn: sqlite3.Connection, bem_id: int, status: str) -> bool:
    """Altera o status de um bem (ex: 'ativo', 'arquivado')."""
    if status not in ("ativo", "arquivado"):
        raise ValueError("Status deve ser 'ativo' ou 'arquivado'.")
    cur = conn.cursor()
    cur.execute("UPDATE bens SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, bem_id))
    conn.commit()
    return cur.rowcount > 0


def listar_historico_avaliacoes(conn: sqlite3.Connection, bem_id: int) -> List[Dict[str, Any]]:
    """Retorna todas as avaliações registradas de um bem ordenadas por data."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, valor_estimado, data_avaliacao, observacoes, created_at
        FROM bens_avaliacoes
        WHERE bem_id = ?
        ORDER BY data_avaliacao ASC, id ASC
    """, (bem_id,))
    rows = cur.fetchall()
    
    historico = []
    val_anterior = None
    for r in rows:
        val = float(r[1])
        dif = round(val - val_anterior, 2) if val_anterior is not None else 0.0
        pct = round((dif / val_anterior) * 100.0, 1) if (val_anterior and val_anterior > 0) else 0.0
        val_anterior = val

        historico.append({
            "id": r[0],
            "valor_estimado": val,
            "data_avaliacao": str(r[2]),
            "observacoes": r[3] or "",
            "created_at": str(r[4]),
            "variacao": dif,
            "variacao_pct": pct
        })
    return historico


def obter_resumo_patrimonial(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Consolida a visão patrimonial analítica e transparente:
    1. ATIVOS:
       - Bens Físicos Ativos (Veículos, Imóveis, Equipamentos, etc.)
       - Caixa & Saldos Bancários Reais (sem contar cofrinhos em duplicidade)
       - Reservas e Cofrinhos (detalhamento informativo; já contidos no saldo da conta-pai)
    2. PASSIVOS (sem qualquer sobreposição ou dupla contagem):
       - Dívidas & Acordos Formais (dividas_gerenciamento)
       - Obrigações de Cartões de Crédito (faturas/compras pendentes em transações)
       - Obrigações do Paga Leve (parcelas pendentes em transações)
       - Outros Parcelamentos Futuros (transações pendentes)
    3. PATRIMÔNIO LÍQUIDO = Total de Ativos (-) Total de Passivos
    """
    import saldo_service
    
    inicializar_tabelas_patrimonio(conn)
    cur = conn.cursor()

    # 1. ATIVOS: BENS FÍSICOS
    bens_ativos = listar_bens(conn, incluir_arquivados=False)
    total_bens = sum(b["valor_atual_estimado"] for b in bens_ativos)

    por_tipo = {}
    for b in bens_ativos:
        t = b["tipo"]
        por_tipo[t] = por_tipo.get(t, 0.0) + b["valor_atual_estimado"]

    por_proprietario = {}
    for b in bens_ativos:
        p = b["proprietario"]
        por_proprietario[p] = por_proprietario.get(p, 0.0) + b["valor_atual_estimado"]

    # 2. ATIVOS: SALDOS BANCÁRIOS & CAIXA CONSOLIDADO
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    saldo_caixa = float(res_saldo.get("saldo_consolidado", 0.0))
    contas_ativas = [
        {
            "id": c.get("conta_id") or c.get("id"),
            "nome": c.get("conta_nome") or c.get("nome"),
            "saldo": float(c.get("saldo_atual", 0.0)),
            "icone": c.get("icone", "🏦"),
            "cor": c.get("cor", "#009ee3")
        }
        for c in res_saldo.get("contas", [])
        if c.get("tipo") != "cofrinho"
    ]

    # Cofrinhos (detalhe informativo sem somar ao saldo_caixa para evitar duplicidade)
    cur.execute("SELECT id, nome, saldo_confirmado, meta_valor, objetivo FROM cofrinhos")
    cofrinhos_reserva = [
        {
            "id": r[0],
            "nome": r[1],
            "saldo": float(r[2] or 0.0),
            "meta": float(r[3] or 0.0),
            "objetivo": r[4] or ""
        }
        for r in cur.fetchall()
    ]
    total_reservas_cofrinhos = sum(c["saldo"] for c in cofrinhos_reserva)

    total_ativos = round(total_bens + saldo_caixa, 2)

    # 3. PASSIVOS COM GARANTIA ANTI-DUPLICIDADE
    # A. Nomes dos cartões cadastrados
    cur.execute("SELECT id, nome FROM cartoes")
    cartoes_nomes = [r[1] for r in cur.fetchall()]

    # B. Obrigações de Cartões de Crédito (transações pendentes)
    ids_processados = set()
    transacoes_cartao = []
    total_cartao = 0.0
    if cartoes_nomes:
        placeholders = ",".join("?" for _ in cartoes_nomes)
        cur.execute(f"""
            SELECT id, descricao, valor, data, conta
            FROM transacoes
            WHERE conta IN ({placeholders}) AND (pago = 0 OR pago IS NULL)
            ORDER BY data ASC
        """, cartoes_nomes)
        for r in cur.fetchall():
            ids_processados.add(r[0])
            val = float(r[2])
            total_cartao += val
            transacoes_cartao.append({
                "id": r[0],
                "descricao": r[1],
                "valor": val,
                "data": str(r[3]),
                "cartao": r[4]
            })

    # C. Obrigações do Paga Leve (transações pendentes - dedup com cartões)
    transacoes_pagaleve = []
    total_pagaleve = 0.0
    cur.execute("""
        SELECT id, descricao, valor, data, grupo_parcelamento
        FROM transacoes
        WHERE grupo_parcelamento LIKE 'pagaleve_%' AND (pago = 0 OR pago IS NULL)
        ORDER BY data ASC
    """)
    for r in cur.fetchall():
        if r[0] not in ids_processados:
            ids_processados.add(r[0])
            val = float(r[2])
            total_pagaleve += val
            transacoes_pagaleve.append({
                "id": r[0],
                "descricao": r[1],
                "valor": val,
                "data": str(r[3]),
                "grupo": r[4]
            })

    # D. Outros Parcelamentos & Financiamentos Legítimos (fora de Cartões e Paga Leve)
    # REGRA PATRIMONIAL DO OIKOS: Contas de consumo e despesas operacionais cotidianas
    # (água, luz, telefonia, internet, assinaturas e mensalidades de consumo),
    # mesmo que cadastradas com antecedência para compor o fluxo de caixa ou pendentes/atrasadas,
    # pertencem ao orçamento mensal e contas a pagar, NÃO sendo passivos patrimoniais.
    # Apenas compras parceladas legítimas de bens duráveis (carnês/crediários) ou financiamentos
    # contraídos são considerados passivos patrimoniais.
    transacoes_outros_parc = []
    total_outros_parc = 0.0

    CATEGORIAS_CONSUMO_COTIDIANO = {
        "moradia/contas", "habitação", "habitacao", "energia", "água", "agua",
        "telefonia", "internet", "combustível", "combustivel", "transporte",
        "alimentação", "alimentacao", "saúde", "saude", "academia / wellhub",
        "barbearia", "educação", "educacao", "pessoal", "pessoal - carlos",
        "pessoal - fernanda", "impostos veículo", "impostos veiculo", "geral"
    }

    cur.execute("""
        SELECT id, descricao, valor, data, categoria, subcategoria, conta, grupo_parcelamento, numero_parcela, total_parcelas_compra
        FROM transacoes
        WHERE grupo_parcelamento IS NOT NULL
          AND grupo_parcelamento != ''
          AND NOT grupo_parcelamento LIKE 'pagaleve_%'
          AND NOT grupo_parcelamento LIKE 'fixa_%'
          AND NOT grupo_parcelamento LIKE 'recorren%'
          AND (pago = 0 OR pago IS NULL)
          AND tipo = 'despesa'
        ORDER BY data ASC
    """)
    for r in cur.fetchall():
        tid = r[0]
        if tid in ids_processados:
            continue
        
        cat = str(r[4] or "").strip().lower()
        tot_p = r[9]

        # Exclui despesas de consumo cotidiano e contas orçamentárias
        if cat in CATEGORIAS_CONSUMO_COTIDIANO:
            continue

        # Inclui apenas compras parceladas legítimas ou financiamentos
        eh_divida_financiamento = any(k in cat for k in ["empréstimo", "emprestimo", "financiamento", "dívida", "divida"])
        eh_compra_parcelada = bool(tot_p and tot_p > 1)

        if eh_divida_financiamento or eh_compra_parcelada:
            ids_processados.add(tid)
            val = float(r[2] or 0.0)
            total_outros_parc += val
            transacoes_outros_parc.append({
                "id": tid,
                "descricao": r[1],
                "valor": val,
                "data": str(r[3]),
                "grupo": r[7]
            })

    # E. Dívidas & Acordos Formais cadastrados (dividas_gerenciamento)
    cur.execute("""
        SELECT id, credor, descricao, saldo_atual, valor_original, bem_id, status
        FROM dividas_gerenciamento
        WHERE status = 'ativa'
    """)
    dividas_formais = []
    total_dividas_formais = 0.0
    for rd in cur.fetchall():
        s_atual = float(rd[3] or 0.0)
        total_dividas_formais += s_atual
        dividas_formais.append({
            "id": rd[0],
            "credor": rd[1],
            "descricao": rd[2],
            "saldo_atual": s_atual,
            "valor_original": float(rd[4] or 0.0),
            "bem_id": rd[5]
        })

    # Total de Passivos Consolidado (sem sobreposições)
    total_passivos = round(total_dividas_formais + total_cartao + total_pagaleve + total_outros_parc, 2)

    # 4. PATRIMÔNIO LÍQUIDO CONSOLIDADO
    patrimonio_liquido = round(total_ativos - total_passivos, 2)

    # 4.1 RESUMO COMPACTO DE CARTÕES E PAGA LEVE (SEM LISTAR ITENS SOLTOS NA TELA INICIAL)
    cartoes_resumo_dict = {}
    for t in transacoes_cartao:
        c_nome = t["cartao"] or "Cartão Geral"
        if c_nome not in cartoes_resumo_dict:
            cartoes_resumo_dict[c_nome] = {"nome": c_nome, "total": 0.0, "qtd_obrigacoes": 0}
        cartoes_resumo_dict[c_nome]["total"] += t["valor"]
        cartoes_resumo_dict[c_nome]["qtd_obrigacoes"] += 1

    cartoes_resumo = [
        {
            "nome": k,
            "total": round(v["total"], 2),
            "qtd_obrigacoes": v["qtd_obrigacoes"]
        }
        for k, v in cartoes_resumo_dict.items()
    ]
    cartoes_resumo.sort(key=lambda x: x["total"], reverse=True)

    pagaleve_resumo = {
        "total": round(total_pagaleve, 2),
        "qtd_parcelas": len(transacoes_pagaleve)
    }

    # 4.2 CÁLCULO DAS FATIAS PARA OS GRÁFICOS DE ROSCA (DONUT CHARTS SVG)
    import math
    raio_donut = 50
    circunf_donut = 2 * math.pi * raio_donut  # ~314.159

    # Fatias Ativos (Bens vs Caixa/Contas) - Cofrinhos NÃO geram fatia separada (evita duplicidade)
    fatias_ativos = []
    offset_ativos = 0.0
    if total_ativos > 0:
        if total_bens > 0:
            pct_b = round((total_bens / total_ativos) * 100, 1)
            dash_len_b = (pct_b / 100.0) * circunf_donut
            fatias_ativos.append({
                "label": "Bens Físicos",
                "icone": "🚗",
                "valor": round(total_bens, 2),
                "pct": pct_b,
                "cor": "#3b82f6",  # blue-500
                "dasharray": f"{dash_len_b:.2f} {circunf_donut - dash_len_b:.2f}",
                "dashoffset": f"{-offset_ativos:.2f}"
            })
            offset_ativos += dash_len_b
        
        if saldo_caixa > 0:
            pct_c = round((saldo_caixa / total_ativos) * 100, 1)
            dash_len_c = (pct_c / 100.0) * circunf_donut
            fatias_ativos.append({
                "label": "Caixa & Contas",
                "icone": "💵",
                "valor": round(saldo_caixa, 2),
                "pct": pct_c,
                "cor": "#10b981",  # emerald-500
                "dasharray": f"{dash_len_c:.2f} {circunf_donut - dash_len_c:.2f}",
                "dashoffset": f"{-offset_ativos:.2f}"
            })
            offset_ativos += dash_len_c

    # Fatias Passivos (Cartões, Paga Leve, Dívidas Formais, Outros) - apenas se valor > 0
    fatias_passivos = []
    offset_passivos = 0.0
    if total_passivos > 0:
        if total_cartao > 0:
            pct_ct = round((total_cartao / total_passivos) * 100, 1)
            dash_len_ct = (pct_ct / 100.0) * circunf_donut
            fatias_passivos.append({
                "label": "Cartões de Crédito",
                "icone": "💳",
                "valor": round(total_cartao, 2),
                "pct": pct_ct,
                "cor": "#ef4444",  # rose-500
                "dasharray": f"{dash_len_ct:.2f} {circunf_donut - dash_len_ct:.2f}",
                "dashoffset": f"{-offset_passivos:.2f}"
            })
            offset_passivos += dash_len_ct

        if total_pagaleve > 0:
            pct_pl = round((total_pagaleve / total_passivos) * 100, 1)
            dash_len_pl = (pct_pl / 100.0) * circunf_donut
            fatias_passivos.append({
                "label": "Paga Leve",
                "icone": "⚡",
                "valor": round(total_pagaleve, 2),
                "pct": pct_pl,
                "cor": "#f59e0b",  # amber-500
                "dasharray": f"{dash_len_pl:.2f} {circunf_donut - dash_len_pl:.2f}",
                "dashoffset": f"{-offset_passivos:.2f}"
            })
            offset_passivos += dash_len_pl

        if total_outros_parc > 0:
            pct_op = round((total_outros_parc / total_passivos) * 100, 1)
            dash_len_op = (pct_op / 100.0) * circunf_donut
            fatias_passivos.append({
                "label": "Outros Parcelamentos",
                "icone": "📋",
                "valor": round(total_outros_parc, 2),
                "pct": pct_op,
                "cor": "#8b5cf6",  # purple-500
                "dasharray": f"{dash_len_op:.2f} {circunf_donut - dash_len_op:.2f}",
                "dashoffset": f"{-offset_passivos:.2f}"
            })
            offset_passivos += dash_len_op

        if total_dividas_formais > 0:
            pct_df = round((total_dividas_formais / total_passivos) * 100, 1)
            dash_len_df = (pct_df / 100.0) * circunf_donut
            fatias_passivos.append({
                "label": "Dívidas Formais",
                "icone": "📁",
                "valor": round(total_dividas_formais, 2),
                "pct": pct_df,
                "cor": "#ec4899",  # pink-500
                "dasharray": f"{dash_len_df:.2f} {circunf_donut - dash_len_df:.2f}",
                "dashoffset": f"{-offset_passivos:.2f}"
            })
            offset_passivos += dash_len_df

    # 5. DADOS DO VEÍCULO DRIVE (SE CADASTRADO)
    veiculo_drive = next((b for b in bens_ativos if b["is_veiculo_drive"]), None)
    metricas_veiculo_drive = None
    if veiculo_drive:
        cur.execute("SELECT COALESCE(SUM(km), 0) FROM turnos")
        km_tot = float(cur.fetchone()[0] or 0.0)
        
        cur.execute("SELECT COALESCE(SUM(valor_pago), 0), COALESCE(SUM(litros), 0) FROM veiculo_abastecimentos")
        row_ab = cur.fetchone()
        comb_tot = float(row_ab[0] or 0.0)
        litros_tot = float(row_ab[1] or 0.0)

        cur.execute("SELECT COALESCE(SUM(valor), 0), COUNT(*) FROM despesas_veiculo")
        row_man = cur.fetchone()
        manut_tot = float(row_man[0] or 0.0)
        qtd_manut = int(row_man[1] or 0)

        metricas_veiculo_drive = {
            "bem_id": veiculo_drive["id"],
            "nome": veiculo_drive["nome"],
            "valor_estimado": veiculo_drive["valor_atual_estimado"],
            "km_total_rodado": km_tot,
            "total_gasto_combustivel": comb_tot,
            "total_litros_abastecidos": litros_tot,
            "total_gasto_manutencao": manut_tot,
            "qtd_manutencoes": qtd_manut
        }

    return {
        # Totais Principais
        "total_ativos": total_ativos,
        "total_passivos": total_passivos,
        "patrimonio_liquido": patrimonio_liquido,
        # Composição Ativos
        "total_bens": round(total_bens, 2),
        "total_bens_count": len(bens_ativos),
        "qtd_bens": len(bens_ativos),
        "saldo_caixa": round(saldo_caixa, 2),
        "contas_ativas": contas_ativas,
        "cofrinhos_reserva": cofrinhos_reserva,
        "total_reservas_cofrinhos": round(total_reservas_cofrinhos, 2),
        "por_tipo": por_tipo,
        "por_proprietario": por_proprietario,
        "bens": bens_ativos,
        "investimentos": [],  # Espaço preparado para produtos futuros
        "fatias_ativos": fatias_ativos,
        # Composição Passivos
        "total_dividas_formais": round(total_dividas_formais, 2),
        "dividas_formais": dividas_formais,
        "total_cartao": round(total_cartao, 2),
        "transacoes_cartao": transacoes_cartao,
        "cartoes_resumo": cartoes_resumo,
        "total_pagaleve": round(total_pagaleve, 2),
        "transacoes_pagaleve": transacoes_pagaleve,
        "pagaleve_resumo": pagaleve_resumo,
        "total_outros_parc": round(total_outros_parc, 2),
        "transacoes_outros_parc": transacoes_outros_parc,
        "fatias_passivos": fatias_passivos,
        # Veículo Drive
        "veiculo_drive": veiculo_drive,
        "metricas_veiculo_drive": metricas_veiculo_drive
    }

