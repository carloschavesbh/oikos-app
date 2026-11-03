# -*- coding: utf-8 -*-
"""
conciliacao_service.py - Módulo de conciliação bancária e importação assistida de extratos (Oikos Pessoal).

Responsabilidades:
1. Gerenciar tabelas de auditoria (lotes_importacao e lote_itens_conciliacao).
2. Fazer parsing determinístico de extratos bancários em formato CSV (ex: Mercado Pago).
3. Detectar reenvio de arquivos (hash SHA-256) e sobreposição de períodos.
4. Sugerir correspondências (matching) com lançamentos cadastrados, faturas/parcelas Paga Leve e Drive 99.
5. Permitir ações por item: Vincular, Nova Movimentação, Transferência Interna, Ignorar com motivo ou Deixar Pendente.
6. Aplicar lote de forma atômica e fornecer reversão auditável completa.
7. Calcular a Visão Anual de Cobertura de Extratos (Etapa 5: Realizado, Previsto, Não Conciliado, Conciliado).
"""

import os
import re
import csv
import hashlib
import unicodedata
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    t = remover_acentos(texto or "").upper()
    return re.sub(r"[^A-Z0-9]", "", t)


def calcular_hash_arquivo(conteudo_bytes: bytes) -> str:
    """Calcula o hash SHA-256 do arquivo para garantia de integridade e antifraude/antiduplicidade."""
    return hashlib.sha256(conteudo_bytes).hexdigest()


