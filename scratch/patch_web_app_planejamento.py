import re

with open('web_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Adicionar resumo em coletar_dados_dashboard
antigo_bloco_patrimonio = """    # 10. Resumo Patrimonial
    try:
        import patrimonio_service
        resumo_patrimonio = patrimonio_service.obter_resumo_patrimonial(conn)
    except Exception:
        resumo_patrimonio = None"""

novo_bloco_patrimonio = """    # 10. Resumo Patrimonial
    try:
        import patrimonio_service
        resumo_patrimonio = patrimonio_service.obter_resumo_patrimonial(conn)
    except Exception:
        resumo_patrimonio = None

    # 11. Resumo Anual e Despesas Eventuais
    try:
        import planejamento_anual_service
        cal_resumo = planejamento_anual_service.obter_calendario_anual(conn, ano_atual, mes_atual)
        proximas_despesas_resumo = [d for d in cal_resumo["todas_despesas"] if d["status"] != "paga"][:4]
        resumo_despesas_anuais = {
            "total_previsto": cal_resumo["total_geral_previsto"],
            "total_reservado": cal_resumo["total_geral_reservado"],
            "total_falta": cal_resumo["total_geral_falta"],
            "taxa_cobertura": cal_resumo["taxa_cobertura_global"],
            "proximas": proximas_despesas_resumo
        }
    except Exception:
        resumo_despesas_anuais = None"""

antigo_dash_ret = """        # Extras
        "missao": missao,
        "cartao": cartao_info,
        "resumo_patrimonio": resumo_patrimonio
    }"""

novo_dash_ret = """        # Extras
        "missao": missao,
        "cartao": cartao_info,
        "resumo_patrimonio": resumo_patrimonio,
        "resumo_despesas_anuais": resumo_despesas_anuais
    }"""

assert antigo_bloco_patrimonio in content, "antigo_bloco_patrimonio não encontrado em web_app.py"
assert antigo_dash_ret in content, "antigo_dash_ret não encontrado em web_app.py"

content = content.replace(antigo_bloco_patrimonio, novo_bloco_patrimonio, 1)
content = content.replace(antigo_dash_ret, novo_dash_ret, 1)

# 2. Adicionar cálculos no final de pagina_planejamento
antigo_plan = """    # Ordena todos os lançamentos com juros ou descontos por data decrescente
    lancamentos_ajustes.sort(key=lambda x: str(x["data"]), reverse=True)

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="planejamento.html",
        context={"""

novo_plan = """    # Ordena todos os lançamentos com juros ou descontos por data decrescente
    lancamentos_ajustes.sort(key=lambda x: str(x["data"]), reverse=True)

    # =========================================================================
    # MÓDULO DE RENDA VARIÁVEL, CENÁRIOS E CALENDÁRIO ANUAL
    # =========================================================================
    import planejamento_anual_service
    renda_analise = planejamento_anual_service.analisar_historico_renda(conn, 12, ano, mes)
    margem_drive = planejamento_anual_service.obter_margem_operacional_drive(conn, ano, mes)
    comp_cenarios = planejamento_anual_service.comparar_cenarios_com_despesas(conn, ano, mes, renda_analise["cenarios"])
    calendario_anual = planejamento_anual_service.obter_calendario_anual(conn, ano, mes)
    naturezas_disponiveis = planejamento_anual_service.NATUREZAS_ORCAMENTARIAS

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="planejamento.html",
        context={
            "renda_analise": renda_analise,
            "margem_drive": margem_drive,
            "comp_cenarios": comp_cenarios,
            "calendario_anual": calendario_anual,
            "naturezas_disponiveis": naturezas_disponiveis,"""

assert antigo_plan in content, "antigo_plan não encontrado em web_app.py"
content = content.replace(antigo_plan, novo_plan, 1)

# 3. Adicionar rotas da API de planejamento anual
rotas_api = """
# =============================================================================
# ROTAS DA API: PLANEJAMENTO DE RENDA VARIÁVEL E DESPESAS ANUAIS / EVENTUAIS
# =============================================================================

@app.post("/api/planejamento/cenarios")
async def api_salvar_cenarios_renda(request: Request):
    dados = await request.json()
    ano = int(dados.get("ano", datetime.date.today().year))
    mes = int(dados.get("mes", datetime.date.today().month))

    estavel_raw = dados.get("estavel_manual")
    cons_raw = dados.get("conservador_manual")
    hab_raw = dados.get("habitual_manual")
    fav_raw = dados.get("favoravel_manual")

    estavel_val = float(estavel_raw) if (estavel_raw is not None and str(estavel_raw).strip() != "") else None
    cons_val = float(cons_raw) if (cons_raw is not None and str(cons_raw).strip() != "") else None
    hab_val = float(hab_raw) if (hab_raw is not None and str(hab_raw).strip() != "") else None
    fav_val = float(fav_raw) if (fav_raw is not None and str(fav_raw).strip() != "") else None

    obs = dados.get("observacoes")

    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.salvar_cenarios_renda(
            conn, ano, mes, estavel_val, cons_val, hab_val, fav_val, obs
        )
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/planejamento/natureza-despesa")
async def api_salvar_natureza_despesa(request: Request):
    dados = await request.json()
    categoria = dados.get("categoria")
    natureza = dados.get("natureza")
    if not categoria or not natureza:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Categoria e natureza são obrigatórios."})

    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.salvar_classificacao_natureza(conn, categoria, natureza)
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/planejamento/despesas-eventuais")
async def api_criar_despesa_eventual(request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        import planejamento_anual_service
        new_id = planejamento_anual_service.criar_despesa_eventual(conn, dados)
        return JSONResponse({"sucesso": True, "id": new_id})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/planejamento/despesas-eventuais/{despesa_id}/editar")
async def api_editar_despesa_eventual(despesa_id: int, request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.atualizar_despesa_eventual(conn, despesa_id, dados)
        if not ok:
            return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Compromisso não encontrado."})
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/planejamento/despesas-eventuais/{despesa_id}/conciliar")
async def api_conciliar_despesa_eventual(despesa_id: int, request: Request):
    dados = await request.json()
    valor_pago = float(dados.get("valor_pago", 0.0))
    data_pag = dados.get("data_pagamento") or datetime.date.today().strftime("%Y-%m-%d")
    baixar_reserva = bool(dados.get("baixar_reserva_cofrinho", True))

    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.conciliar_pagamento_despesa_eventual(
            conn, despesa_id, valor_pago, data_pag, baixar_reserva
        )
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/planejamento/despesas-eventuais/{despesa_id}/excluir")
async def api_excluir_despesa_eventual(despesa_id: int):
    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM planejamento_despesas_eventuais WHERE id = ?", (despesa_id,))
        conn.commit()
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()
"""

ancora_rotas = '@app.get("/patrimonio"'
assert ancora_rotas in content, "ancora_rotas não encontrada em web_app.py"

content = content.replace(ancora_rotas, rotas_api + "\n\n" + ancora_rotas, 1)

with open('web_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCESSO: web_app.py atualizado com todas as rotas e integrações do planejamento anual!")
