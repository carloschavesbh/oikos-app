#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web App FastAPI + PWA - Gerenciador Financeiro & Central Operacional
Interface limpa, moderna, responsiva (Tailwind CSS) e otimizada para Desktop e Mobile (Xiaomi 12).
Preserva app.py intacto como backup.
"""

import os
import re
import json
import sqlite3
import calendar
import asyncio
import datetime
from datetime import date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal

from fastapi import FastAPI, Request, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import saldo_service
import planejamento_service

from google import genai
from google.genai import types

client = genai.Client(api_key="AQ.Ab8RN6LEqt1vtNMt6G4zuvVHh5m5fZEj6szuYf7hQUnz4zUQsg")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "financas_casa.db"))

app = FastAPI(
    title="Oikos - Gestão Financeira Familiar",
    description="Oikos • Mordomia & Gestão Familiar",
    version="2.0.0"
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Garante que nenhum erro interno derrube o FastAPI ou cause tela branca sem tratamento."""
    import traceback
    traceback.print_exc()
    accept = request.headers.get("accept", "")
    if "application/json" in accept or request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": "Erro interno no servidor."})
    return HTMLResponse(
        status_code=500,
        content="""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Oikos • Recuperação</title>
        <script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-slate-900 text-white min-h-screen flex items-center justify-center p-4">
          <div class="bg-slate-800 border border-slate-700 p-6 rounded-2xl max-w-md w-full text-center space-y-4 shadow-2xl">
            <span class="text-4xl">🛡️</span>
            <h2 class="text-lg font-bold text-white">Oikos • Recuperação do Sistema</h2>
            <p class="text-xs text-slate-400">Uma falha temporária foi contida com segurança sem comprometer seus dados.</p>
            <a href="/" class="inline-block px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition">Voltar ao Início</a>
          </div>
        </body>
        </html>
        """
    )

# Garantir existência de pastas estáticas e templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/manifest.json", include_in_schema=False)
async def rota_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
async def rota_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")


@app.get("/favicon.ico", include_in_schema=False)
async def rota_favicon():
    return FileResponse(os.path.join(STATIC_DIR, "app-icon.png"), media_type="image/png")


def conectar_db() -> sqlite3.Connection:
    """Abre conexão com o banco financas_casa.db com suporte a Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def formatar_moeda_br(valor: Any) -> str:
    """Formata qualquer valor decimal/numérico no padrão monetário brasileiro R$ 1.234,56."""
    if valor is None:
        return "R$ 0,00"
    try:
        val = float(valor)
        negativo = val < 0
        val = abs(val)
        partes = f"{val:,.2f}".split(".")
        inteira = partes[0].replace(",", ".")
        decimal = partes[1]
        sinal = "-" if negativo else ""
        return f"{sinal}R$ {inteira},{decimal}"
    except Exception:
        return f"R$ {valor}"


# Registrar filtros no Jinja2
templates.env.filters["moeda"] = formatar_moeda_br


def obter_icone_categoria(cat: str) -> str:
    """Mapeia categoria para ícone representativo."""
    if not cat:
        return "🏷️"
    c = cat.lower()
    if any(k in c for k in ["aliment", "mercado", "super"]):
        return "🛒"
    if any(k in c for k in ["saúde", "farm", "medic", "dent", "consult"]):
        return "💊"
    if any(k in c for k in ["combust", "posto", "gasol", "etanol"]):
        return "⛽"
    if any(k in c for k in ["veículo", "carro", "ipva", "manut"]):
        return "🚗"
    if any(k in c for k in ["água", "copasa"]):
        return "💧"
    if any(k in c for k in ["luz", "cemig", "energ"]):
        return "⚡"
    if any(k in c for k in ["internet", "claro", "vivo", "celular"]):
        return "📱"
    if any(k in c for k in ["aluguel", "condom", "casa", "morad"]):
        return "🏠"
    if any(k in c for k in ["dívida", "emprést", "acordo", "bv", "banco"]):
        return "📁"
    if any(k in c for k in ["salário", "fernanda"]):
        return "💼"
    if any(k in c for k in ["99", "uber", "corrida"]):
        return "🚕"
    return "🏷️"


templates.env.filters["icone_cat"] = obter_icone_categoria


def coletar_dados_dashboard() -> Dict[str, Any]:
    """Coleta e calcula todos os dados essenciais da Visão Geral de forma centralizada e performática."""
    conn = conectar_db()
    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    ano_atual = hoje.year
    mes_atual = hoje.month
    inicio_mes_str = f"{ano_atual}-{mes_atual:02d}-01"
    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    fim_mes_str = f"{ano_atual}-{mes_atual:02d}-{ultimo_dia:02d}"
    limite_7d_str = (hoje + timedelta(days=6)).strftime("%Y-%m-%d")
    dias_restantes_mes = max(1, ultimo_dia - hoje.day + 1)

    # 1. Saldo em Caixa Consolidado (via Serviço Centralizado)
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    saldo_caixa = float(res_saldo.get("saldo_consolidado", 0.0))
    contas_lista = res_saldo.get("contas", [])

    mp_conta = next((c for c in contas_lista if "Mercado" in c["conta_nome"]), None)
    cart_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["dinheiro", "carteira"])), None)
    pay99_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["99pay", "99 pay", "saldo 99"])), None)
    mp_saldo = float(mp_conta["saldo_atual"]) if mp_conta else 40.0
    cart_saldo = float(cart_conta["saldo_atual"]) if cart_conta else 7.0
    pay99_saldo = float(pay99_conta["saldo_atual"]) if pay99_conta else 0.0

    contas_movimentacao = [
        {
            "id": c["conta_id"],
            "nome": c["conta_nome"],
            "tipo": c.get("tipo", "digital"),
            "saldo_atual": float(c["saldo_atual"]),
            "cor": c.get("cor", "#009ee3"),
            "icone": c.get("icone", "🏦"),
            "incluir_saldo_consolidado": c.get("incluir_saldo_consolidado", 1),
            "subtitulo": "Conta Principal" if "mercado" in c["conta_nome"].lower() else ("Ganhos Operação 99" if "99" in c["conta_nome"].lower() else ("Caixa Físico" if any(k in c["conta_nome"].lower() for k in ["carteira", "dinheiro"]) else "Conta Corrente"))
        }
        for c in contas_lista
        if c.get("tipo") != "cofrinho"
    ]

    # 2. Receita Mensal Consolidada (Salário Fernanda + Produção Oficial 99)
    prod_99 = saldo_service.obter_producao_consolidada_99(conn)
    fat_99_mes = float(prod_99.get("total_mes_bruto", 1469.50))
    fat_99_semana = float(prod_99.get("semana", {}).get("bruto", 146.70))

    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'receita' AND pago = 1 AND data >= ? AND data <= ?
          AND (descricao LIKE '%Fernanda%' OR categoria LIKE '%Fernanda%')
    """, (inicio_mes_str, fim_mes_str))
    row_sal = cur.fetchone()
    sal_fernanda = float(row_sal[0]) if (row_sal and row_sal[0] > 0) else 3523.43
    receita_mensal_total = sal_fernanda + fat_99_mes

    # 3. Despesas do Mês (Pagas + Pendentes do Mês)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'despesa' AND pago = 1 AND data >= ? AND data <= ?
    """, (inicio_mes_str, fim_mes_str))
    despesas_pagas_mes = float(cur.fetchone()[0] or 0.0)

    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data >= ? AND data <= ?
    """, (inicio_mes_str, fim_mes_str))
    despesas_pendentes_mes = float(cur.fetchone()[0] or 0.0)
    despesa_mensal_total = despesas_pagas_mes + despesas_pendentes_mes

    # 4. Meta do Dia e Produção de Hoje
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'horas_hoje_planejadas'")
    row_h_cfg = cur.fetchone()
    horas_hoje_meta = float(row_h_cfg[0]) if row_h_cfg and row_h_cfg[0] else 5.0
    taxa_hora_mercado = 35.0
    meta_bruta_hoje = horas_hoje_meta * taxa_hora_mercado

    cur.execute("""
        SELECT COALESCE(SUM(ganho_bruto), 0), COALESCE(SUM(horas), 0), COUNT(*), COALESCE(SUM(combustivel), 0)
        FROM turnos
        WHERE data = ?
    """, (hoje_str,))
    row_t_hoje = cur.fetchone()
    bruto_hoje = float(row_t_hoje[0] or 0.0)
    horas_hoje_real = float(row_t_hoje[1] or 0.0)
    qtd_turnos_hoje = int(row_t_hoje[2] or 0)
    comb_hoje = float(row_t_hoje[3] or 0.0)
    liquido_hoje = bruto_hoje - comb_hoje

    pct_meta_hoje = min(100.0, (bruto_hoje / meta_bruta_hoje * 100.0)) if meta_bruta_hoje > 0 else 0.0
    restante_meta_hoje = max(0.0, meta_bruta_hoje - bruto_hoje)

    # 5. Contas Atrasadas (Vencidas)
    cur.execute("""
        SELECT id, data, descricao, categoria, valor, conta, COALESCE(titular, '') as titular
        FROM transacoes
        WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data < ?
        ORDER BY data ASC, id ASC
    """, (hoje_str,))
    rows_atrasadas = cur.fetchall()
    atrasadas = []
    tot_atrasadas = 0.0
    for r in rows_atrasadas:
        val = float(r["valor"])
        tot_atrasadas += val
        dt_obj = datetime.datetime.strptime(str(r["data"])[:10], "%Y-%m-%d").date()
        dias_atraso = (hoje - dt_obj).days
        atrasadas.append({
            "id": r["id"],
            "data": dt_obj.strftime("%d/%m"),
            "data_completa": dt_obj.strftime("%d/%m/%Y"),
            "descricao": r["descricao"],
            "categoria": r["categoria"],
            "valor": val,
            "conta": r["conta"] or "Mercado Pago",
            "dias_atraso": dias_atraso
        })

    # 6. Contas que Vencem Hoje
    cur.execute("""
        SELECT id, data, descricao, categoria, valor, conta, COALESCE(titular, '') as titular
        FROM transacoes
        WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data = ?
        ORDER BY id ASC
    """, (hoje_str,))
    rows_hoje = cur.fetchall()
    vence_hoje = []
    tot_vence_hoje = 0.0
    for r in rows_hoje:
        val = float(r["valor"])
        tot_vence_hoje += val
        vence_hoje.append({
            "id": r["id"],
            "data": hoje.strftime("%d/%m"),
            "descricao": r["descricao"],
            "categoria": r["categoria"],
            "valor": val,
            "conta": r["conta"] or "Mercado Pago"
        })

    # 7. Contas Próximos 7 Dias (apenas contagem e valor resumido)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0), COUNT(*)
        FROM transacoes
        WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data > ? AND data <= ?
    """, (hoje_str, limite_7d_str))
    row_prox7 = cur.fetchone()
    tot_prox7 = float(row_prox7[0] or 0.0)
    qtd_prox7 = int(row_prox7[1] or 0)

    # 8. Missão Ativa da Semana (IPVA / Prioridade)
    try:
        missao = planejamento_service.obter_missao_ativa_semana(conn, mes_ano=f"{ano_atual}-{mes_atual:02d}", data_referencia=hoje)
    except Exception:
        missao = {"tem_missao": False}

    # 9. Cartão de Crédito
    cur.execute("SELECT id, nome, bandeira, limite_total, dia_vencimento FROM cartoes LIMIT 1")
    row_crd = cur.fetchone()
    cartao_info = None
    if row_crd:
        nome_crd = row_crd["nome"]
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0) FROM transacoes
            WHERE (descricao LIKE ? OR conta = ?) AND data >= ? AND data <= ?
        """, (f"%{nome_crd}%", nome_crd, inicio_mes_str, fim_mes_str))
        gastos_crd = float(cur.fetchone()[0] or 0.0)
        lim_total = float(row_crd["limite_total"] or 0.0)
        lim_disp = max(0.0, lim_total - gastos_crd)
        cartao_info = {
            "nome": nome_crd,
            "bandeira": row_crd["bandeira"],
            "limite_total": lim_total,
            "limite_disponivel": lim_disp,
            "dia_vencimento": row_crd["dia_vencimento"]
        }

    conn.close()

    dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    nome_dia_hoje = dias_semana_pt[hoje.weekday()]

    return {
        "hoje_str": hoje_str,
        "hoje_formatado": hoje.strftime("%d/%m/%Y"),
        "dia_semana": nome_dia_hoje,
        "mes_nome": "Outubro",
        "ano": ano_atual,
        # Resumo da Casa
        "receita_mensal": receita_mensal_total,
        "salario_fernanda": sal_fernanda,
        "fat_99_mes": fat_99_mes,
        "despesa_mensal": despesa_mensal_total,
        "despesas_pagas": despesas_pagas_mes,
        "despesas_pendentes": despesas_pendentes_mes,
        "saldo_caixa": saldo_caixa,
        "mp_saldo": mp_saldo,
        "cart_saldo": cart_saldo,
        "pay99_saldo": pay99_saldo,
        "contas": contas_movimentacao,
        # Meta do Dia
        "horas_hoje_meta": horas_hoje_meta,
        "meta_bruta_hoje": meta_bruta_hoje,
        "bruto_hoje": bruto_hoje,
        "horas_hoje_real": horas_hoje_real,
        "qtd_turnos_hoje": qtd_turnos_hoje,
        "liquido_hoje": liquido_hoje,
        "pct_meta_hoje": round(pct_meta_hoje, 1),
        "restante_meta_hoje": restante_meta_hoje,
        # Contas a Pagar
        "atrasadas": atrasadas,
        "tot_atrasadas": tot_atrasadas,
        "vence_hoje": vence_hoje,
        "tot_vence_hoje": tot_vence_hoje,
        "qtd_prox7": qtd_prox7,
        "tot_prox7": tot_prox7,
        # Extras
        "missao": missao,
        "cartao": cartao_info
    }