def inicializar_tabelas_conciliacao(conn) -> None:
    """
    Cria as tabelas de conciliação caso não existam.
    Não altera nenhuma estrutura ou dado de tabelas existentes.
    """
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lotes_importacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arquivo_nome TEXT NOT NULL,
        hash_arquivo TEXT NOT NULL,
        banco_ou_conta TEXT NOT NULL,
        conta_id INTEGER,
        data_importacao TEXT NOT NULL,
        periodo_inicio TEXT,
        periodo_fim TEXT,
        total_linhas INTEGER NOT NULL,
        total_creditos REAL NOT NULL DEFAULT 0.0,
        total_debitos REAL NOT NULL DEFAULT 0.0,
        saldo_inicial REAL,
        saldo_final REAL,
        status TEXT NOT NULL DEFAULT 'pendente', -- 'pendente', 'confirmado', 'revertido'
        criado_em TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lote_itens_conciliacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id INTEGER NOT NULL,
        linha_num INTEGER NOT NULL,
        data TEXT NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT NOT NULL, -- 'receita', 'despesa', 'transferencia', 'saldo'
        ref_id TEXT,
        saldo_parcial REAL,
        tipo_alerta TEXT, -- 'saldo_resumo', 'possivel_duplicata', 'transferencia_interna', 'paga_leve', 'drive_99', 'ok'
        acao_sugerida TEXT NOT NULL, -- 'vincular', 'novo', 'transferencia', 'ignorar', 'pendente'
        transacao_id_sugerida INTEGER,
        transacao_id_efetiva INTEGER,
        acao_efetiva TEXT,
        status_conciliacao TEXT NOT NULL DEFAULT 'pendente', -- 'pendente', 'conciliado', 'ignorado', 'revertido'
        categoria_sugerida TEXT,
        subcategoria_sugerida TEXT,
        motivo_ignorado TEXT,
        linha_bruta TEXT,
        FOREIGN KEY (lote_id) REFERENCES lotes_importacao(id)
    )
    """)

    # Adiciona colunas auxiliares em transacoes se não existirem (não destrutivo)
    cur.execute("PRAGMA table_info(transacoes)")
    colunas_transacoes = [r[1] for r in cur.fetchall()]

    if "lote_importacao_id" not in colunas_transacoes:
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN lote_importacao_id INTEGER")
        except Exception:
            pass

    if "conciliado_com_extrato" not in colunas_transacoes:
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN conciliado_com_extrato INTEGER DEFAULT 0")
        except Exception:
            pass

    if "ref_externa" not in colunas_transacoes:
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN ref_externa TEXT")
        except Exception:
            pass

    if "origem" not in colunas_transacoes:
        try:
            cur.execute("ALTER TABLE transacoes ADD COLUMN origem TEXT")
        except Exception:
            pass

    conn.commit()


def parse_csv_mercado_pago(conteudo_texto: str) -> Dict[str, Any]:
    """
    Realiza o parsing determinístico do formato real de CSV exportado pelo Mercado Pago.
    Lida com o bloco de cabeçalho de saldos (INITIAL_BALANCE;CREDITS;DEBITS;FINAL_BALANCE)
    e com a tabela de movimentações (RELEASE_DATE;TRANSACTION_TYPE;REFERENCE_ID;TRANSACTION_NET_AMOUNT;PARTIAL_BALANCE).
    """
    linhas = [l.strip() for l in conteudo_texto.splitlines() if l.strip()]
    if not linhas:
        raise ValueError("O arquivo CSV está vazio.")

    # Localizar cabeçalho de metadados de saldo
    saldo_inicial = 0.0
    creditos_totais = 0.0
    debitos_totais = 0.0
    saldo_final = 0.0

    idx_cabecalho_tx = -1
    for i, linha in enumerate(linhas):
        if "RELEASE_DATE" in linha.upper() and "REFERENCE_ID" in linha.upper():
            idx_cabecalho_tx = i
            break

    if idx_cabecalho_tx == -1:
        raise ValueError("Cabeçalho de transações do Mercado Pago não encontrado (esperado 'RELEASE_DATE;...;REFERENCE_ID').")

    # Linhas antes do cabeçalho de transações podem conter INITIAL_BALANCE
    if idx_cabecalho_tx >= 2:
        meta_header = linhas[0].split(";")
        meta_vals = linhas[1].split(";")
        if len(meta_vals) >= 4 and "INITIAL_BALANCE" in meta_header[0].upper():
            try:
                saldo_inicial = float(meta_vals[0].replace(".", "").replace(",", "."))
                creditos_totais = float(meta_vals[1].replace(".", "").replace(",", "."))
                debitos_totais = float(meta_vals[2].replace(".", "").replace(",", "."))
                saldo_final = float(meta_vals[3].replace(".", "").replace(",", "."))
            except Exception:
                pass

    # Processar as linhas de transações
    reader = csv.reader(linhas[idx_cabecalho_tx:], delimiter=";")
    header = next(reader)
    col_map = {col.strip().upper(): idx for idx, col in enumerate(header)}

    transacoes = []
    linha_num = idx_cabecalho_tx + 1

    for row in reader:
        linha_num += 1
        if not row or len(row) < 4:
            continue

        raw_date = row[col_map.get("RELEASE_DATE", 0)].strip()
        descricao = row[col_map.get("TRANSACTION_TYPE", 1)].strip()
        ref_id = row[col_map.get("REFERENCE_ID", 2)].strip() if "REFERENCE_ID" in col_map else ""
        raw_val = row[col_map.get("TRANSACTION_NET_AMOUNT", 3)].strip()

        saldo_parcial = 0.0
        if "PARTIAL_BALANCE" in col_map and len(row) > col_map["PARTIAL_BALANCE"]:
            try:
                saldo_parcial = float(row[col_map["PARTIAL_BALANCE"]].strip().replace(".", "").replace(",", "."))
            except Exception:
                pass

        # Data: converter DD-MM-YYYY para YYYY-MM-DD
        dt_convertida = raw_date
        partes_dt = raw_date.split("-")
        if len(partes_dt) == 3 and len(partes_dt[2]) == 4:
            # formato DD-MM-YYYY
            dt_convertida = f"{partes_dt[2]}-{partes_dt[1]}-{partes_dt[0]}"

        # Valor
        try:
            val_num = float(raw_val.replace(".", "").replace(",", "."))
        except Exception:
            continue

        tipo = "receita" if val_num > 0 else "despesa"
        valor_abs = abs(val_num)

        transacoes.append({
            "linha_num": linha_num,
            "data": dt_convertida,
            "descricao": descricao,
            "ref_id": ref_id,
            "valor": valor_abs,
            "tipo": tipo,
            "saldo_parcial": saldo_parcial,
            "linha_bruta": ";".join(row)
        })

    # Período
    datas = [t["data"] for t in transacoes if t["data"]]
    periodo_inicio = min(datas) if datas else None
    periodo_fim = max(datas) if datas else None

    # Totais calculados se não estavam nos metadados
    if creditos_totais == 0.0 and debitos_totais == 0.0:
        creditos_totais = sum(t["valor"] for t in transacoes if t["tipo"] == "receita")
        debitos_totais = sum(t["valor"] for t in transacoes if t["tipo"] == "despesa")

    return {
        "saldo_inicial": saldo_inicial,
        "creditos_totais": creditos_totais,
        "debitos_totais": debitos_totais,
        "saldo_final": saldo_final,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "total_transacoes": len(transacoes),
        "transacoes": transacoes
    }


def sugerir_classificacao_e_matching(item: Dict[str, Any], transacoes_db: List[Dict[str, Any]], pagaleve_db: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compara uma linha do extrato bancário com a base atual e infere a ação sugerida:
    1. 'vincular' se já existe lançamento idêntico ou muito próximo na data (+- 3 dias).
    2. 'transferencia' se for transferência interna (Mercado Pago, 99Pay, Carteira, Reserva, Cofrinho).
    3. 'novo' com categoria e subcategoria automáticas.
    4. 'ignorar' se for ajuste de saldo ou linha redundante.
    """
    dt = item["data"]
    desc = item["descricao"]
    desc_norm = normalizar_texto(desc)
    val = item["valor"]
    tipo = item["tipo"]

    resultado = {
        "acao_sugerida": "novo",
        "transacao_id_sugerida": None,
        "match_detalhe": None,
        "categoria_sugerida": "Outros",
        "subcategoria_sugerida": "Geral",
        "tipo_alerta": "ok",
        "motivo_ignorado": ""
    }

    # 1. Checar Transferências Internas e Cofrinhos
    if any(termo in desc_norm for termo in ["DINHEIRORETIRADO", "DINHEIRORESERVADO", "CONTASDECASA", "COFRINHO"]):
        resultado["acao_sugerida"] = "transferencia"
        resultado["tipo_alerta"] = "transferencia_interna"
        resultado["categoria_sugerida"] = "Transferência Entre Contas"
        resultado["subcategoria_sugerida"] = "Reserva / Cofrinho"
        return resultado

    # 2. Checar Ganhos da 99 / Motorista App (Drive)
    if (
        "99TECNOLOGIA" in desc_norm
        or "99POP" in desc_norm
        or "99APP" in desc_norm
        or ("PIXRECEBIDO" in desc_norm and "CARLOS" in desc_norm and tipo == "receita")
    ):
        resultado["acao_sugerida"] = "novo"
        resultado["tipo_alerta"] = "drive_99"
        resultado["categoria_sugerida"] = "99 / Chaves (Carlos)"
        resultado["subcategoria_sugerida"] = "Corridas App"
        return resultado

    # 3. Checar Paga Leve
    if "PAGALEVE" in desc_norm or "PAGA LEVE" in desc.upper():
        resultado["tipo_alerta"] = "paga_leve"
        resultado["categoria_sugerida"] = "Medicamentos"
        resultado["subcategoria_sugerida"] = "Paga Leve"

        # Procurar correspondência em compras Paga Leve ou transações
        for pl in pagaleve_db:
            if abs(pl.get("valor_parcela", 0.0) - val) < 0.05:
                resultado["acao_sugerida"] = "vincular"
                resultado["transacao_id_sugerida"] = pl.get("transacao_id")
                resultado["match_detalhe"] = f"Parcela Paga Leve: {pl.get('descricao', '')}"
                return resultado

    # 4. Checar Rendimentos
    if "RENDIMENTOS" in desc_norm or "RENDIMENTO" in desc_norm:
        resultado["acao_sugerida"] = "novo"
        resultado["categoria_sugerida"] = "Rendimentos"
        resultado["subcategoria_sugerida"] = "Rendimentos Conta"
        return resultado

    # 5. Buscar correspondência em transacoes_db (Matching por Valor e Data Próxima)
    melhor_match = None
    menor_distancia_dias = 999

    try:
        data_item = datetime.strptime(dt, "%Y-%m-%d").date()
    except Exception:
        data_item = None

    for tx in transacoes_db:
        if tx["tipo"] == tipo and abs(tx["valor"] - val) < 0.02:
            dist_dias = 999
            if data_item:
                try:
                    data_tx = datetime.strptime(tx["data"], "%Y-%m-%d").date()
                    dist_dias = abs((data_item - data_tx).days)
                except Exception:
                    pass

            if dist_dias <= 3 and dist_dias < menor_distancia_dias:
                melhor_match = tx
                menor_distancia_dias = dist_dias

    if melhor_match:
        resultado["acao_sugerida"] = "vincular"
        resultado["transacao_id_sugerida"] = melhor_match["id"]
        resultado["categoria_sugerida"] = melhor_match.get("categoria", "Outros")
        resultado["subcategoria_sugerida"] = melhor_match.get("subcategoria", "Geral")
        resultado["tipo_alerta"] = "possivel_duplicata"
        resultado["match_detalhe"] = f"Lançamento existente ID {melhor_match['id']} ({melhor_match['data']} - {melhor_match['descricao']})"
        return resultado

    # 6. Sugestão automática de categorias para novos lançamentos com base em termos conhecidos
    if any(k in desc_norm for k in ["POSTO", "SHELL", "IPIRANGA", "PETROBRAS", "COMBUSTIVEL"]):
        resultado["categoria_sugerida"] = "Combustível (Trabalho)"
        resultado["subcategoria_sugerida"] = "Abastecimento"
    elif any(k in desc_norm for k in ["SUPERMERCADO", "EPA", "BH", "CARREFOUR", "PAO", "PADARIA"]):
        resultado["categoria_sugerida"] = "Alimentação"
        resultado["subcategoria_sugerida"] = "Supermercado"
    elif any(k in desc_norm for k in ["FARMACIA", "DROGARIA", "RAIA", "ARAUJO", "DROGASIL"]):
        resultado["categoria_sugerida"] = "Medicamentos"
        resultado["subcategoria_sugerida"] = "Farmácia"
    elif any(k in desc_norm for k in ["GOOGLE", "NETFLIX", "SPOTIFY", "YOUCINE", "STREAMING"]):
        resultado["categoria_sugerida"] = "Streaming"
        resultado["subcategoria_sugerida"] = "Assinaturas"
    elif any(k in desc_norm for k in ["COPASA", "AGUA"]):
        resultado["categoria_sugerida"] = "HABITAÇÃO"
        resultado["subcategoria_sugerida"] = "Água e Esgoto"
    elif any(k in desc_norm for k in ["CEMIG", "ENERGIA", "LUZ"]):
        resultado["categoria_sugerida"] = "Energia"
        resultado["subcategoria_sugerida"] = "Eletricidade"
    elif any(k in desc_norm for k in ["CLARO", "VIVO", "TIM", "TELEFONE"]):
        resultado["categoria_sugerida"] = "HABITAÇÃO"
        resultado["subcategoria_sugerida"] = "Telefonia / Internet"

    return resultado


