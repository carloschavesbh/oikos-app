with open('web_app.py', 'r', encoding='utf-8') as f:
    text = f.read()

rota_alvo = '@app.post("/api/planejamento/cenarios")'
assert rota_alvo in text, "rota_alvo não encontrada"

nova_rota = """@app.post("/api/planejamento/meses-amostra")
async def api_salvar_meses_amostra(request: Request):
    dados = await request.json()
    meses_ativos = dados.get("meses_ativos", [])
    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.salvar_selecao_meses_amostra(conn, meses_ativos)
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


"""

if '@app.post("/api/planejamento/meses-amostra")' not in text:
    text = text.replace(rota_alvo, nova_rota + rota_alvo, 1)
    with open('web_app.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCESSO: rota /api/planejamento/meses-amostra adicionada a web_app.py!")
else:
    print("Rota já presente.")