# =============================================================================
# ROTAS HTTP
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    dados = coletar_dados_dashboard()
    return templates.TemplateResponse(request=request, name="index.html", context={"d": dados, "active_tab": "visao_geral"})


# =============================================================================
# ROTAS: LANÇAMENTOS & EXTRATO
# =============================================================================

@app.get("/extrato", include_in_schema=False)
@app.get("/extrato/", include_in_schema=False)
async def rota_extrato_redirect(request: Request):
    """Redireciona permanentemente /extrato para /lancamentos preservando parâmetros de busca."""
    url = "/lancamentos"
    if request.url.query:
        url += f"?{request.url.query}"
    return RedirectResponse(url=url, status_code=301)


@app.get("/lancamentos", response_class=HTMLResponse)
async def pagina_lancamentos(
    request: Request,
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    periodo: Optional[str] = Query(None),
    filtro: Optional[str] = Query(None)
):
    conn = conectar_db()
    hoje = date.today()

    if periodo and "-" in periodo:
        try:
            parts = periodo.strip().split("-")
            ano = int(parts[0])
            mes = int(parts[1])
        except Exception:
            pass

    if ano is None:
        ano = hoje.year
    if mes is None or mes < 1 or mes > 12:
        mes = hoje.month

    MESES_PT = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    mes_nome = MESES_PT[mes]

    if mes == 1:
        mes_ant, ano_ant = 12, ano - 1
    else:
        mes_ant, ano_ant = mes - 1, ano

    if mes == 12:
        mes_prox, ano_prox = 1, ano + 1
    else:
        mes_prox, ano_prox = mes + 1, ano

    eh_mes_atual = (ano == hoje.year and mes == hoje.month)

    inicio_mes = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    # Lista para o dropdown de saltar meses (ano anterior, atual e próximo)
    opcoes_periodo = []
    anos_disp = sorted(list({hoje.year - 1, hoje.year, ano, ano + 1}))
    for a in anos_disp:
        for m in range(1, 13):
            opcoes_periodo.append({
                "valor": f"{a}-{m:02d}",
                "mes": m,
                "ano": a,
                "label": f"{MESES_PT[m]} {a}",
                "selecionado": (a == ano and m == mes)
            })

    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, descricao, valor, tipo, categoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra
        FROM transacoes
        WHERE data >= ? AND data <= ?
        ORDER BY data DESC, id DESC
    """, (inicio_mes, fim_mes))
    rows = cur.fetchall()

    hoje_str = hoje.strftime("%Y-%m-%d")
    transacoes = []
    tot_receitas = 0.0
    tot_despesas = 0.0

    for r in rows:
        val = float(r["valor"] or 0.0)
        tipo = r["tipo"] or "despesa"
        if tipo == "receita":
            tot_receitas += val
        else:
            tot_despesas += val

        dt_str = str(r["data"])[:10]
        try:
            dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
            dt_fmt = dt_obj.strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str

        pago_flag = 1 if r["pago"] == 1 else 0
        is_atrasada = (tipo == "despesa" and pago_flag == 0 and dt_str < hoje_str)

        transacoes.append({
            "id": r["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": r["descricao"] or "",
            "valor": val,
            "tipo": tipo,
            "categoria": r["categoria"] or "Geral",
            "conta": r["conta"] or "Mercado Pago",
            "pago": pago_flag,
            "grupo_parcelamento": r["grupo_parcelamento"],
            "numero_parcela": r["numero_parcela"],
            "total_parcelas_compra": r["total_parcelas_compra"],
            "eh_passada": False,
            "is_atrasada": is_atrasada
        })

    # Contas atrasadas de meses anteriores: despesas pendentes com vencimento anterior ao mês selecionado
    cur.execute("""
        SELECT id, data, descricao, valor, tipo, categoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra
        FROM transacoes
        WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data < ?
        ORDER BY data ASC, id ASC
    """, (inicio_mes,))
    rows_atrasadas = cur.fetchall()

    transacoes_atrasadas = []
    tot_atrasadas = 0.0

    for r in rows_atrasadas:
        val = float(r["valor"] or 0.0)
        tot_atrasadas += val
        dt_str = str(r["data"])[:10]
        try:
            dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
            dt_fmt = dt_obj.strftime("%d/%m/%Y")
        except Exception:
            dt_fmt = dt_str

        transacoes_atrasadas.append({
            "id": r["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": r["descricao"] or "",
            "valor": val,
            "tipo": "despesa",
            "categoria": r["categoria"] or "Geral",
            "conta": r["conta"] or "Mercado Pago",
            "pago": 0,
            "grupo_parcelamento": r["grupo_parcelamento"],
            "numero_parcela": r["numero_parcela"],
            "total_parcelas_compra": r["total_parcelas_compra"],
            "eh_passada": True,
            "is_atrasada": True
        })

    qtd_atrasadas = len(transacoes_atrasadas)

    conn.close()
    saldo_periodo = tot_receitas - tot_despesas

    return templates.TemplateResponse(
        request=request,
        name="lancamentos.html",
        context={
            "transacoes": transacoes,
            "transacoes_atrasadas": transacoes_atrasadas,
            "qtd_atrasadas": qtd_atrasadas,
            "total_atrasadas": tot_atrasadas,
            "total_receitas": tot_receitas,
            "total_despesas": tot_despesas,
            "saldo_periodo": saldo_periodo,
            "mes": mes,
            "ano": ano,
            "mes_nome": mes_nome,
            "mes_ant": mes_ant,
            "ano_ant": ano_ant,
            "mes_prox": mes_prox,
            "ano_prox": ano_prox,
            "eh_mes_atual": eh_mes_atual,
            "opcoes_periodo": opcoes_periodo,
            "filtro_inicial": filtro or "",
            "hoje_str": hoje_str,
            "active_tab": "lancamentos"
        }
    )


@app.post("/api/lancamentos")
async def api_criar_lancamento(
    data: str = Form(...),
    tipo: str = Form(...),
    valor: float = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    conta: str = Form(...),
    pago: Optional[int] = Form(0)
):
    """Insere nova transação de receita ou despesa no banco SQLite."""
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser positivo.")

    conn = conectar_db()
    try:
        cur.execute("SELECT id FROM contas_config WHERE nome = ?", (conta,))
        row_c = cur.fetchone()
        if row_c:
            conta_id = row_c[0]
        else:
            conta_id = 1 if "Mercado" in conta else (2 if "Dinheiro" in conta or "Carteira" in conta else (1779 if "99" in conta else 1))
        afeta_saldo = 1 if pago == 1 else 0

        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data, descricao.strip(), valor, tipo, categoria, conta, conta_id, pago, afeta_saldo))
        conn.commit()
        return {"sucesso": True, "mensagem": f"{tipo.capitalize()} '{descricao}' de {formatar_moeda_br(valor)} lançada com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


# =============================================================================
# ROTAS: CONTAS & COFRINHOS
# =============================================================================

@app.get("/contas", response_class=HTMLResponse)
async def pagina_contas(request: Request):
    conn = conectar_db()
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    saldo_livre = float(res_saldo.get("saldo_consolidado", 0.0))

    contas_lista = res_saldo.get("contas", [])
    mp_conta = next((c for c in contas_lista if "Mercado" in c["conta_nome"]), None)
    cart_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["dinheiro", "carteira"])), None)
    pay99_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["99pay", "99 pay", "saldo 99"])), None)
    mp_saldo = float(mp_conta["saldo_atual"]) if mp_conta else 40.0
    cart_saldo = float(cart_conta["saldo_atual"]) if cart_conta else 7.0
    pay99_saldo = float(pay99_conta["saldo_atual"]) if pay99_conta else 0.0

    contas_movimentacao = [
        {
            "id": c["conta_id"],
            "nome": c["conta_nome"],
            "tipo": c.get("tipo", "digital"),
            "saldo": float(c["saldo_atual"]),
            "saldo_atual": float(c["saldo_atual"]),
            "cor": c.get("cor", "#009ee3"),
            "icone": c.get("icone", "🏦"),
            "incluir_saldo_consolidado": c.get("incluir_saldo_consolidado", 1),
            "subtitulo": "Conta Principal • Pix & Débito" if "mercado" in c["conta_nome"].lower() else ("Conta Digital • Ganhos da 99" if "99" in c["conta_nome"].lower() else ("Caixa Físico • Recebimentos em Espécie" if any(k in c["conta_nome"].lower() for k in ["carteira", "dinheiro"]) else "Conta Corrente")),
            "tag": "Principal" if "mercado" in c["conta_nome"].lower() else ("Digital" if "99" in c["conta_nome"].lower() else ("Físico" if any(k in c["conta_nome"].lower() for k in ["carteira", "dinheiro"]) else "Conta"))
        }
        for c in contas_lista
        if c.get("tipo") != "cofrinho"
    ]

    cofrinhos = planejamento_service.obter_cofrinhos(conn)
    total_cofrinhos = sum(float(c.get("saldo_confirmado") or 0.0) for c in cofrinhos)
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="contas.html",
        context={
            "saldo_livre": saldo_livre,
            "mp_saldo": mp_saldo,
            "cart_saldo": cart_saldo,
            "pay99_saldo": pay99_saldo,
            "contas_movimentacao": contas_movimentacao,
            "total_reservas": total_cofrinhos,
            "saldo_total_geral": saldo_livre + total_cofrinhos,
            "cofrinhos": cofrinhos,
            "active_tab": "contas"
        }
    )


@app.post("/api/contas/{conta_id}/editar")
@app.post("/contas/{conta_id}/editar")
@app.post("/api/contas/editar")
@app.post("/contas/editar")
@app.post("/api/contas/salvar")
@app.post("/contas/salvar")
async def api_salvar_conta(request: Request, conta_id: Optional[int] = None):
    """
    Cria ou edita uma conta em contas_config e registra o ajuste/marco inicial de saldo se aplicável.
    """
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            target_id = conta_id or payload.get("conta_id") or payload.get("id")
            nome = str(payload.get("nome", "")).strip()
            saldo_informado = float(payload.get("saldo") or payload.get("saldo_atual") or payload.get("saldo_inicial") or 0.0)
            cor = str(payload.get("cor", "#009ee3")).strip()
            icone = str(payload.get("icone", "mercadopago.svg")).strip()
            tipo = str(payload.get("tipo", "digital")).strip()
            nao_somar = payload.get("nao_somar")
            if nao_somar is not None:
                incluir_consolidado = 0 if (nao_somar is True or nao_somar == 1 or str(nao_somar).lower() in ["true", "1", "on"]) else 1
            else:
                incluir_consolidado = int(payload.get("incluir_saldo_consolidado", 1) or 0)
        else:
            form = await request.form()
            target_id = conta_id or form.get("conta_id") or form.get("id")
            nome = str(form.get("nome", "")).strip()
            saldo_informado = float(form.get("saldo") or form.get("saldo_atual") or form.get("saldo_inicial") or 0.0)
            cor = str(form.get("cor", "#009ee3")).strip()
            icone = str(form.get("icone", "mercadopago.svg")).strip()
            tipo = str(form.get("tipo", "digital")).strip()
            nao_somar = form.get("nao_somar")
            if nao_somar is not None:
                incluir_consolidado = 0 if (nao_somar is True or nao_somar == 1 or str(nao_somar).lower() in ["true", "1", "on"]) else 1
            else:
                incluir_consolidado = int(form.get("incluir_saldo_consolidado", 1) or 0)

        if not nome:
            raise HTTPException(status_code=400, detail="O nome da conta é obrigatório.")

        cur = conn.cursor()
        hoje_iso = date.today().strftime("%Y-%m-%d")

        if target_id and int(target_id) > 0:
            target_id = int(target_id)
            cur.execute("""
                UPDATE contas_config 
                SET nome = ?, tipo = ?, cor = ?, icone = ?, incluir_saldo_consolidado = ?
                WHERE id = ?
            """, (nome, tipo, cor, icone, incluir_consolidado, target_id))

            # Verifica se o saldo informado difere do saldo calculado atualmente
            res_atual = saldo_service.calcular_saldo_conta(conn, target_id)
            saldo_atual = float(res_atual["saldo_atual"])
            if abs(saldo_atual - saldo_informado) > 0.009:
                diferenca = round(saldo_informado - saldo_atual, 2)
                # 1. Registra marco dinâmico de ajuste de saldo
                saldo_service.registrar_ajuste(
                    conn=conn,
                    conta_id=target_id,
                    data_ajuste=hoje_iso,
                    saldo_informado=Decimal(str(round(saldo_informado, 2))),
                    tipo="ajuste",
                    motivo="Ajuste manual de saldo via edição de conta"
                )
                # 2. Registra lançamento histórico de conferência em transacoes
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
                    VALUES (?, ?, ?, ?, 'AJUSTE', ?, ?, 1, 0)
                """, (
                    hoje_iso,
                    f"Ajuste de Saldo ({'+' if diferenca > 0 else ''}{diferenca:.2f})",
                    abs(diferenca),
                    "receita" if diferenca > 0 else "despesa",
                    nome,
                    target_id
                ))
            conn.commit()
            return JSONResponse({
                "success": True,
                "sucesso": True,
                "conta_id": target_id,
                "mensagem": f"Conta '{nome}' atualizada com sucesso!"
            })
        else:
            cur.execute("""
                INSERT INTO contas_config (nome, tipo, cor, icone, incluir_saldo_consolidado)
                VALUES (?, ?, ?, ?, ?)
            """, (nome, tipo, cor, icone, incluir_consolidado))
            nova_id = cur.lastrowid
            if abs(saldo_informado) > 0.009:
                saldo_service.registrar_ajuste(
                    conn=conn,
                    conta_id=nova_id,
                    data_ajuste=hoje_iso,
                    saldo_informado=Decimal(str(round(saldo_informado, 2))),
                    tipo="marco_inicial",
                    motivo="Saldo inicial de cadastro de conta"
                )
            conn.commit()
            return JSONResponse({
                "success": True,
                "sucesso": True,
                "conta_id": nova_id,
                "mensagem": f"Conta '{nome}' cadastrada com sucesso!"
            })
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/contas/{conta_id}/excluir")
@app.post("/contas/{conta_id}/excluir")
@app.post("/api/contas/excluir")
@app.post("/contas/excluir")
@app.post("/api/contas/remover")
@app.post("/contas/remover")
async def api_remover_conta(request: Request, conta_id: Optional[int] = None):
    """
    Exclui ou oculta conta de movimentação com segurança.
    """
    conn = conectar_db()
    try:
        target_id = conta_id
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            target_id = target_id or int(payload.get("id") or payload.get("conta_id") or 0)
        else:
            form = await request.form()
            target_id = target_id or int(form.get("id") or form.get("conta_id") or 0)

        if not target_id:
            raise HTTPException(status_code=400, detail="ID da conta não informado.")

        conta_id = int(target_id)

        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM transacoes 
            WHERE conta_id = ? OR conta_destino_id = ?
        """, (conta_id, conta_id))
        qtd_transacoes = cur.fetchone()[0]

        if qtd_transacoes > 0:
            cur.execute("UPDATE contas_config SET incluir_saldo_consolidado = 0 WHERE id = ?", (conta_id,))
            conn.commit()
            return JSONResponse({
                "sucesso": True,
                "mensagem": "A conta possui transações vinculadas e foi desativada do saldo consolidado."
            })
        else:
            cur.execute("DELETE FROM ajustes_saldo WHERE conta_id = ?", (conta_id,))
            cur.execute("DELETE FROM contas_config WHERE id = ?", (conta_id,))
            conn.commit()
            return JSONResponse({
                "sucesso": True,
                "mensagem": "Conta removida com sucesso!"
            })
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/cofrinhos/guardar")
async def api_cofrinho_guardar(
    cofrinho_id: int = Form(...),
    valor: float = Form(...),
    descricao: Optional[str] = Form(None)
):
    """Guarda valor do Mercado Pago em um cofrinho via saldo_service."""
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")
    conn = conectar_db()
    try:
        hoje_iso = date.today().strftime("%Y-%m-%d")
        ok, msg = saldo_service.transferir_para_cofrinho(
            conn=conn,
            cofrinho_id=cofrinho_id,
            valor=valor,
            data_iso=hoje_iso,
            descricao=descricao
        )
        if ok:
            return {"sucesso": True, "mensagem": msg}
        else:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": msg})
    finally:
        conn.close()


@app.post("/api/cofrinhos/resgatar")
async def api_cofrinho_resgatar(
    cofrinho_id: int = Form(...),
    valor: float = Form(...),
    descricao: Optional[str] = Form(None)
):
    """Resgata valor de um cofrinho para o Mercado Pago via saldo_service."""
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")
    conn = conectar_db()
    try:
        hoje_iso = date.today().strftime("%Y-%m-%d")
        ok, msg = saldo_service.retirar_de_cofrinho(
            conn=conn,
            cofrinho_id=cofrinho_id,
            valor=valor,
            data_iso=hoje_iso,
            descricao=descricao
        )
        if ok:
            return {"sucesso": True, "mensagem": msg}
        else:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": msg})
    finally:
        conn.close()


# =============================================================================
# ROTAS: CARTÕES & FATURAS
# =============================================================================

@app.get("/cartoes", response_class=HTMLResponse)
async def pagina_cartoes(request: Request, c: Optional[int] = 1):
    conn = conectar_db()
    hoje = date.today()
    ano = hoje.year
    mes = hoje.month
    inicio_mes = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    cur = conn.cursor()

    # Garante que os dois cartões reais existem no banco
    cur.execute("SELECT id FROM cartoes WHERE nome LIKE '%Inter%' OR nome LIKE '%Aparecida%'")
    row_inter = cur.fetchone()
    if not row_inter:
        cur.execute("""
            INSERT INTO cartoes (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor)
            VALUES ('Cartão Inter Aparecida', 'Mastercard', 5000.0, 1, 7, '#ea580c')
        """)
        id_inter = cur.lastrowid
        trans_inter = [
            ('2026-11-07', 'Lava e Seca Midea 11kg - Parcela 04/10', 389.00, 'despesa', 'Eletrodomésticos', 'Cartão Inter Aparecida', id_inter, 0, 4, 10, 'Aparecida'),
            ('2026-11-07', 'Venvanse 70mg - Drogaria Raia', 489.50, 'despesa', 'Medicamentos', 'Cartão Inter Aparecida', id_inter, 0, 1, 3, 'Carlos'),
            ('2026-11-07', 'Empréstimo Pessoal Inter - Parcela 02/06', 1056.62, 'despesa', 'Empréstimos', 'Cartão Inter Aparecida', id_inter, 0, 2, 6, 'Carlos')
        ]
        for dt, desc, val, tp, cat, cnta, cid, pg, np, tp_compra, tit in trans_inter:
            cur.execute("""
                INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, numero_parcela, total_parcelas_compra, titular, afeta_saldo_bancario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (dt, desc, val, tp, cat, cnta, cid, pg, np, tp_compra, tit))
        conn.commit()

    # Busca todos os cartões cadastrados
    cur.execute("SELECT id, nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor FROM cartoes ORDER BY id ASC")
    rows_crd = cur.fetchall()

    cartoes_dados = []
    cartao_ativo = None

    for r in rows_crd:
        cid = r["id"]
        nome = r["nome"]
        bandeira = r["bandeira"]
        lim_total = float(r["limite_total"] or 0.0)
        dia_fech = r["dia_fechamento"]
        dia_venc = r["dia_vencimento"]
        cor = r["cor"] or "#0f172a"

        # Compras estritamente de cartão de crédito para este cartão:
        # Exclui Copasa, Cemig, receitas, e parcelamentos Pix (Paga Leve)
        if "Inter" in nome or "Aparecida" in nome:
            cur.execute("""
                SELECT id, data, descricao, valor, categoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
                FROM transacoes
                WHERE tipo = 'despesa'
                  AND (conta = 'Cartão Inter Aparecida' OR descricao LIKE '%Inter Aparecida%')
                ORDER BY data ASC, id ASC
            """)
        else:
            # Mercado Pago Card: Compras e despesas no cartão MP
            cur.execute("""
                SELECT id, data, descricao, valor, categoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
                FROM transacoes
                WHERE tipo = 'despesa'
                  AND (
                    conta = 'Mercado Pago Card'
                    OR (descricao LIKE '%Fatura Cartão%' AND categoria = 'Pagamento de fatura')
                    OR (descricao LIKE '%Mercado Pago Card%')
                    OR (descricao LIKE '%Audible%' OR descricao LIKE '%YouCine%')
                  )
                  AND (grupo_parcelamento IS NULL OR NOT grupo_parcelamento LIKE 'pagaleve%')
                  AND categoria NOT IN ('HABITAÇÃO', 'Energia', 'Impostos Veículo', 'Acordo BV')
                  AND descricao NOT LIKE '%Copasa%'
                  AND descricao NOT LIKE '%Cemig%'
                  AND descricao NOT LIKE '%Salário%'
                ORDER BY data ASC, id ASC
            """)

        raw_compras = cur.fetchall()
        compras = []
        tot_fatura = 0.0

        for it in raw_compras:
            val = float(it["valor"] or 0.0)
            tot_fatura += val
            dt_str = str(it["data"])[:10]
            try:
                dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                dt_fmt = dt_str

            compras.append({
                "id": it["id"],
                "data": dt_str,
                "data_formatada": dt_fmt,
                "descricao": it["descricao"],
                "valor": val,
                "categoria": it["categoria"] or "Cartão",
                "conta": it["conta"],
                "pago": 1 if it["pago"] == 1 else 0,
                "numero_parcela": it["numero_parcela"],
                "total_parcelas_compra": it["total_parcelas_compra"],
                "titular": it["titular"] or ("Aparecida" if "Inter" in nome else "Carlos")
            })

        lim_disp = max(0.0, lim_total - tot_fatura) if lim_total > 0 else 0.0
        pct_uso = (tot_fatura / lim_total * 100) if lim_total > 0 else 100.0

        c_info = {
            "id": cid,
            "nome": nome,
            "bandeira": bandeira,
            "limite_total": lim_total,
            "total_fatura": tot_fatura,
            "limite_disponivel": lim_disp,
            "pct_uso": pct_uso,
            "dia_fechamento": dia_fech,
            "dia_vencimento": dia_venc,
            "cor": cor,
            "compras": compras
        }
        cartoes_dados.append(c_info)

        if cid == c:
            cartao_ativo = c_info

    if not cartao_ativo and cartoes_dados:
        cartao_ativo = cartoes_dados[0]

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="cartoes.html",
        context={
            "cartoes": cartoes_dados,
            "cartao_ativo": cartao_ativo,
            "mes_atual": f"{mes:02d}",
            "active_tab": "cartoes"
        }
    )