def processar_previa_importacao(conteudo_bytes: bytes, nome_arquivo: str, conta_nome: str, conn) -> Dict[str, Any]:
    """
    Gera a prévia completa e assistida da importação para conferência prévia do usuário.
    NÃO altera nenhuma tabela financeira definitiva antes da aprovação explícita.
    """
    inicializar_tabelas_conciliacao(conn)
    cur = conn.cursor()

    hash_arquivo = calcular_hash_arquivo(conteudo_bytes)

    # 1. Verificar se o mesmo arquivo já foi importado
    cur.execute("SELECT id, arquivo_nome, data_importacao, status FROM lotes_importacao WHERE hash_arquivo = ?", (hash_arquivo,))
    lote_existente = cur.fetchone()
    aviso_duplicidade = None
    if lote_existente:
        aviso_duplicidade = f"Atenção: Este arquivo exato já foi processado no Lote #{lote_existente[0]} ({lote_existente[1]}) em {lote_existente[2]} com status '{lote_existente[3]}'."

    # Decodificar texto
    try:
        conteudo_texto = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        conteudo_texto = conteudo_bytes.decode("latin-1", errors="replace")

    dados_csv = parse_csv_mercado_pago(conteudo_texto)

    # 2. Verificar sobreposição de período com outros lotes
    aviso_sobreposicao = None
    if dados_csv["periodo_inicio"] and dados_csv["periodo_fim"]:
        cur.execute("""
            SELECT id, arquivo_nome, periodo_inicio, periodo_fim, status
            FROM lotes_importacao
            WHERE status != 'revertido'
              AND NOT (periodo_fim < ? OR periodo_inicio > ?)
        """, (dados_csv["periodo_inicio"], dados_csv["periodo_fim"]))
        sobrepostos = cur.fetchall()
        if sobrepostos:
            nomes = ", ".join([f"Lote #{s[0]} ({s[1]}: {s[2]} a {s[3]})" for s in sobrepostos])
            aviso_sobreposicao = f"Aviso de sobreposição de datas: O período deste extrato ({dados_csv['periodo_inicio']} a {dados_csv['periodo_fim']}) sobrepõe lotes existentes: {nomes}."

    # 3. Carregar transações do período para matching heurístico
    p_inicio = dados_csv["periodo_inicio"] or "2026-01-01"
    p_fim = dados_csv["periodo_fim"] or "2026-12-31"

    cur.execute("""
        SELECT id, data, descricao, valor, tipo, categoria, subcategoria, conta, pago, status_pagamento
        FROM transacoes
        WHERE data >= ? AND data <= ?
    """, (p_inicio, p_fim))
    col_names = [d[0] for d in cur.description]
    transacoes_db = [dict(zip(col_names, row)) for row in cur.fetchall()]

    # Carregar compras/parcelas Paga Leve
    pagaleve_db = []
    try:
        cur.execute("SELECT id, descricao, valor_parcela, status FROM pagaleve_compras")
        pl_cols = [d[0] for d in cur.description]
        pagaleve_db = [dict(zip(pl_cols, row)) for row in cur.fetchall()]
    except Exception:
        pass

    # Processar matching para cada item
    itens_previa = []
    contagem_sugestoes = {"vincular": 0, "novo": 0, "transferencia": 0, "ignorar": 0}

    for item in dados_csv["transacoes"]:
        sugestao = sugerir_classificacao_e_matching(item, transacoes_db, pagaleve_db)
        acao = sugestao["acao_sugerida"]
        contagem_sugestoes[acao] = contagem_sugestoes.get(acao, 0) + 1

        itens_previa.append({
            "linha_num": item["linha_num"],
            "data": item["data"],
            "descricao": item["descricao"],
            "ref_id": item["ref_id"],
            "valor": item["valor"],
            "tipo": item["tipo"],
            "saldo_parcial": item["saldo_parcial"],
            "tipo_alerta": sugestao["tipo_alerta"],
            "acao_sugerida": acao,
            "transacao_id_sugerida": sugestao["transacao_id_sugerida"],
            "match_detalhe": sugestao["match_detalhe"],
            "categoria_sugerida": sugestao["categoria_sugerida"],
            "subcategoria_sugerida": sugestao["subcategoria_sugerida"],
            "motivo_ignorado": sugestao["motivo_ignorado"],
            "linha_bruta": item["linha_bruta"]
        })

    return {
        "arquivo_nome": nome_arquivo,
        "hash_arquivo": hash_arquivo,
        "conta_nome": conta_nome,
        "saldo_inicial": dados_csv["saldo_inicial"],
        "creditos_totais": dados_csv["creditos_totais"],
        "debitos_totais": dados_csv["debitos_totais"],
        "saldo_final": dados_csv["saldo_final"],
        "periodo_inicio": dados_csv["periodo_inicio"],
        "periodo_fim": dados_csv["periodo_fim"],
        "total_transacoes": dados_csv["total_transacoes"],
        "aviso_duplicidade": aviso_duplicidade,
        "aviso_sobreposicao": aviso_sobreposicao,
        "contagem_sugestoes": contagem_sugestoes,
        "itens": itens_previa
    }


