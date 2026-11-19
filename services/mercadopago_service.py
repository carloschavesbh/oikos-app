import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List

import database
import saldo_service

MP_USER_ID_FERNANDA = "2489313"
CONTA_MP_ID = 1
CONTA_MP_NOME = "Mercado Pago"

PALAVRAS_TRANSFERENCIA_INTERNA = (
    "carlos alberto",
    "chaves transportes",
    "99pay",
    "99 tecnologia",
    "cofrinho",
    "reserva",
)


def _eh_transferencia_interna(item: Dict[str, Any], descricao: str) -> bool:
    """Identifica transferências internas entre contas próprias (Carlos/Fernanda/99Pay/Cofrinhos)."""
    if (item.get("operation_type") or "") == "partition_transfer":
        return True

    poi = item.get("point_of_interaction") or {}
    tx_data = poi.get("transaction_data") or {}
    bank_info = tx_data.get("bank_info") or {}
    payer_info = bank_info.get("payer") or {}
    collector_info = bank_info.get("collector") or {}
    payer = item.get("payer") or {}

    textos = [
        descricao,
        item.get("description") or "",
        payer_info.get("long_name") or "",
        collector_info.get("account_holder_name") or "",
        f"{payer.get('first_name') or ''} {payer.get('last_name') or ''}",
    ]
    blob = " ".join(str(t).lower() for t in textos if t)
    return any(kw in blob for kw in PALAVRAS_TRANSFERENCIA_INTERNA)


def obter_saldo_real_mp() -> Any:
    """Consulta o saldo disponível na API do Mercado Pago. Retorna None se 403/404 ou indisponível."""
    token = os.getenv("MP_TOKEN_FERNANDA")
    if not token:
        return None
    url = f"https://api.mercadopago.com/users/{MP_USER_ID_FERNANDA}/mercadopago_account/balance"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Oikos-Sync/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            val = data.get("available_balance")
            if val is None:
                val = data.get("total_amount")
            return round(float(val), 2) if val is not None else None
    except Exception:
        return None


def _extrair_descricao_limpa(item: Dict[str, Any], eh_entrada: bool) -> str:
    """Extrai descrição amigável da movimentação do Mercado Pago."""
    desc = (item.get("description") or "").strip()
    if desc and desc.lower() not in ("pix", "transferência", "transferencia"):
        return desc[:120]

    poi = item.get("point_of_interaction") or {}
    tx_data = poi.get("transaction_data") or {}
    bank_info = tx_data.get("bank_info") or {}
    nome_parte = ""
    if eh_entrada:
        payer_info = bank_info.get("payer") or {}
        nome_parte = (payer_info.get("long_name") or "").strip()
        if not nome_parte:
            payer = item.get("payer") or {}
            first = (payer.get("first_name") or "").strip()
            last = (payer.get("last_name") or "").strip()
            nome_parte = f"{first} {last}".strip()
        base = "Pix Recebido MP" if item.get("payment_method_id") == "pix" else "Entrada Mercado Pago"
    else:
        collector_info = bank_info.get("collector") or {}
        nome_parte = (collector_info.get("account_holder_name") or "").strip()
        base = "Pix Enviado MP" if item.get("payment_method_id") == "pix" else "Pagamento Mercado Pago"

    if nome_parte:
        return f"{base} - {nome_parte}"[:120]
    return base


def _buscar_pagamentos_mp(data_inicio: str, data_fim: str) -> Dict[str, Any]:
    """Busca todos os pagamentos aprovados no período usando paginação (limit=50, offset)."""
    token = os.getenv("MP_TOKEN_FERNANDA")
    if not token:
        return {"erro": "Variável MP_TOKEN_FERNANDA não configurada no ambiente."}

    begin_date = f"{data_inicio}T00:00:00.000-03:00"
    end_date = f"{data_fim}T23:59:59.999-03:00"

    todos_itens: List[Dict[str, Any]] = []
    ignorados_cofrinho = 0
    offset = 0
    limit = 50
    max_paginas = 10  # Limite de segurança (até 500 registros por consulta)

    for _ in range(max_paginas):
        params = urllib.parse.urlencode({
            "sort": "date_created",
            "criteria": "desc",
            "range": "date_created",
            "begin_date": begin_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset,
        })
        url = f"https://api.mercadopago.com/v1/payments/search?{params}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Oikos-Sync/1.0"
        })

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")[:300]
            return {"erro": f"Erro HTTP {e.code} na API do Mercado Pago: {err_body}"}
        except Exception as e:
            return {"erro": f"Falha de conexão com Mercado Pago: {e}"}

        results = payload.get("results") or []
        for item in results:
            if item.get("status") != "approved":
                continue
            op_type = item.get("operation_type") or ""
            if op_type == "partition_transfer":
                ignorados_cofrinho += 1
                continue
            todos_itens.append(item)

        paging = payload.get("paging") or {}
        total = int(paging.get("total") or 0)
        offset += limit
        if not results or offset >= total:
            break

    return {"itens": todos_itens, "ignorados_cofrinho": ignorados_cofrinho}