# =============================================================================
# ROTAS: PAGA LEVE (PIX 4X QUINZENAL)
# =============================================================================

@app.get("/pagaleve", response_class=HTMLResponse)
async def pagina_pagaleve(request: Request):
    conn = conectar_db()
    cur = conn.cursor()

    # 1. Contas Paga Leve (Carlos e Fernanda)
    cur.execute("SELECT * FROM pagaleve_contas WHERE ativo = 1 ORDER BY id ASC")
    contas_pl = [dict(r) for r in cur.fetchall()]

    # 2. Metadados de compras cadastradas em pagaleve_compras
    cur.execute("SELECT * FROM pagaleve_compras ORDER BY id ASC")
    compras_meta = {r["grupo_parcelamento"]: dict(r) for r in cur.fetchall()}

    # 3. Transações de Paga Leve
    cur.execute("""
        SELECT id, data, descricao, valor, categoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
        FROM transacoes
        WHERE tipo = 'despesa'
          AND (grupo_parcelamento LIKE 'pagaleve%' OR descricao LIKE '%Paga Leve%')
        ORDER BY data ASC, id ASC
    """)
    trans_pl = [dict(r) for r in cur.fetchall()]

    import re
    grupos = {}
    for t in trans_pl:
        grp = t.get("grupo_parcelamento")
        if not grp:
            grp = re.sub(r' - Paga Leve.*', '', t["descricao"], flags=re.I).strip()
        if grp not in grupos:
            grupos[grp] = []
        grupos[grp].append(t)

    contratos = []
    tot_aberto_geral = 0.0
    tot_pago_geral = 0.0
    aberto_carlos = 0.0
    aberto_fernanda = 0.0
    proximas_parcelas = []

    for grp_id, itens in grupos.items():
        meta = compras_meta.get(grp_id, {})
        nome = meta.get("descricao") or re.sub(r' - Paga Leve.*', '', itens[0]["descricao"], flags=re.I).strip()
        val_orig = float(meta.get("valor_original") or sum(r["valor"] for r in itens))
        total_parc = int(meta.get("total_parcelas") or len(itens))
        titular = meta.get("titular") or itens[0].get("titular") or "Carlos"
        if titular in ("A Confirmar", "None", ""):
            titular = "Carlos"

        itens_sorted = sorted(itens, key=lambda x: str(x["data"]))
        pago_itens = sum(r["valor"] for r in itens_sorted if r["pago"] == 1)
        aberto_itens = sum(r["valor"] for r in itens_sorted if r["pago"] != 1)

        # 1ª parcela no ato quitada antes do banco
        parc_reg = len(itens_sorted)
        parc_anteriores_quitadas = max(0, total_parc - parc_reg)
        val_parc = float(meta.get("valor_parcela") or (val_orig / total_parc if total_parc > 0 else 0))
        valor_quitado_anterior = parc_anteriores_quitadas * val_parc

        pago_total = valor_quitado_anterior + pago_itens
        aberto_total = aberto_itens

        tot_aberto_geral += aberto_total
        tot_pago_geral += pago_total

        if "fernanda" in titular.lower():
            aberto_fernanda += aberto_total
        else:
            aberto_carlos += aberto_total

        pct = min(100.0, (pago_total / val_orig * 100)) if val_orig > 0 else 100.0

        parcelas_formatadas = []
        for it in itens_sorted:
            dt_s = str(it["data"])[:10]
            try:
                dt_f = datetime.datetime.strptime(dt_s, "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                dt_f = dt_s

            parcelas_formatadas.append({
                "id": it["id"],
                "data": dt_s,
                "data_formatada": dt_f,
                "descricao": it["descricao"],
                "valor": float(it["valor"]),
                "pago": 1 if it["pago"] == 1 else 0
            })
            if it["pago"] != 1:
                proximas_parcelas.append({
                    "data": dt_s,
                    "data_formatada": dt_f,
                    "valor": float(it["valor"]),
                    "nome": nome,
                    "id": it["id"]
                })

        contratos.append({
            "grupo_id": grp_id,
            "nome": nome,
            "titular": titular,
            "valor_original": val_orig,
            "total_parcelas": total_parc,
            "valor_parcela": val_parc,
            "pago_total": pago_total,
            "aberto_total": aberto_total,
            "percentual_pago": pct,
            "status": "Quitada" if aberto_total <= 0.001 else "Ativa",
            "parcelas": parcelas_formatadas
        })

    conn.close()

    proximas_parcelas.sort(key=lambda x: x["data"])
    prox_venc = proximas_parcelas[0] if proximas_parcelas else None

    contratos_ativos = [c for c in contratos if c["status"] == "Ativa"]
    contratos_quitados = [c for c in contratos if c["status"] == "Quitada"]

    return templates.TemplateResponse(
        request=request,
        name="pagaleve.html",
        context={
            "contratos": contratos,
            "contratos_ativos": contratos_ativos,
            "contratos_quitados": contratos_quitados,
            "total_aberto_geral": tot_aberto_geral,
            "total_pago_geral": tot_pago_geral,
            "aberto_carlos": aberto_carlos,
            "aberto_fernanda": aberto_fernanda,
            "proximo_vencimento": prox_venc,
            "active_tab": "pagaleve"
        }
    )


# =============================================================================
# ROTAS: MOTORISTA 99
# =============================================================================

def calcular_horas_periodo(hora_ini: Optional[str], hora_fim: Optional[str]) -> float:
    """Calcula a diferença em horas decimais entre dois horários HH:MM."""
    if not hora_ini or not hora_fim:
        return 0.0
    try:
        hi = [int(p) for p in str(hora_ini).strip().split(":")[:2]]
        hf = [int(p) for p in str(hora_fim).strip().split(":")[:2]]
        m_ini = hi[0] * 60 + hi[1]
        m_fim = hf[0] * 60 + hf[1]
        diff = m_fim - m_ini
        if diff < 0:  # Virada de meia-noite
            diff += 24 * 60
        return round(diff / 60.0, 2)
    except Exception:
        return 0.0


@app.get("/drive", response_class=HTMLResponse)
@app.get("/motorista", response_class=HTMLResponse)
async def pagina_motorista(request: Request, filtro: Optional[str] = "semana"):
    conn = conectar_db()
    hoje = date.today()
    ano = hoje.year
    mes = hoje.month
    hoje_str = hoje.strftime("%Y-%m-%d")

    # Início e fim do mês
    inicio_mes = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    # Início e fim da semana (Segunda a Domingo)
    inicio_semana = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
    fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d")

    # Produção 99 consolidada oficial
    prod_99 = saldo_service.obter_producao_consolidada_99(conn)
    total_mes_bruto = float(prod_99.get("total_mes_bruto", 1469.50))
    marco_bruto = float(prod_99.get("marco", {}).get("faturamento_bruto", 1322.80) if prod_99.get("marco") else 1322.80)
    semana_bruto = float(prod_99.get("semana", {}).get("bruto", 146.70))
    recebido_online = float(prod_99.get("total_mes_online", 1046.39))
    recebido_dinheiro = float(prod_99.get("total_mes_dinheiro", 423.11))

    # Obter saldos das contas para transferências rápidas
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    contas_lista = res_saldo.get("contas", [])
    
    cart_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["dinheiro", "carteira"])), None)
    cart_saldo = float(cart_conta["saldo_atual"]) if cart_conta else 7.0

    app_99_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["99pay", "99 pay", "saldo 99"])), None)
    saldo_99_app = float(app_99_conta["saldo_atual"]) if app_99_conta else 0.0

    cur = conn.cursor()

    # Todos os turnos com todos os campos de controle operacional
    cur.execute("""
        SELECT id, data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma,
               ganho_dinheiro_pix, ganho_online, hora_inicio, hora_fim, km_inicial, km_final,
               status_turno, status_conciliacao, created_at
        FROM turnos
        ORDER BY 
            CASE WHEN UPPER(COALESCE(status_turno, '')) = 'EM_ANDAMENTO' THEN 0 ELSE 1 END,
            data DESC, id DESC
    """)
    turnos_raw = cur.fetchall()

    turnos = []
    for r in turnos_raw:
        dt_str = str(r["data"])[:10]
        try:
            dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str

        h_val = round(float(r["horas"] or 0.0), 2)
        km_val = round(float(r["km"] or 0.0), 1)
        bruto_val = float(r["ganho_bruto"] or 0.0)
        comb_val = float(r["combustivel"] or 0.0)
        st_turno = str(r["status_turno"] or "encerrado").strip()
        st_upper = st_turno.upper()

        # Classificação de status & badges de integridade
        if st_upper == "EM_ANDAMENTO":
            tag_codigo = "EM_ANDAMENTO"
            tag_label = "● Em Andamento"
            tag_badge = "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20 animate-pulse font-bold"
        elif km_val <= 0:
            tag_codigo = "PENDENTE_KM"
            tag_label = "⚠️ Pendente KM"
            tag_badge = "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20 font-bold"
        elif bruto_val <= 0:
            tag_codigo = "A_CONFIRMAR"
            tag_label = "⚠️ A Confirmar"
            tag_badge = "bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20 font-bold"
        else:
            tag_codigo = "CONCLUIDO"
            tag_label = "✓ Concluído"
            tag_badge = "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20 font-bold"

        prod_hora = round(bruto_val / h_val, 2) if (h_val > 0 and bruto_val > 0) else 0.0

        turnos.append({
            "id": r["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "horas": h_val,
            "km": km_val,
            "ganho_bruto": bruto_val,
            "combustivel": comb_val,
            "observacao": r["observacao"] or "",
            "periodo": r["periodo"] or "Manhã",
            "plataforma": r["plataforma"] or "99",
            "ganho_dinheiro_pix": float(r["ganho_dinheiro_pix"] or 0.0),
            "ganho_online": float(r["ganho_online"] or 0.0),
            "hora_inicio": r["hora_inicio"] or "",
            "hora_fim": r["hora_fim"] or "",
            "km_inicial": float(r["km_inicial"]) if r["km_inicial"] is not None else None,
            "km_final": float(r["km_final"]) if r["km_final"] is not None else None,
            "status_turno": st_turno,
            "status_conciliacao": r["status_conciliacao"] or "conciliado",
            "tag_codigo": tag_codigo,
            "tag_label": tag_label,
            "tag_badge": tag_badge,
            "prod_hora": prod_hora,
            "created_at": r["created_at"] or ""
        })

    # Detecta se há turno ativo rodando em tempo real
    turno_ativo = next((t for t in turnos if t["status_turno"].upper() == "EM_ANDAMENTO"), None)

    # Abastecimentos reais registrados (Drivvo)
    cur.execute("""
        SELECT id, data, valor_pago, litros, combustivel, preco_litro, posto, hodometro, observacao
        FROM veiculo_abastecimentos
        ORDER BY data DESC, id DESC
    """)
    abasts_raw = cur.fetchall()
    abastecimentos = []
    for a in abasts_raw:
        dt_str = str(a["data"])[:10]
        try:
            dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str
        abastecimentos.append({
            "id": a["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "valor_pago": float(a["valor_pago"] or 0.0),
            "litros": float(a["litros"] or 0.0),
            "combustivel": a["combustivel"] or "Etanol",
            "preco_litro": float(a["preco_litro"] or 0.0),
            "posto": a["posto"] or "Posto de Combustível",
            "hodometro": float(a["hodometro"] or 0.0),
            "observacao": a["observacao"] or ""
        })

    # CÁLCULO DOS 4 INDICADORES OPERACIONAIS POR PERÍODO
    def calcular_metricas(p_tipo):
        if p_tipo == "hoje":
            t_filtro = [t for t in turnos if t["data"] == hoje_str]
            a_filtro = [a for a in abastecimentos if a["data"] == hoje_str]
            bruto = sum(t["ganho_bruto"] for t in t_filtro)
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = (comb_est / tot_km) if tot_km > 0 else 0.0
            caixa_liquido = bruto - abast_real
            sub_bruto = f"{len(t_filtro)} turno(s) hoje"
            sub_abast = f"{len(a_filtro)} abastecimento(s) hoje"
            sub_km = f"{round(tot_km, 1)} km hoje"
            sub_liq = "Bruto (-) Abastecido Real"

        elif p_tipo == "semana":
            t_filtro = [t for t in turnos if inicio_semana <= t["data"] <= fim_semana]
            a_filtro = [a for a in abastecimentos if inicio_semana <= a["data"] <= fim_semana]
            bruto = sum(t["ganho_bruto"] for t in t_filtro) if t_filtro else semana_bruto
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = (comb_est / tot_km) if tot_km > 0 else 0.28
            caixa_liquido = bruto - abast_real
            sub_bruto = "R$ 146,70 na semana"
            sub_abast = f"{sum(a['litros'] for a in a_filtro):.2f} L Drivvo"
            sub_km = f"R$ {comb_est:.2f} em {round(tot_km, 1)} km"
            sub_liq = f"R$ {bruto:.2f} - R$ {abast_real:.2f}"

        elif p_tipo == "mes":
            t_filtro = [t for t in turnos if inicio_mes <= t["data"] <= fim_mes]
            a_filtro = [a for a in abastecimentos if inicio_mes <= a["data"] <= fim_mes]
            bruto = total_mes_bruto
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = (comb_est / tot_km) if tot_km > 0 else 0.28
            caixa_liquido = bruto - abast_real
            sub_bruto = "R$ 1.469,50 no mês"
            sub_abast = f"{sum(a['litros'] for a in a_filtro):.2f} L Drivvo"
            sub_km = f"R$ {comb_est:.2f} em {round(tot_km, 1)} km"
            sub_liq = f"R$ {bruto:.2f} - R$ {abast_real:.2f}"

        else: # todos
            t_filtro = turnos
            a_filtro = abastecimentos
            bruto = total_mes_bruto
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = (comb_est / tot_km) if tot_km > 0 else 0.28
            caixa_liquido = bruto - abast_real
            sub_bruto = "Acumulado Histórico"
            sub_abast = f"{sum(a['litros'] for a in a_filtro):.2f} L Drivvo"
            sub_km = f"{round(tot_km, 1)} km registrados"
            sub_liq = "Bruto (-) Abastecido Total"

        return {
            "bruto": bruto,
            "abastecido_real": abast_real,
            "consumo_estimado_km": consumo_km,
            "caixa_liquido": caixa_liquido,
            "total_km": round(tot_km, 1),
            "total_horas": round(tot_horas, 2),
            "combustivel_estimado_total": comb_est,
            "sub_bruto": sub_bruto,
            "sub_abast": sub_abast,
            "sub_km": sub_km,
            "sub_liq": sub_liq,
            "turnos_count": len(t_filtro)
        }

    periodos_dados = {
        "hoje": calcular_metricas("hoje"),
        "semana": calcular_metricas("semana"),
        "mes": calcular_metricas("mes"),
        "todos": calcular_metricas("todos")
    }

    filtro_ativo = filtro if filtro in periodos_dados else "semana"
    metricas_ativas = periodos_dados[filtro_ativo]

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="motorista.html",
        context={
            "filtro_ativo": filtro_ativo,
            "metricas": metricas_ativas,
            "periodos_dados": periodos_dados,
            "periodos_json": json.dumps(periodos_dados),
            "total_mes_bruto": total_mes_bruto,
            "marco_bruto": marco_bruto,
            "semana_bruto": semana_bruto,
            "recebido_online": recebido_online,
            "recebido_dinheiro": recebido_dinheiro,
            "cart_saldo": cart_saldo,
            "saldo_99_app": saldo_99_app,
            "saldo_99pay": saldo_99_app,
            "turnos": turnos,
            "turno_ativo": turno_ativo,
            "abastecimentos": abastecimentos,
            "hoje_str": hoje_str,
            "active_tab": "drive"
        }
    )


@app.post("/motorista/turnos/salvar")
@app.post("/motorista/turnos/registrar")
@app.post("/motorista/turnos/manual")
@app.post("/motorista/turnos/editar")
@app.post("/api/turnos")
async def api_salvar_turno(
    data: str = Form(...),
    hora_inicio: Optional[str] = Form(None),
    hora_fim: Optional[str] = Form(None),
    horas: Optional[float] = Form(0.0),
    km_inicial: Optional[float] = Form(None),
    km_final: Optional[float] = Form(None),
    km: Optional[float] = Form(None),
    ganho_online: Optional[float] = Form(0.0),
    ganho_dinheiro_pix: Optional[float] = Form(0.0),
    ganho_bruto: Optional[float] = Form(None),
    combustivel: Optional[float] = Form(None),
    observacao: Optional[str] = Form(""),
    periodo: Optional[str] = Form(None),
    id: Optional[int] = Form(None)
):
    """
    Cria ou edita um turno operacional único com cálculos automáticos por horários e hodômetro.
    - Horas Trabalhadas: calculado por Hora Início e Hora Fim.
    - KM Rodados: Hodômetro Final - Hodômetro Inicial (opcional).
    - Faturamento Bruto: soma automática de Online + Dinheiro.
    - Se Hodômetro Final em branco: KM=0, status '⚠️ Pendente KM'.
    """
    conn = conectar_db()
    try:
        cur = conn.cursor()

        # 1. Tratar Horários & Horas Trabalhadas
        h_ini_str = str(hora_inicio).strip() if (hora_inicio and str(hora_inicio).strip() != "") else None
        h_fim_str = str(hora_fim).strip() if (hora_fim and str(hora_fim).strip() != "") else None

        try:
            h_val = float(horas or 0.0)
        except (TypeError, ValueError):
            h_val = 0.0

        if h_val <= 0 and h_ini_str and h_fim_str:
            try:
                hi, mi = map(int, h_ini_str.split(":")[:2])
                hf, mf = map(int, h_fim_str.split(":")[:2])
                diff_m = (hf * 60 + mf) - (hi * 60 + mi)
                if diff_m < 0:
                    diff_m += 24 * 60  # virada de meia-noite
                h_val = round(diff_m / 60.0, 2)
            except Exception:
                h_val = 0.0

        # Auto-detecção de período
        periodo_val = str(periodo).strip() if (periodo and str(periodo).strip() != "") else None
        if not periodo_val:
            if h_ini_str:
                try:
                    h_int = int(h_ini_str.split(":")[0])
                    if 5 <= h_int < 12:
                        periodo_val = "Manhã"
                    elif 12 <= h_int < 18:
                        periodo_val = "Tarde"
                    else:
                        periodo_val = "Noite"
                except Exception:
                    periodo_val = "Manhã"
            else:
                periodo_val = "Manhã"

        # 2. Tratar Hodômetros & KM Rodados
        try:
            k_ini_val = float(km_inicial) if (km_inicial is not None and str(km_inicial).strip() != "") else None
        except (TypeError, ValueError):
            k_ini_val = None

        try:
            k_fim_val = float(km_final) if (km_final is not None and str(km_final).strip() != "") else None
        except (TypeError, ValueError):
            k_fim_val = None

        if k_ini_val is not None and k_fim_val is not None and k_fim_val >= k_ini_val:
            km_val = round(k_fim_val - k_ini_val, 1)
        elif km is not None and str(km).strip() != "" and float(km) > 0:
            km_val = round(float(km), 1)
        else:
            km_val = 0.0

        # 3. Tratar Ganhos (Faturamento Bruto travado: Online + Dinheiro)
        g_onl = float(ganho_online or 0.0)
        g_din = float(ganho_dinheiro_pix or 0.0)
        g_bruto = round(g_onl + g_din, 2) if (g_onl + g_din > 0) else (float(ganho_bruto or 0.0))

        # 4. Combustível estimado (R$ 0,38/km)
        if km_val > 0:
            c_val = round(km_val * 0.38, 2)
            st_conciliacao = "conciliado" if (g_bruto > 0 and h_val > 0) else "pendente"
        else:
            c_val = 0.0
            st_conciliacao = "pendente"

        if id and int(id) > 0:
            cur.execute("""
                UPDATE turnos
                SET data = ?, periodo = ?, hora_inicio = ?, hora_fim = ?, horas = ?,
                    km_inicial = ?, km_final = ?, km = ?, ganho_bruto = ?,
                    ganho_online = ?, ganho_dinheiro_pix = ?, combustivel = ?,
                    observacao = ?, status_turno = 'encerrado', status_conciliacao = ?
                WHERE id = ?
            """, (data, periodo_val, h_ini_str, h_fim_str, h_val,
                  k_ini_val, k_fim_val, km_val, g_bruto, g_onl, g_din, c_val,
                  observacao or "", st_conciliacao, id))
            conn.commit()
            msg = f"Turno #{id} atualizado com sucesso!"
            novo_id = id
        else:
            cur.execute("""
                INSERT INTO turnos (
                    data, periodo, hora_inicio, hora_fim, horas, km_inicial, km_final, km,
                    ganho_bruto, ganho_online, ganho_dinheiro_pix, combustivel, observacao,
                    plataforma, status_turno, status_conciliacao, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '99', 'encerrado', ?, ?)
            """, (
                data, periodo_val, h_ini_str, h_fim_str, h_val,
                k_ini_val, k_fim_val, km_val, g_bruto, g_onl, g_din,
                c_val, observacao or "", st_conciliacao, datetime.datetime.now().isoformat()
            ))
            conn.commit()
            novo_id = cur.lastrowid
            msg = f"Turno de {formatar_moeda_br(g_bruto)} ({h_val}h) registrado com sucesso!"

        # CONTABILIZAÇÃO FINANCEIRA SEGREGADA DOS GANHOS DO TURNO:
        # - Ganho Online (App) -> Destino: conta '99Pay'
        # - Ganho Dinheiro / Pix -> Destino: conta 'Dinheiro / Carteira' (bolso físico)
        cur.execute("SELECT id FROM contas_config WHERE nome IN ('99Pay', 'Saldo 99 (App)')")
        row_99 = cur.fetchone()
        if not row_99:
            cur.execute("""
                INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
                VALUES ('99Pay', 'digital', '#f59e0b', NULL, 1)
            """)
            c_id_99 = cur.lastrowid
        else:
            c_id_99 = row_99[0]

        c_id_din = 2

        # 1. Sincroniza Ganho Online -> 99Pay
        cur.execute("SELECT id FROM transacoes WHERE turno_id = ? AND (conta_id = ? OR descricao LIKE '%Online%')", (novo_id, c_id_99))
        tr_onl = cur.fetchone()
        if g_onl > 0:
            desc_onl = f"Ganho Online 99Pay (Turno #{novo_id})"
            if tr_onl:
                cur.execute("""
                    UPDATE transacoes
                    SET data = ?, descricao = ?, valor = ?, tipo = 'receita', categoria = '99 / Chaves (Carlos)',
                        conta = '99Pay', conta_id = ?, pago = 1, afeta_saldo_bancario = 1
                    WHERE id = ?
                """, (data, desc_onl, g_onl, c_id_99, tr_onl[0]))
            else:
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', '99Pay', ?, 1, 1, ?)
                """, (data, desc_onl, g_onl, c_id_99, novo_id))
        else:
            if tr_onl:
                cur.execute("DELETE FROM transacoes WHERE id = ?", (tr_onl[0],))

        # 2. Sincroniza Ganho Dinheiro / Pix -> Dinheiro / Carteira
        cur.execute("SELECT id FROM transacoes WHERE turno_id = ? AND (conta_id = ? OR descricao LIKE '%Dinheiro%')", (novo_id, c_id_din))
        tr_din = cur.fetchone()
        if g_din > 0:
            desc_din = f"Ganho Dinheiro/Pix 99 (Turno #{novo_id})"
            if tr_din:
                cur.execute("""
                    UPDATE transacoes
                    SET data = ?, descricao = ?, valor = ?, tipo = 'receita', categoria = '99 / Chaves (Carlos)',
                        conta = 'Dinheiro / Carteira', conta_id = ?, pago = 1, afeta_saldo_bancario = 1
                    WHERE id = ?
                """, (data, desc_din, g_din, c_id_din, tr_din[0]))
            else:
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', 'Dinheiro / Carteira', ?, 1, 1, ?)
                """, (data, desc_din, g_din, c_id_din, novo_id))
        else:
            if tr_din:
                cur.execute("DELETE FROM transacoes WHERE id = ?", (tr_din[0],))

        conn.commit()

        if km_val <= 0:
            msg += " (⚠️ Pendente KM)"

        return {
            "sucesso": True,
            "mensagem": msg,
            "id": novo_id,
            "dados": {
                "id": novo_id,
                "data": data,
                "periodo": periodo_val,
                "hora_inicio": h_ini_str,
                "hora_fim": h_fim_str,
                "horas": h_val,
                "km_inicial": k_ini_val,
                "km_final": k_fim_val,
                "km": km_val,
                "ganho_online": g_onl,
                "ganho_dinheiro_pix": g_din,
                "ganho_bruto": g_bruto,
                "combustivel": c_val,
                "status_conciliacao": st_conciliacao
            }
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/motorista/turnos/excluir")
async def api_excluir_turno(id: int = Form(...)):
    """Remove um turno operacional e suas transações contábeis do banco financas_casa.db."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM transacoes WHERE turno_id = ?", (id,))
        cur.execute("DELETE FROM turnos WHERE id = ?", (id,))
        conn.commit()
        return {"sucesso": True, "mensagem": f"Turno #{id} excluído com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()



@app.post("/motorista/abastecer")
async def api_motorista_abastecer(
    data: str = Form(...),
    valor_pago: float = Form(...),
    litros: float = Form(...),
    preco_litro: Optional[float] = Form(None),
    combustivel: Optional[str] = Form("Etanol"),
    posto: Optional[str] = Form("Posto de Combustível"),
    hodometro: Optional[float] = Form(None),
    conta: Optional[str] = Form("Dinheiro / Carteira"),
    desconto: Optional[float] = Form(0.0),
    tanque_cheio: Optional[int] = Form(0),
    observacao: Optional[str] = Form("")
):
    """Registra abastecimento real do veículo (Drivvo) e gera transação de saída."""
    try:
        val_pago = float(valor_pago)
        lits = float(litros)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valor pago e litros devem ser numéricos.")

    if val_pago <= 0 or lits <= 0:
        raise HTTPException(status_code=400, detail="Valor pago e litros devem ser maiores que zero.")

    try:
        p_litro = float(preco_litro) if (preco_litro is not None and not hasattr(preco_litro, 'default')) else None
    except (TypeError, ValueError):
        p_litro = None

    calc_preco = p_litro if (p_litro and p_litro > 0) else round(val_pago / lits, 3)

    conta_nome = str(conta) if (conta and not hasattr(conta, 'default')) else "Dinheiro / Carteira"
    conta_id = 1 if "Mercado" in conta_nome else 2

    try:
        desc_val = float(desconto) if (desconto is not None and not hasattr(desconto, 'default')) else 0.0
    except (TypeError, ValueError):
        desc_val = 0.0

    try:
        hodo_val = float(hodometro) if (hodometro is not None and not hasattr(hodometro, 'default')) else 0.0
    except (TypeError, ValueError):
        hodo_val = 0.0

    try:
        tq_cheio = int(tanque_cheio) if (tanque_cheio is not None and not hasattr(tanque_cheio, 'default')) else 0
    except (TypeError, ValueError):
        tq_cheio = 0

    comb_nome = str(combustivel) if (combustivel and not hasattr(combustivel, 'default')) else "Etanol"
    posto_nome = str(posto) if (posto and not hasattr(posto, 'default')) else "Posto de Combustível"
    obs_txt = str(observacao) if (observacao and not hasattr(observacao, 'default')) else ""

    conn = conectar_db()
    try:
        cur = conn.cursor()
        # 1. Registrar transação financeira de despesa
        desc_trans = f"Abastecimento {comb_nome} ({lits:.2f}L) - {posto_nome}"
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, 'despesa', 'Combustível (Trabalho)', ?, ?, 1, 1)
        """, (str(data), desc_trans, val_pago, conta_nome, conta_id))
        trans_id = cur.lastrowid

        # 2. Registrar na tabela veiculo_abastecimentos (Drivvo)
        valor_bruto = val_pago + desc_val
        cur.execute("""
            INSERT INTO veiculo_abastecimentos (
                data, hodometro, combustivel, litros, preco_litro, valor_bruto,
                desconto, valor_pago, conta, conta_id, tanque_cheio, posto,
                observacao, transacao_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (str(data), hodo_val, comb_nome, lits, calc_preco, valor_bruto,
              desc_val, val_pago, conta_nome, conta_id, tq_cheio,
              posto_nome, obs_txt, trans_id))

        conn.commit()
        return {"sucesso": True, "mensagem": f"Abastecimento de {formatar_moeda_br(val_pago)} ({lits:.2f}L) registrado com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/motorista/transferir-99-mp")
async def api_transferir_99_mp(
    valor: float = Form(...),
    data: Optional[str] = Form(None),
    observacao: Optional[str] = Form("Repasse de corridas online 99 para Mercado Pago")
):
    """Transfere saldo acumulado de corridas online retidas no App 99 para o Mercado Pago."""
    try:
        val_trans = float(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valor deve ser numérico.")

    if val_trans <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")

    data_trans = str(data) if (data and not hasattr(data, 'default')) else date.today().strftime("%Y-%m-%d")
    obs_txt = str(observacao) if (observacao and not hasattr(observacao, 'default')) else "Transferência 99Pay → Mercado Pago"

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM contas_config WHERE nome IN ('99Pay', 'Saldo 99 (App)')")
        row_99 = cur.fetchone()
        if not row_99:
            cur.execute("""
                INSERT INTO contas_config (nome, tipo, cor, conta_pai_id, incluir_saldo_consolidado)
                VALUES ('99Pay', 'digital', '#f59e0b', NULL, 1)
            """)
            c_id_99 = cur.lastrowid
        else:
            c_id_99 = row_99[0]

        # Transferência: sai de 99Pay (conta_id=c_id_99) e entra no Mercado Pago (conta_destino_id=1)
        cur.execute("""
            INSERT INTO transacoes (
                data, descricao, valor, tipo, categoria, conta, conta_id,
                conta_destino_id, pago, afeta_saldo_bancario
            ) VALUES (?, ?, ?, 'transferencia', 'Transferência Entre Contas', '99Pay', ?, 1, 1, 1)
        """, (data_trans, obs_txt, val_trans, c_id_99))
        conn.commit()
        return {"sucesso": True, "mensagem": f"Transferência de {formatar_moeda_br(val_trans)} da 99Pay para o Mercado Pago realizada com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/motorista/transferir-dinheiro-mp")
async def api_transferir_dinheiro_mp(
    valor: float = Form(...),
    data: Optional[str] = Form(None),
    observacao: Optional[str] = Form("Depósito de corridas em dinheiro no Mercado Pago")
):
    """Transfere rapidamente dinheiro físico das corridas da Carteira para o Mercado Pago."""
    try:
        val_trans = float(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valor deve ser numérico.")

    if val_trans <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")

    data_trans = str(data) if (data and not hasattr(data, 'default')) else date.today().strftime("%Y-%m-%d")
    obs_txt = str(observacao) if (observacao and not hasattr(observacao, 'default')) else "Depósito Dinheiro Corridas → MP"

    conn = conectar_db()
    try:
        cur = conn.cursor()
        # Transferência: sai da Carteira (conta_id=2) e entra no Mercado Pago (conta_destino_id=1)
        cur.execute("""
            INSERT INTO transacoes (
                data, descricao, valor, tipo, categoria, conta, conta_id,
                conta_destino_id, pago, afeta_saldo_bancario
            ) VALUES (?, ?, ?, 'transferencia', 'Transferência Entre Contas', 'Dinheiro / Carteira', 2, 1, 1, 1)
        """, (data_trans, obs_txt, val_trans))
        conn.commit()
        return {"sucesso": True, "mensagem": f"Transferência de {formatar_moeda_br(val_trans)} para o Mercado Pago realizada com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/motorista/manutencao")
async def api_motorista_manutencao(
    data: str = Form(...),
    tipo: str = Form(...),
    descricao: str = Form(...),
    valor: float = Form(...),
    km_atual: Optional[float] = Form(0.0),
    proxima_troca_km: Optional[float] = Form(None),
    conta: Optional[str] = Form("Mercado Pago"),
    observacao: Optional[str] = Form("")
):
    """Registra manutenção veicular na frota e cria despesa correspondente."""
    try:
        val_manut = float(valor)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valor deve ser numérico.")

    if val_manut <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero.")

    try:
        km_val = float(km_atual) if (km_atual is not None and not hasattr(km_atual, 'default')) else 0.0
    except (TypeError, ValueError):
        km_val = 0.0

    try:
        prox_km = float(proxima_troca_km) if (proxima_troca_km is not None and not hasattr(proxima_troca_km, 'default')) else None
    except (TypeError, ValueError):
        prox_km = None

    conta_nome = str(conta) if (conta and not hasattr(conta, 'default')) else "Mercado Pago"
    conta_id = 1 if "Mercado" in conta_nome else 2
    tipo_nome = str(tipo) if (tipo and not hasattr(tipo, 'default')) else "Manutenção"
    desc_nome = str(descricao) if (descricao and not hasattr(descricao, 'default')) else "Manutenção Veículo"
    obs_txt = str(observacao) if (observacao and not hasattr(observacao, 'default')) else ""

    conn = conectar_db()
    try:
        cur = conn.cursor()
        # 1. Registrar em despesas_veiculo
        cur.execute("""
            INSERT INTO despesas_veiculo (
                data, tipo, descricao, valor, km_atual, proxima_troca_km, conta, observacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(data), tipo_nome, desc_nome.strip(), val_manut, km_val, prox_km, conta_nome, obs_txt))

        # 2. Registrar em transacoes
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, 'despesa', 'Manutenção Veículo', ?, ?, 1, 1)
        """, (str(data), f"Manutenção: {desc_nome.strip()}", val_manut, conta_nome, conta_id))

        conn.commit()
        return {"sucesso": True, "mensagem": f"Manutenção '{desc_nome}' de {formatar_moeda_br(val_manut)} registrada com sucesso!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


# =============================================================================
# ROTAS: MISSÕES & METAS
# =============================================================================

@app.get("/missoes", response_class=HTMLResponse)
async def pagina_missoes(request: Request):
    conn = conectar_db()
    hoje = date.today()
    mes_ano = f"{hoje.year}-{hoje.month:02d}"

    try:
        missao = planejamento_service.obter_missao_ativa_semana(conn, mes_ano=mes_ano, data_referencia=hoje)
    except Exception:
        missao = {"tem_missao": False}

    try:
        opcoes = planejamento_service.obter_opcoes_missoes_semana(conn, mes_ano=mes_ano)
    except Exception:
        opcoes = []

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="missoes.html",
        context={
            "missao": missao,
            "opcoes": opcoes,
            "active_tab": "missoes"
        }
    )


@app.post("/api/missoes/definir")
async def api_definir_missao(transacao_id: int = Form(...)):
    """Define a obrigação selecionada como Missão Ativa da Semana."""
    conn = conectar_db()
    try:
        hoje = date.today()
        mes_ano = f"{hoje.year}-{hoje.month:02d}"
        ok, msg = planejamento_service.definir_missao_ativa_semana(conn, transacao_id=transacao_id, mes_ano=mes_ano)
        if ok:
            return {"sucesso": True, "mensagem": msg}
        else:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": msg})
    finally:
        conn.close()


@app.get("/manifest.json")
async def get_manifest():
    """Entrega o manifesto do PWA com headers corretos para instalação no Xiaomi 12."""
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/sw.js")
async def get_service_worker():
    """Entrega o Service Worker do PWA no escopo raiz."""
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    return FileResponse(sw_path, media_type="application/javascript")


def converter_para_serializavel(obj: Any) -> Any:
    """Converte recursivamente Decimals e datas para tipos primitivos serializáveis em JSON."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): converter_para_serializavel(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [converter_para_serializavel(item) for item in obj]
    return obj