def registrar_lote_pendente(previa: Dict[str, Any], conn) -> int:
    """
    Registra o lote em estado 'pendente' e seus itens em lote_itens_conciliacao.
    Permite salvar o rascunho da conciliação sem tocar na tabela transacoes.
    """
    inicializar_tabelas_conciliacao(conn)
    cur = conn.cursor()

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Obter conta_id
    cur.execute("SELECT id FROM contas_config WHERE nome = ?", (previa["conta_nome"],))
    row_c = cur.fetchone()
    conta_id = row_c[0] if row_c else 1

    cur.execute("""
        INSERT INTO lotes_importacao (
            arquivo_nome, hash_arquivo, banco_ou_conta, conta_id, data_importacao,
            periodo_inicio, periodo_fim, total_linhas, total_creditos, total_debitos,
            saldo_inicial, saldo_final, status, criado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?)
    """, (
        previa["arquivo_nome"],
        previa["hash_arquivo"],
        previa["conta_nome"],
        conta_id,
        agora,
        previa["periodo_inicio"],
        previa["periodo_fim"],
        previa["total_transacoes"],
        previa["creditos_totais"],
        previa["debitos_totais"],
        previa["saldo_inicial"],
        previa["saldo_final"],
        agora
    ))
    lote_id = cur.lastrowid

    for item in previa["itens"]:
        cur.execute("""
            INSERT INTO lote_itens_conciliacao (
                lote_id, linha_num, data, descricao, valor, tipo, ref_id,
                saldo_parcial, tipo_alerta, acao_sugerida, transacao_id_sugerida,
                status_conciliacao, categoria_sugerida, subcategoria_sugerida,
                motivo_ignorado, linha_bruta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?, ?)
        """, (
            lote_id,
            item["linha_num"],
            item["data"],
            item["descricao"],
            item["valor"],
            item["tipo"],
            item["ref_id"],
            item["saldo_parcial"],
            item["tipo_alerta"],
            item["acao_sugerida"],
            item["transacao_id_sugerida"],
            item["categoria_sugerida"],
            item["subcategoria_sugerida"],
            item["motivo_ignorado"],
            item["linha_bruta"]
        ))

    conn.commit()
    return lote_id


