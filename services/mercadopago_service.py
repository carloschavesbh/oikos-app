import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List

import database

MP_USER_ID_FERNANDA = "2489313"
CONTA_MP_ID = 1
CONTA_MP_NOME = "Mercado Pago"


def _extrair_descricao_limpa(item: Dict[str, Any], eh_entrada: bool) -> str:
    """Extrai descrição amigável da movimentação do Mercado Pago."""
    desc = (item.get("description") or "").strip()
    if desc and desc.lower() not in ("pix", "transferência", "transferencia"):
        return desc[:120]

    # Tenta extrair nome do pagador/recebedor em point_of_interaction ou payer
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


def sincronizar_mercadopago(data_inicio: str = "2026-11-19") -> Dict[str, Any]:
    """
    Sincroniza movimentações aprovadas da conta Mercado Pago da Fernanda (user_id 2489313)
    para a conta ID 1 ('Mercado Pago'), ignorando cofrinhos (partition_transfer) e duplicidades.
    """
    token = os.getenv("MP_TOKEN_FERNANDA")
    if not token:
        return {"status": "erro", "erro": "Variável MP_TOKEN_FERNANDA não configurada no ambiente."}

    url = "https://api.mercadopago.com/v1/payments/search?sort=date_created&criteria=desc&limit=50"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Oikos-Sync/1.0"
    })

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")[:300]
        return {"status": "erro", "erro": f"Erro HTTP {e.code} na API do Mercado Pago: {err_body}"}
    except Exception as e:
        return {"status": "erro", "erro": f"Falha de conexão com Mercado Pago: {e}"}

    results = payload.get("results") or []
    importados = 0
    ignorados_duplicados = 0
    ignorados_cofrinho = 0
    itens_importados: List[Dict[str, Any]] = []

    conn = database.conectar_db_hibrido(pooled=True)
    try:
        cur = conn.cursor()
        for item in results:
            if item.get("status") != "approved":
                continue

            op_type = item.get("operation_type") or ""
            if op_type == "partition_transfer":
                ignorados_cofrinho += 1
                continue

            dt_raw = (item.get("date_approved") or item.get("date_created") or "")[:10]
            if not dt_raw or dt_raw < data_inicio:
                continue

            id_ext = f"mp_{item['id']}"
            cur.execute("SELECT id FROM transacoes WHERE id_externo = ? LIMIT 1", (id_ext,))
            if cur.fetchone():
                ignorados_duplicados += 1
                continue

            collector = item.get("collector") or {}
            collector_id = str(collector.get("id") or item.get("collector_id") or "")
            eh_entrada = (collector_id == MP_USER_ID_FERNANDA) and (op_type != "money_transfer")

            tipo = "receita" if eh_entrada else "despesa"
            categoria = "Outras Receitas" if eh_entrada else "Outros Gastos"
            valor = round(float(item.get("transaction_amount") or 0.0), 2)
            if valor <= 0:
                continue

            descricao = _extrair_descricao_limpa(item, eh_entrada)

            cur.execute("""
                INSERT INTO transacoes (
                    data, descricao, valor, tipo, categoria, conta, conta_id,
                    pago, status_pagamento, afeta_saldo_bancario, titular, origem, id_externo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'pago', 1, 'Fernanda', 'mercadopago_api', ?)
            """, (dt_raw, descricao, valor, tipo, categoria, CONTA_MP_NOME, CONTA_MP_ID, id_ext))

            importados += 1
            itens_importados.append({
                "id_externo": id_ext,
                "data": dt_raw,
                "tipo": tipo,
                "valor": valor,
                "descricao": descricao
            })

        conn.commit()
    finally:
        conn.close()

    return {
        "status": "ok",
        "importados": importados,
        "ignorados_duplicados": ignorados_duplicados,
        "ignorados_cofrinho": ignorados_cofrinho,
        "itens": itens_importados
    }