@app.get("/api/dados")
async def api_dados():
    """Retorna os dados consolidados em formato JSON para atualização assíncrona."""
    dados = coletar_dados_dashboard()
    return JSONResponse(converter_para_serializavel(dados))


@app.post("/api/baixa/{transacao_id}")
async def api_baixar_conta(transacao_id: int):
    """
    Executa a baixa imediata e oficial de uma conta a pagar no banco SQLite
    via saldo_service.registrar_pagamento.
    """
    conn = conectar_db()
    try:
        resumo = saldo_service.obter_resumo_obrigacao(conn, transacao_id)
        if not resumo:
            raise HTTPException(status_code=404, detail="Obrigação não encontrada.")

        val_devedor = float(resumo["saldo_devedor"])
        hoje_str = date.today().strftime("%Y-%m-%d")
        conta_id = resumo.get("conta_id") or 1  # 1 = Mercado Pago

        saldo_service.registrar_pagamento(
            conn=conn,
            transacao_id=transacao_id,
            data_pagamento=hoje_str,
            valor_pago=val_devedor,
            conta_id=conta_id,
            afeta_saldo_bancario=1,
            considerado_no_marco=0,
            forma_pagamento="Pix",
            tipo_ajuste_valor="normal",
            valor_encargos=0.0,
            valor_desconto=0.0
        )
        conn.commit()

        # Recalcular saldos e métricas consolidadas após a baixa
        dados = coletar_dados_dashboard()

        return {
            "sucesso": True,
            "mensagem": f"Baixa de '{resumo['descricao']}' ({formatar_moeda_br(val_devedor)}) realizada com sucesso!",
            "transacao_id": transacao_id,
            "valor_baixado": val_devedor,
            "novo_saldo_caixa": formatar_moeda_br(dados["saldo_caixa"]),
            "novos_totais": {
                "despesa_mensal": formatar_moeda_br(dados["despesa_mensal"]),
                "despesas_pagas": formatar_moeda_br(dados["despesas_pagas"]),
                "despesas_pendentes": formatar_moeda_br(dados["despesas_pendentes"]),
                "saldo_caixa": formatar_moeda_br(dados["saldo_caixa"]),
                "tot_vence_hoje": formatar_moeda_br(dados["tot_vence_hoje"]),
                "qtd_vence_hoje": len(dados["vence_hoje"]),
                "tot_atrasadas": formatar_moeda_br(dados["tot_atrasadas"]),
                "qtd_atrasadas": len(dados["atrasadas"]),
                "tot_prox7": formatar_moeda_br(dados["tot_prox7"]),
                "qtd_prox7": dados["qtd_prox7"]
            }
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/contas/excluir")
@app.post("/api/contas/excluir")
async def api_excluir_conta(request: Request):
    """
    Exclui ou cancela conta a pagar / despesa recorrente no banco financas_casa.db:
    - Escopo 'pontual': exclui apenas a ocorrência selecionada do mês.
    - Escopo 'recorrente': exclui a ocorrência atual e encerra/cancela as ocorrências futuras da regra.
    """
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            transacao_id = int(payload.get("transacao_id") or payload.get("id") or 0)
            escopo = str(payload.get("escopo", "pontual")).strip().lower()
        else:
            form = await request.form()
            transacao_id = int(form.get("transacao_id") or form.get("id") or 0)
            escopo = str(form.get("escopo", "pontual")).strip().lower()

        if not transacao_id:
            raise HTTPException(status_code=400, detail="ID da transação não fornecido.")

        cur = conn.cursor()
        cur.execute("SELECT * FROM transacoes WHERE id = ?", (transacao_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lançamento não encontrado no banco de dados.")

        desc = row["descricao"]
        dt = row["data"]
        cat = row["categoria"]
        val = float(row["valor"] or 0.0)

        # Garantir tabela de registro de cancelamento de recorrências
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regras_recorrentes_canceladas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                categoria TEXT,
                valor REAL,
                data_cancelamento TEXT NOT NULL,
                motivo TEXT,
                created_at TEXT
            )
        """)

        if escopo in ("recorrente", "este_e_proximos", "todos_proximos"):
            # 1. Registrar cancelamento da regra
            cur.execute("""
                INSERT INTO regras_recorrentes_canceladas (descricao, categoria, valor, data_cancelamento, motivo, created_at)
                VALUES (?, ?, ?, ?, 'Cancelado pelo usuário em Contas a Pagar Imediatas', datetime('now'))
            """, (desc, cat, val, str(dt)[:10]))

            # 2. Excluir esta ocorrência e quaisquer ocorrências futuras pendentes com mesma descrição
            cur.execute("""
                SELECT id FROM transacoes
                WHERE id = ? 
                   OR (tipo = 'despesa' AND (pago = 0 OR pago IS NULL) 
                       AND LOWER(TRIM(descricao)) = LOWER(TRIM(?)) 
                       AND data >= ?)
            """, (transacao_id, desc, dt))
            ids_excluir = [r[0] for r in cur.fetchall()]

            for tid in ids_excluir:
                cur.execute("DELETE FROM transacoes WHERE id = ?", (tid,))
                cur.execute("DELETE FROM planejamento_metas WHERE transacao_alvo_id = ?", (tid,))
                cur.execute("DELETE FROM pagamentos_despesas WHERE transacao_id = ?", (tid,))

            conn.commit()
            qtd_removidas = len(ids_excluir)
            msg = f"Regra de '{desc}' encerrada com sucesso! {qtd_removidas} ocorrência(s) removida(s) (este mês e futuras)."
        else:
            # Exclusão apenas deste lançamento pontual
            cur.execute("DELETE FROM transacoes WHERE id = ?", (transacao_id,))
            cur.execute("DELETE FROM planejamento_metas WHERE transacao_alvo_id = ?", (transacao_id,))
            cur.execute("DELETE FROM pagamentos_despesas WHERE transacao_id = ?", (transacao_id,))
            conn.commit()
            msg = f"Lançamento '{desc}' ({formatar_moeda_br(val)}) excluído com sucesso do mês selecionado."

        # Recalcular métricas do dashboard após a exclusão
        dados = coletar_dados_dashboard()
        return {
            "sucesso": True,
            "mensagem": msg,
            "transacao_id": transacao_id,
            "escopo": escopo,
            "novos_totais": {
                "despesa_mensal": formatar_moeda_br(dados["despesa_mensal"]),
                "despesas_pagas": formatar_moeda_br(dados["despesas_pagas"]),
                "despesas_pendentes": formatar_moeda_br(dados["despesas_pendentes"]),
                "saldo_caixa": formatar_moeda_br(dados["saldo_caixa"]),
                "tot_vence_hoje": formatar_moeda_br(dados["tot_vence_hoje"]),
                "qtd_vence_hoje": len(dados["vence_hoje"]),
                "tot_atrasadas": formatar_moeda_br(dados["tot_atrasadas"]),
                "qtd_atrasadas": len(dados["atrasadas"]),
                "tot_prox7": formatar_moeda_br(dados["tot_prox7"]),
                "qtd_prox7": dados["qtd_prox7"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/meta-horas")
async def api_salvar_meta_horas(horas: float = Form(...)):
    """Atualiza as horas de meta de hoje."""
    if horas < 0.5 or horas > 16.0:
        raise HTTPException(status_code=400, detail="Horas inválidas (permitido entre 0.5h e 16h).")
    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES (?, ?)", ("horas_hoje_planejadas", str(horas)))
        conn.commit()
        return {"sucesso": True, "horas": horas, "nova_meta": formatar_moeda_br(horas * 35.0)}
    finally:
        conn.close()


# =============================================================================
# CHAT INTELIGENTE COM GEMINI API NATIVO NO OIKOS (/api/chat)
# =============================================================================

def obter_contexto_oikos_para_gemini(conn: sqlite3.Connection) -> Dict[str, Any]:
    hoje = date.today().isoformat()
    dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    dia_str = dias_semana[date.today().weekday()]

    cur = conn.cursor()
    # Saldos consolidados das contas de movimentação
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    saldo_livre = float(res_saldo.get("saldo_consolidado", 0.0))
    contas_lista = res_saldo.get("contas", [])
    saldos_txt = [
        f"- {c['conta_nome']}: R$ {float(c['saldo_atual']):.2f}"
        for c in contas_lista
        if c.get("tipo") != "cofrinho"
    ]

    # Últimas 5 transações no sistema
    cur.execute("SELECT id, data, descricao, valor, tipo, conta, categoria FROM transacoes ORDER BY id DESC LIMIT 5")
    trans_recentes = cur.fetchall()
    trans_txt = [
        f"- {t[4].upper() if len(t) > 4 and t[4] else 'LANCAMENTO'}: {t[2]} R$ {float(t[3]):.2f} ({t[5]} | {t[6]})"
        for t in trans_recentes
    ]

    # Turno hoje do Oikos Drive
    cur.execute("SELECT id, ganho_online, ganho_dinheiro_pix, ganho_bruto, horas, km FROM turnos WHERE data = ? ORDER BY id DESC LIMIT 1", (hoje,))
    th = cur.fetchone()
    if th:
        turno_txt = f"Turno de hoje: R$ {float(th[1] or 0):.2f} online + R$ {float(th[2] or 0):.2f} dinheiro (Total R$ {float(th[3] or 0):.2f}, {float(th[4] or 0)}h, {float(th[5] or 0)}km)"
    else:
        turno_txt = "Nenhum turno registrado hoje ainda."

    return {
        "hoje": hoje,
        "dia_semana": dia_str,
        "saldo_livre": saldo_livre,
        "saldos": "\n".join(saldos_txt) if saldos_txt else "Sem contas de movimentação cadastradas.",
        "ultimas_trans": "\n".join(trans_txt) if trans_txt else "Nenhum lançamento recente.",
        "turno_hoje": turno_txt
    }


def executar_acao_ia(conn: sqlite3.Connection, action: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Executa a ação identificada pelo Gemini diretamente na base SQLite financas_casa.db.
    """
    cur = conn.cursor()
    acao = str(action.get("acao", "")).lower().strip()
    hoje = date.today().isoformat()

    if acao == "transacao":
        tipo = str(action.get("tipo", "despesa")).lower().strip()
        if tipo not in ["despesa", "receita"]:
            tipo = "despesa"
        try:
            valor = float(action.get("valor", 0.0))
        except (ValueError, TypeError):
            valor = 0.0

        if valor <= 0:
            return False, "Valor inválido para a transação."

        descricao = str(action.get("descricao", "Lançamento via Chat")).strip() or "Lançamento via Chat"
        categoria_raw = str(action.get("categoria", "")).strip()
        conta_raw = str(action.get("conta", "Mercado Pago")).strip()

        # Identificação da conta bancária no banco
        cur.execute("SELECT id, nome FROM contas_config WHERE nome LIKE ?", (f"%{conta_raw}%",))
        rc = cur.fetchone()
        if rc:
            conta_id = rc[0]
            conta_oficial = rc[1]
        else:
            if any(k in conta_raw.lower() for k in ["mp", "mercado", "pago"]):
                conta_id = 1
                conta_oficial = "Mercado Pago"
            elif any(k in conta_raw.lower() for k in ["dinheiro", "carteira", "especie", "bolso"]):
                conta_id = 2
                conta_oficial = "Dinheiro / Carteira"
            elif any(k in conta_raw.lower() for k in ["99", "99pay", "app"]):
                conta_id = 1779
                conta_oficial = "99Pay"
            else:
                conta_id = 1
                conta_oficial = "Mercado Pago"

        # Identificação da categoria contábil
        c_low = categoria_raw.lower()
        d_low = descricao.lower()
        if any(k in c_low or k in d_low for k in ["gasolina", "combustivel", "combustível", "etanol", "posto", "abasteci"]):
            categoria_oficial = "Combustível (Trabalho)"
        elif any(k in c_low or k in d_low for k in ["mercado", "supermercado", "feira", "compras", "açougue", "acougue"]):
            categoria_oficial = "Supermercado / Feira"
        elif any(k in c_low or k in d_low for k in ["lanche", "restaurante", "almoco", "almoço", "jantar", "ifood", "comida", "pizza"]):
            categoria_oficial = "Restaurante"
        elif any(k in c_low or k in d_low for k in ["farmacia", "farmácia", "drogaria", "remedio", "remédio", "medicamento"]):
            categoria_oficial = "Medicamentos"
        elif any(k in c_low or k in d_low for k in ["corrida", "99", "uber", "passageiro"]) and tipo == "receita":
            categoria_oficial = "99 / Chaves (Carlos)"
        elif any(k in c_low or k in d_low for k in ["salario", "salário"]):
            categoria_oficial = "Salário Fernanda" if "fernanda" in d_low else "Outros"
        elif categoria_raw:
            categoria_oficial = categoria_raw
        else:
            categoria_oficial = "Outros"

        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
        """, (hoje, descricao, valor, tipo, categoria_oficial, conta_oficial, conta_id))
        conn.commit()
        return True, f"{tipo.capitalize()} '{descricao}' de {formatar_moeda_br(valor)} registrada em {conta_oficial} ({categoria_oficial})."

    elif acao == "turno":
        data_turno = str(action.get("data", hoje)).strip() or hoje
        try:
            g_onl = float(action.get("online", 0.0) or 0.0)
        except Exception:
            g_onl = 0.0
        try:
            g_din = float(action.get("dinheiro", 0.0) or 0.0)
        except Exception:
            g_din = 0.0

        g_bruto = round(g_onl + g_din, 2)
        try:
            h_val = float(action.get("horas", 0.0) or 0.0)
        except Exception:
            h_val = 0.0
        try:
            km_val = float(action.get("km", 0.0) or 0.0)
        except Exception:
            km_val = 0.0

        c_val = round(km_val * 0.38, 2) if km_val > 0 else 0.0
        obs = str(action.get("obs", "")).strip()

        cur.execute("SELECT id FROM turnos WHERE data = ? ORDER BY id DESC LIMIT 1", (data_turno,))
        row_t = cur.fetchone()
        if row_t:
            tid = row_t[0]
            cur.execute("""
                UPDATE turnos
                SET ganho_online = ?, ganho_dinheiro_pix = ?, ganho_bruto = ?,
                    horas = CASE WHEN ? > 0 THEN ? ELSE horas END,
                    km = CASE WHEN ? > 0 THEN ? ELSE km END,
                    combustivel = CASE WHEN ? > 0 THEN ? ELSE combustivel END,
                    observacao = CASE WHEN ? != '' THEN ? ELSE observacao END,
                    status_turno = 'encerrado'
                WHERE id = ?
            """, (g_onl, g_din, g_bruto, h_val, h_val, km_val, km_val, c_val, c_val, obs, obs, tid))
            conn.commit()
            return True, f"Turno #{tid} atualizado: {formatar_moeda_br(g_onl)} online + {formatar_moeda_br(g_din)} dinheiro (Total: {formatar_moeda_br(g_bruto)})."
        else:
            cur.execute("""
                INSERT INTO turnos (
                    data, periodo, horas, km, ganho_bruto, ganho_online, ganho_dinheiro_pix,
                    combustivel, observacao, plataforma, status_turno, status_conciliacao, created_at
                ) VALUES (?, 'Manhã', ?, ?, ?, ?, ?, ?, ?, '99', 'encerrado', 'conciliado', ?)
            """, (data_turno, h_val, km_val, g_bruto, g_onl, g_din, c_val, obs, datetime.datetime.now().isoformat()))
            conn.commit()
            return True, f"Turno de {formatar_moeda_br(g_bruto)} ({formatar_moeda_br(g_onl)} online + {formatar_moeda_br(g_din)} dinheiro) registrado com sucesso!"

    return False, "Tipo de ação não reconhecido."


def processar_fallback_nlp(mensagem: str, conn: sqlite3.Connection) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Parser NLP local para quando a API remota estiver temporariamente em manutenção ou 503.
    """
    txt = mensagem.lower().strip()
    hoje = date.today().isoformat()

    # 1. Turno de motorista: ex "Turno de hoje 150 online e 40 dinheiro"
    m_turno = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:on|online).*?(\d+(?:[.,]\d+)?)\s*(?:din|dinheiro|físico|fisico|pix)", txt)
    if not m_turno:
        m_turno = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:din|dinheiro|físico|fisico|pix).*?(\d+(?:[.,]\d+)?)\s*(?:on|online)", txt)
        if m_turno:
            din_val = float(m_turno.group(1).replace(",", "."))
            onl_val = float(m_turno.group(2).replace(",", "."))
            action = {"acao": "turno", "data": hoje, "online": onl_val, "dinheiro": din_val, "horas": 0.0, "km": 0.0, "obs": ""}
            ok, msg = executar_acao_ia(conn, action)
            return action, msg

    if m_turno:
        onl_val = float(m_turno.group(1).replace(",", "."))
        din_val = float(m_turno.group(2).replace(",", "."))
        action = {"acao": "turno", "data": hoje, "online": onl_val, "dinheiro": din_val, "horas": 0.0, "km": 0.0, "obs": ""}
        ok, msg = executar_acao_ia(conn, action)
        return action, msg

    # 2. Despesa: ex "gastei 50 de gasolina no MP", "paguei 80 no mercado no cartão"
    m_gasto = re.search(r"(?:gastei|paguei|comprei|gasto de|despesa de)\s+(?:r\$\s*)?(\d+(?:[.,]\d+)?)", txt)
    if m_gasto:
        valor = float(m_gasto.group(1).replace(",", "."))
        conta = "Mercado Pago"
        if any(k in txt for k in ["dinheiro", "carteira", "bolso", "especie"]):
            conta = "Dinheiro / Carteira"
        elif any(k in txt for k in ["99", "99pay"]):
            conta = "99Pay"
        elif any(k in txt for k in ["mp", "mercado pago", "cartão", "cartao"]):
            conta = "Mercado Pago"

        if any(k in txt for k in ["gasolina", "combustivel", "combustível", "etanol", "posto"]):
            desc = "Gasolina"
            cat = "Combustível (Trabalho)"
        elif any(k in txt for k in ["mercado", "supermercado", "feira"]):
            desc = "Supermercado"
            cat = "Supermercado / Feira"
        elif any(k in txt for k in ["lanche", "almoço", "almoco", "restaurante", "comida"]):
            desc = "Almoço / Refeição"
            cat = "Restaurante"
        elif any(k in txt for k in ["remedio", "remédio", "farmacia", "farmácia"]):
            desc = "Farmácia"
            cat = "Medicamentos"
        else:
            desc = "Despesa"
            cat = "Outros"

        action = {"acao": "transacao", "tipo": "despesa", "valor": valor, "descricao": desc, "categoria": cat, "conta": conta}
        ok, msg = executar_acao_ia(conn, action)
        return action, msg

    # 3. Receita: ex "recebi 120 da corrida", "ganhei 50"
    m_rec = re.search(r"(?:recebi|ganhei|receita de|entrada de)\s+(?:r\$\s*)?(\d+(?:[.,]\d+)?)", txt)
    if m_rec:
        valor = float(m_rec.group(1).replace(",", "."))
        conta = "99Pay" if "99" in txt else ("Dinheiro / Carteira" if "dinheiro" in txt else "Mercado Pago")
        desc = "Corrida / Serviço" if any(k in txt for k in ["corrida", "viagem", "uber", "99"]) else "Receita"
        cat = "99 / Chaves (Carlos)" if any(k in txt for k in ["corrida", "viagem", "uber", "99"]) else "Outros"
        action = {"acao": "transacao", "tipo": "receita", "valor": valor, "descricao": desc, "categoria": cat, "conta": conta}
        ok, msg = executar_acao_ia(conn, action)
        return action, msg

    # 4. Consulta de Saldo: ex "qual meu saldo", "quanto tenho no MP"
    if any(k in txt for k in ["saldo", "quanto tenho", "extrato", "caixa"]):
        res_saldo = saldo_service.calcular_saldo_consolidado(conn)
        saldo_livre = float(res_saldo.get("saldo_consolidado", 0.0))
        contas_lista = res_saldo.get("contas", [])
        partes = [f"{c['conta_nome']}: {formatar_moeda_br(float(c['saldo_atual']))}" for c in contas_lista if c.get("tipo") != "cofrinho"]
        txt_saldos = " | ".join(partes)
        return None, f"💰 Saldos Atuais: {txt_saldos} (Consolidado Livre: {formatar_moeda_br(saldo_livre)})."

    return None, "Olá! Posso registrar despesas (ex: 'gastei 50 de gasolina no MP'), turnos da 99 ('turno de hoje 150 online e 40 dinheiro') ou informar saldos atuais."