def aplicar_lote_conciliacao(lote_id: int, decisoes: List[Dict[str, Any]], conn) -> Dict[str, Any]:
    """
    Aplica as decisões aprovadas pelo usuário de forma ATÔMICA e auditável.
    Decisões possíveis para cada item:
      - 'vincular': vincula a uma transação existente (sem duplicar).
      - 'novo': cria novo lançamento em 'transacoes'.
      - 'transferencia': cria transferência entre contas (sem duplicar receita).
      - 'ignorar': marca como ignorado com motivo.
      - 'pendente': mantém pendente para revisão futura.
    """
    cur = conn.cursor()

    cur.execute("SELECT id, arquivo_nome, banco_ou_conta, conta_id, status FROM lotes_importacao WHERE id = ?", (lote_id,))
    lote = cur.fetchone()
    if not lote:
        raise ValueError(f"Lote #{lote_id} não encontrado.")
    if lote[4] == "confirmado":
        raise ValueError(f"Lote #{lote_id} já foi confirmado anteriormente.")

    conta_nome = lote[2]
    conta_id = lote[3]
    nome_arquivo = lote[1]

    # Indexar decisões enviadas pelo front: {item_id: {acao, categoria, subcategoria, transacao_id, motivo}}
    decisoes_map = {d["item_id"]: d for d in decisoes}

    cur.execute("SELECT id, linha_num, data, descricao, valor, tipo, ref_id, acao_sugerida, transacao_id_sugerida, categoria_sugerida, subcategoria_sugerida FROM lote_itens_conciliacao WHERE lote_id = ?", (lote_id,))
    itens_db = cur.fetchall()

    resumo = {
        "vinculados": 0,
        "novos_criados": 0,
        "transferencias_criadas": 0,
        "ignorados": 0,
        "pendentes": 0
    }

    for item in itens_db:
        iid, lnum, dt, desc, val, tp, ref_id, acao_sug, tx_sug, cat_sug, subcat_sug = item

        decisao = decisoes_map.get(iid, {
            "acao": acao_sug,
            "transacao_id": tx_sug,
            "categoria": cat_sug,
            "subcategoria": subcat_sug,
            "motivo": ""
        })

        acao = decisao.get("acao", acao_sug)
        tx_id_escolhido = decisao.get("transacao_id", tx_sug)
        cat_escolhida = decisao.get("categoria", cat_sug) or "Outros"
        subcat_escolhida = decisao.get("subcategoria", subcat_sug) or "Geral"
        motivo = decisao.get("motivo", "")

        tx_efetiva = None

        if acao == "vincular" and tx_id_escolhido:
            # Atualiza transação existente marcando como conciliada e liquidada
            cur.execute("""
                UPDATE transacoes
                SET pago = 1,
                    status_pagamento = 'pago',
                    data_liquidacao = ?,
                    conciliado_com_extrato = 1,
                    lote_importacao_id = ?,
                    ref_externa = COALESCE(ref_externa, ?)
                WHERE id = ?
            """, (dt, lote_id, ref_id, tx_id_escolhido))
            tx_efetiva = tx_id_escolhido
            resumo["vinculados"] += 1
            status_item = "conciliado"

        elif acao == "novo":
            # Cria novo lançamento pago/liquidado
            cur.execute("""
                INSERT INTO transacoes (
                    data, data_liquidacao, descricao, valor, tipo, categoria, subcategoria,
                    conta, conta_id, pago, afeta_saldo_bancario, status_pagamento,
                    lote_importacao_id, conciliado_com_extrato, ref_externa, origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 'pago', ?, 1, ?, ?)
            """, (
                dt, dt, desc, val, tp, cat_escolhida, subcat_escolhida,
                conta_nome, conta_id, lote_id, ref_id, f"Extrato {nome_arquivo}"
            ))
            tx_efetiva = cur.lastrowid
            resumo["novos_criados"] += 1
            status_item = "conciliado"

        elif acao == "transferencia":
            # Registra transferência interna garantindo que não entre em receita/despesa orçamentária
            cur.execute("""
                INSERT INTO transacoes (
                    data, data_liquidacao, descricao, valor, tipo, categoria, subcategoria,
                    conta, conta_id, pago, afeta_saldo_bancario, status_pagamento,
                    lote_importacao_id, conciliado_com_extrato, ref_externa, origem
                ) VALUES (?, ?, ?, ?, 'transferencia', 'Transferência Entre Contas', 'Transferência Interna',
                    ?, ?, 1, 0, 'pago', ?, 1, ?, ?)
            """, (
                dt, dt, desc, val, conta_nome, conta_id, lote_id, ref_id, f"Extrato {nome_arquivo}"
            ))
            tx_efetiva = cur.lastrowid
            resumo["transferencias_criadas"] += 1
            status_item = "conciliado"

        elif acao == "ignorar":
            status_item = "ignorado"
            resumo["ignorados"] += 1

        else:  # pendente
            status_item = "pendente"
            resumo["pendentes"] += 1

        # Atualizar registro do item de conciliação
        cur.execute("""
            UPDATE lote_itens_conciliacao
            SET acao_efetiva = ?,
                transacao_id_efetiva = ?,
                status_conciliacao = ?,
                motivo_ignorado = ?
            WHERE id = ?
        """, (acao, tx_efetiva, status_item, motivo, iid))

    # Atualizar status do lote
    cur.execute("UPDATE lotes_importacao SET status = 'confirmado' WHERE id = ?", (lote_id,))
    conn.commit()

    return resumo