def simular_conciliacao_mp(data_inicio: str, data_fim: str) -> Dict[str, Any]:
    """
    Busca movimentações aprovadas no MP no intervalo [data_inicio, data_fim] e cruza com
    a tabela transacoes (conta_id = 1) para classificar em:
    - ja_sincronizado
    - possivel_duplicado_manual
    - novo
    """
    busca = _buscar_pagamentos_mp(data_inicio, data_fim)
    if "erro" in busca:
        return {"status": "erro", "erro": busca["erro"]}

    itens_mp = busca["itens"]
    ignorados_cofrinho = busca["ignorados_cofrinho"]

    # Janela de ±1 dia para busca de possíveis duplicados manuais
    dt_ini_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date() - timedelta(days=1)
    dt_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date() + timedelta(days=1)

    conn = database.conectar_db_hibrido(pooled=True)
    try:
        cur = conn.cursor()
        # Carrega id_externo já sincronizados
        cur.execute("SELECT id_externo FROM transacoes WHERE id_externo LIKE 'mp_%'")
        ids_existentes = {str(r[0]) for r in cur.fetchall() if r[0]}

        # Carrega transações da conta 1 na janela de datas para detecção de duplicado manual
        cur.execute("""
            SELECT id, data, descricao, valor, tipo, id_externo
            FROM transacoes
            WHERE conta_id = ? AND data >= ? AND data <= ?
        """, (CONTA_MP_ID, dt_ini_obj.strftime("%Y-%m-%d"), dt_fim_obj.strftime("%Y-%m-%d")))
        manuais = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    resultado_itens: List[Dict[str, Any]] = []
    for item in itens_mp:
        valor = round(float(item.get("transaction_amount") or 0.0), 2)
        if valor <= 0:
            continue

        dt_raw = (item.get("date_approved") or item.get("date_created") or "")[:10]
        op_type = item.get("operation_type") or ""
        collector = item.get("collector") or {}
        collector_id = str(collector.get("id") or item.get("collector_id") or "")
        eh_entrada = (collector_id == MP_USER_ID_FERNANDA) and (op_type != "money_transfer")
        tipo = "receita" if eh_entrada else "despesa"
        categoria_sugerida = "Outras Receitas" if eh_entrada else "Outros Gastos"
        descricao = _extrair_descricao_limpa(item, eh_entrada)
        id_ext = f"mp_{item['id']}"

        if _eh_transferencia_interna(item, descricao):
            tipo = "transferencia"
            status_conc = "transferencia_interna"
            manual_id = None
            manual_desc = None
        elif id_ext in ids_existentes:
            status_conc = "ja_sincronizado"
            manual_id = None
            manual_desc = None
        else:
            # Procura transação manual sem id_externo com mesma data (±1 dia) e mesmo valor absoluto
            match_manual = None
            dt_item_obj = datetime.strptime(dt_raw, "%Y-%m-%d").date()
            for m in manuais:
                if m.get("id_externo"):
                    continue
                val_m = round(abs(float(m.get("valor") or 0.0)), 2)
                if abs(val_m - valor) <= 0.01:
                    try:
                        dt_m = datetime.strptime(str(m["data"])[:10], "%Y-%m-%d").date()
                        if abs((dt_m - dt_item_obj).days) <= 1:
                            match_manual = m
                            break
                    except Exception:
                        continue

            if match_manual:
                status_conc = "possivel_duplicado_manual"
                manual_id = match_manual["id"]
                manual_desc = f"{match_manual['data']} • {match_manual['descricao']}"
            else:
                status_conc = "novo"
                manual_id = None
                manual_desc = None

        resultado_itens.append({
            "id_externo": id_ext,
            "data": dt_raw,
            "tipo": tipo,
            "valor": valor,
            "descricao": descricao,
            "categoria": categoria_sugerida,
            "status_conciliacao": status_conc,
            "manual_id": manual_id,
            "manual_descricao": manual_desc,
        })

    conn_s = database.conectar_db_hibrido(pooled=True)
    try:
        saldo_info = saldo_service.calcular_saldo_conta(conn_s, CONTA_MP_ID)
        saldo_oikos = round(float(saldo_info.get("saldo_atual") or 0.0), 2)
    finally:
        conn_s.close()

    saldo_api = obter_saldo_real_mp()

    return {
        "status": "ok",
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "ignorados_cofrinho": ignorados_cofrinho,
        "saldo_oikos": saldo_oikos,
        "saldo_api": saldo_api,
        "total": len(resultado_itens),
        "itens": resultado_itens,
    }