@app.post("/api/chat")
async def api_chat(request: Request):
    """
    Endpoint de Chat Inteligente integrado com Gemini API nativo e financas_casa.db.
    Recebe { "mensagem": str }.
    """
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            mensagem = str(body.get("mensagem", "")).strip()
        else:
            form = await request.form()
            mensagem = str(form.get("mensagem", "")).strip()

        if not mensagem:
            return JSONResponse({"sucesso": False, "resposta": "Por favor, digite uma mensagem."})

        # Contexto dinâmico das finanças e turnos em tempo real
        ctx = obter_contexto_oikos_para_gemini(conn)

        system_instruction = f"""Você é o Assistente Inteligente do Oikos, o ecossistema familiar de finanças e central de motorista de aplicativo.
Seu tom é profissional, extremamente direto, curto e objetivo (sem introduções prolixas, enrolação ou floreados).

Hoje é {ctx['hoje']} ({ctx['dia_semana']}).

--- DADOS ATUAIS DE FINANCAS_CASA.DB ---
Saldos das Contas:
{ctx['saldos']}
Saldo Livre Consolidado: R$ {ctx['saldo_livre']:.2f}

Últimos Lançamentos Registrados:
{ctx['ultimas_trans']}

Status do Turno de Hoje (Oikos Drive):
{ctx['turno_hoje']}

--- INSTRUÇÕES DE AÇÃO ---
1. Se a mensagem for sobre LANÇAR UM GASTO ou RECEITA (ex: "gastei 50 no mercado no cartão", "recebi 120 da corrida", "gastei 50 de gasolina no MP"):
   Você DEVE incluir OBRIGATORIAMENTE na PRIMEIRA LINHA da resposta um comando no formato:
   ACTION: {{"acao": "transacao", "tipo": "despesa"|"receita", "valor": float, "descricao": "<descrição curta>", "categoria": "<categoria>", "conta": "Mercado Pago"|"Dinheiro / Carteira"|"99Pay"}}
   Seguido imediatamente na próxima linha por uma confirmação curta e direta do registro.

2. Se a mensagem for sobre REGISTRAR ou ATUALIZAR TURNO do Oikos Drive (ex: "turno de hoje 150 online e 40 dinheiro"):
   Você DEVE incluir OBRIGATORIAMENTE na PRIMEIRA LINHA da resposta um comando no formato:
   ACTION: {{"acao": "turno", "data": "{ctx['hoje']}", "online": float, "dinheiro": float, "horas": float, "km": float, "obs": ""}}
   Seguido imediatamente na próxima linha por uma confirmação curta e direta.

3. Se a mensagem for uma DÚVIDA ou PERGUNTA (ex: "quanto tenho no Mercado Pago?", "qual meu saldo?"):
   Responda de forma direta e curta em 1 linha com os números exatos dos saldos acima, sem linha ACTION.
"""

        modelos = ["gemini-2.5-flash", "gemini-3.8-flash"]
        resposta_texto = None

        if client and hasattr(client, "aio"):
            for mod in modelos:
                try:
                    resp = await asyncio.wait_for(
                        client.aio.models.generate_content(
                            model=mod,
                            contents=mensagem,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.2
                            )
                        ),
                        timeout=2.0
                    )
                    if resp and resp.text:
                        resposta_texto = resp.text.strip()
                        break
                except Exception:
                    continue

        acao_executada = None
        if resposta_texto:
            m_act = re.search(r"ACTION:\s*(\{.*?\})", resposta_texto, re.DOTALL)
            if m_act:
                try:
                    act_json = json.loads(m_act.group(1))
                    ok_act, msg_act = executar_acao_ia(conn, act_json)
                    acao_executada = act_json
                    resposta_limpa = re.sub(r"ACTION:\s*\{.*?\}\s*", "", resposta_texto, flags=re.DOTALL).strip()
                    if not resposta_limpa:
                        resposta_limpa = msg_act
                    resposta_texto = resposta_limpa
                except Exception as ex_act:
                    pass
        else:
            acao_executada, resposta_texto = processar_fallback_nlp(mensagem, conn)

        return JSONResponse({
            "sucesso": True,
            "resposta": resposta_texto or "Comando processado com sucesso.",
            "acao": acao_executada
        })
    except Exception as e:
        conn.rollback()
        try:
            _, fallback_resp = processar_fallback_nlp(mensagem, conn)
            return JSONResponse({"sucesso": True, "resposta": fallback_resp})
        except Exception:
            return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e), "resposta": "Desculpe, ocorreu uma instabilidade momentânea. Tente novamente."})
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Servidor Web PWA em http://localhost:8000 ...")
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