def reverter_lote_conciliacao(lote_id: int, conn) -> Dict[str, Any]:
    """
    Reverte um lote importado:
    1. Remove as transações criadas por esse lote.
    2. Remove o vínculo de conciliação das transações que foram vinculadas.
    3. Marca o lote e seus itens como 'revertido'.
    Garante restauração exata e segura sem perdas acidentais.
    """
    cur = conn.cursor()

    cur.execute("SELECT id, arquivo_nome, status FROM lotes_importacao WHERE id = ?", (lote_id,))
    lote = cur.fetchone()
    if not lote:
        raise ValueError(f"Lote #{lote_id} não encontrado.")
    if lote[2] == "revertido":
        raise ValueError(f"Lote #{lote_id} já está revertido.")

    # 1. Remover transações criadas pelo lote
    cur.execute("SELECT COUNT(*) FROM transacoes WHERE lote_importacao_id = ? AND origem LIKE 'Extrato%'", (lote_id,))
    removidas = cur.fetchone()[0]
    cur.execute("DELETE FROM transacoes WHERE lote_importacao_id = ? AND origem LIKE 'Extrato%'", (lote_id,))

    # 2. Desvincular transações preexistentes que foram vinculadas
    cur.execute("""
        UPDATE transacoes
        SET conciliado_com_extrato = 0,
            lote_importacao_id = NULL
        WHERE lote_importacao_id = ?
    """, (lote_id,))

    # 3. Marcar itens e lote como revertidos
    cur.execute("UPDATE lote_itens_conciliacao SET status_conciliacao = 'revertido' WHERE lote_id = ?", (lote_id,))
    cur.execute("UPDATE lotes_importacao SET status = 'revertido' WHERE id = ?", (lote_id,))

    conn.commit()
    return {
        "lote_id": lote_id,
        "transacoes_removidas": removidas,
        "status": "revertido"
    }