def confirmar_conciliacao_mp(itens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Efetiva os itens selecionados pelo usuário:
    - acao == 'importar': insere nova transação na conta 1 com id_externo.
    - acao == 'vincular': apenas atualiza id_externo na transação manual existente.
    """
    importados = 0
    vinculados = 0
    ignorados = 0

    conn = database.conectar_db_hibrido(pooled=True)
    try:
        cur = conn.cursor()
        for it in itens:
            acao = it.get("acao")
            id_ext = str(it.get("id_externo") or "").strip()
            if not id_ext:
                continue

            if it.get("tipo") == "transferencia" or it.get("status_conciliacao") == "transferencia_interna":
                ignorados += 1
                continue

            if acao == "vincular" and it.get("manual_id"):
                cur.execute(
                    "UPDATE transacoes SET id_externo = ? WHERE id = ?",
                    (id_ext, int(it["manual_id"]))
                )
                vinculados += 1
            elif acao == "importar":
                cur.execute("SELECT id FROM transacoes WHERE id_externo = ? LIMIT 1", (id_ext,))
                if cur.fetchone():
                    ignorados += 1
                    continue

                dt_raw = str(it.get("data") or "")[:10]
                descricao = str(it.get("descricao") or "Movimentação MP").strip()[:120]
                valor = round(float(it.get("valor") or 0.0), 2)
                tipo = "receita" if it.get("tipo") == "receita" else "despesa"
                categoria = str(it.get("categoria") or ("Outras Receitas" if tipo == "receita" else "Outros Gastos")).strip()

                cur.execute("""
                    INSERT INTO transacoes (
                        data, descricao, valor, tipo, categoria, conta, conta_id,
                        pago, status_pagamento, afeta_saldo_bancario, titular, origem, id_externo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'pago', 1, 'Fernanda', 'mercadopago_api', ?)
                """, (dt_raw, descricao, valor, tipo, categoria, CONTA_MP_NOME, CONTA_MP_ID, id_ext))
                importados += 1

        conn.commit()
        saldo_info = saldo_service.calcular_saldo_conta(conn, CONTA_MP_ID)
        saldo_oikos = round(float(saldo_info.get("saldo_atual") or 0.0), 2)
    finally:
        conn.close()

    return {
        "status": "ok",
        "importados": importados,
        "vinculados": vinculados,
        "ignorados": ignorados,
        "saldo_oikos": saldo_oikos,
    }


def ajustar_saldo_para_mp(saldo_real_mp: float) -> Dict[str, Any]:
    """
    Ajusta o marco de saldo (ajustes_saldo) da conta Mercado Pago (id = 1) na data de hoje
    para que o saldo disponível no Oikos fique 100% idêntico ao saldo real do app Mercado Pago.
    """
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    saldo_alvo = round(float(saldo_real_mp), 2)

    conn = database.conectar_db_hibrido(pooled=True)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ajustes_saldo (conta_id, data_marco, saldo_informado, observacao)
            VALUES (?, ?, ?, ?)
        """, (CONTA_MP_ID, hoje_str, saldo_alvo, "Conciliação automática com Saldo Real Mercado Pago"))
        conn.commit()
        saldo_info = saldo_service.calcular_saldo_conta(conn, CONTA_MP_ID)
        novo_saldo = round(float(saldo_info.get("saldo_atual") or 0.0), 2)
    finally:
        conn.close()

    return {
        "status": "ok",
        "saldo_ajustado": novo_saldo,
        "data_marco": hoje_str,
    }


def sincronizar_mercadopago(data_inicio: str = "2026-11-19", data_fim: str = None) -> Dict[str, Any]:
    """Compatibilidade com chamada direta: importa apenas itens com status 'novo'."""
    if not data_fim:
        data_fim = datetime.now().strftime("%Y-%m-%d")
    sim = simular_conciliacao_mp(data_inicio, data_fim)
    if sim.get("status") != "ok":
        return sim

    novos = [
        {**it, "acao": "importar"}
        for it in sim["itens"]
        if it["status_conciliacao"] == "novo"
    ]
    ja_sync = sum(1 for it in sim["itens"] if it["status_conciliacao"] == "ja_sincronizado")
    conf = confirmar_conciliacao_mp(novos)
    return {
        "status": "ok",
        "importados": conf["importados"],
        "ignorados_duplicados": ja_sync,
        "ignorados_cofrinho": sim["ignorados_cofrinho"],
        "itens": novos,
    }