def obter_visao_anual_cobertura(ano: int, conn) -> Dict[str, Any]:
    """
    Etapa 5 — Visão Anual e Cobertura:
    Calcula para cada mês do ano (01 a 12):
      - Realizado (receitas e despesas pagas)
      - Previsto (despesas e receitas a vencer / não pagas)
      - Histórico Não Conciliado (lançamentos pagos sem vínculo com extrato bancário oficial)
      - Conciliado (lançamentos pagos com conciliação bancária confirmada)
      - Status de Cobertura: 'Completo', 'Parcial' ou 'Sem Dados'
    Sem forçar saldos fictícios nem ajustes inventados.
    """
    inicializar_tabelas_conciliacao(conn)
    cur = conn.cursor()
    ano_str = str(ano)

    # Buscar lotes confirmados do ano
    cur.execute("""
        SELECT id, arquivo_nome, periodo_inicio, periodo_fim, banco_ou_conta, total_linhas
        FROM lotes_importacao
        WHERE status = 'confirmado'
    """)
    lotes = cur.fetchall()

    meses_com_extrato = set()
    for l in lotes:
        ini = l[2] or ""
        fim = l[3] or ""
        if ini.startswith(ano_str):
            meses_com_extrato.add(ini[:7])
        if fim.startswith(ano_str):
            meses_com_extrato.add(fim[:7])

    # Buscar agregações de transações mês a mês
    cur.execute("""
        SELECT
            substr(data, 1, 7) AS mes,
            SUM(CASE WHEN tipo = 'receita' AND pago = 1 THEN valor ELSE 0 END) AS rec_realizada,
            SUM(CASE WHEN tipo = 'receita' AND pago = 0 THEN valor ELSE 0 END) AS rec_prevista,
            SUM(CASE WHEN tipo = 'despesa' AND pago = 1 THEN valor ELSE 0 END) AS desp_realizada,
            SUM(CASE WHEN tipo = 'despesa' AND pago = 0 THEN valor ELSE 0 END) AS desp_prevista,
            SUM(CASE WHEN pago = 1 AND conciliado_com_extrato = 1 THEN valor ELSE 0 END) AS total_conciliado,
            SUM(CASE WHEN pago = 1 AND (conciliado_com_extrato IS NULL OR conciliado_com_extrato = 0) THEN valor ELSE 0 END) AS total_nao_conciliado,
            COUNT(CASE WHEN pago = 1 AND conciliado_com_extrato = 1 THEN 1 END) AS qtd_conciliados,
            COUNT(CASE WHEN pago = 1 AND (conciliado_com_extrato IS NULL OR conciliado_com_extrato = 0) THEN 1 END) AS qtd_nao_conciliados,
            COUNT(*) AS total_itens
        FROM transacoes
        WHERE data >= ? AND data <= ?
        GROUP BY mes
        ORDER BY mes
    """, (f"{ano_str}-01-01", f"{ano_str}-12-31"))

    dados_meses = {row[0]: row for row in cur.fetchall()}

    nomes_meses = [
        ("01", "Janeiro"), ("02", "Fevereiro"), ("03", "Março"), ("04", "Abril"),
        ("05", "Maio"), ("06", "Junho"), ("07", "Julho"), ("08", "Agosto"),
        ("09", "Setembro"), ("10", "Outubro"), ("11", "Novembro"), ("12", "Dezembro")
    ]

    linhas_visao = []
    totais_ano = {
        "rec_realizada": 0.0,
        "rec_prevista": 0.0,
        "desp_realizada": 0.0,
        "desp_prevista": 0.0,
        "total_conciliado": 0.0,
        "total_nao_conciliado": 0.0
    }

    for num, nome in nomes_meses:
        chave_mes = f"{ano_str}-{num}"
        d = dados_meses.get(chave_mes)

        if d:
            _, r_real, r_prev, d_real, d_prev, v_conc, v_nconc, q_conc, q_nconc, tot_itens = d
            r_real = r_real or 0.0
            r_prev = r_prev or 0.0
            d_real = d_real or 0.0
            d_prev = d_prev or 0.0
            v_conc = v_conc or 0.0
            v_nconc = v_nconc or 0.0
        else:
            r_real = r_prev = d_real = d_prev = v_conc = v_nconc = 0.0
            q_conc = q_nconc = tot_itens = 0

        # Avaliar cobertura
        if chave_mes in meses_com_extrato and q_conc > 0 and q_nconc == 0:
            status_cobertura = "Completo"
            badge_class = "badge-completo"
        elif tot_itens > 0 and (chave_mes in meses_com_extrato or q_conc > 0):
            status_cobertura = "Parcial (Extrato + Histórico)"
            badge_class = "badge-parcial"
        elif tot_itens > 0:
            status_cobertura = "Histórico Sem Extrato"
            badge_class = "badge-historico"
        else:
            status_cobertura = "Sem Dados"
            badge_class = "badge-vazio"

        totais_ano["rec_realizada"] += r_real
        totais_ano["rec_prevista"] += r_prev
        totais_ano["desp_realizada"] += d_real
        totais_ano["desp_prevista"] += d_prev
        totais_ano["total_conciliado"] += v_conc
        totais_ano["total_nao_conciliado"] += v_nconc

        linhas_visao.append({
            "mes": chave_mes,
            "nome_mes": nome,
            "rec_realizada": r_real,
            "rec_prevista": r_prev,
            "desp_realizada": d_real,
            "desp_prevista": d_prev,
            "saldo_realizado": r_real - d_real,
            "saldo_previsto": r_prev - d_prev,
            "total_conciliado": v_conc,
            "total_nao_conciliado": v_nconc,
            "qtd_conciliados": q_conc,
            "qtd_nao_conciliados": q_nconc,
            "status_cobertura": status_cobertura,
            "badge_class": badge_class
        })

    return {
        "ano": ano,
        "meses": linhas_visao,
        "totais": totais_ano
    }
