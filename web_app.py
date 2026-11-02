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

# Banco de dados isolado da branch de remodelação
DB_PATH = os.environ.get(
    "OIKOS_DB_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "financas_remodelacao.db"))
)

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
IMAGEM_DIR = os.path.join(BASE_DIR, "Imagem")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(IMAGEM_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/imagem", StaticFiles(directory=IMAGEM_DIR), name="imagem")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
OIKOS_EDICAO_NOME = os.environ.get("OIKOS_EDICAO_NOME", "Pessoal")
templates.env.globals["OIKOS_EDICAO_NOME"] = OIKOS_EDICAO_NOME


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


def formatar_horas_br(val) -> str:
    """Formata valor numérico de horas no padrão brasileiro (ex: 6,0h ou 1,5h)."""
    if val is None or val == "":
        return "0,0h"
    try:
        f = float(val)
        return f"{f:.1f}".replace(".", ",") + "h"
    except Exception:
        return f"{val}h"


def formatar_pct_br(val) -> str:
    """Formata valor percentual no padrão brasileiro (ex: 100% ou 85,5%)."""
    if val is None or val == "":
        return "0%"
    try:
        f = float(val)
        if f == int(f):
            return f"{int(f)}%"
        return f"{f:.1f}".replace(".", ",") + "%"
    except Exception:
        return f"{val}%"


def formatar_numero_br(val, casas: int = 1) -> str:
    """Formata valor numérico decimal com vírgula (ex: 1,5 ou 10)."""
    if val is None or val == "":
        return "0"
    try:
        f = float(val)
        if casas == 0 or f == int(f):
            return str(int(f))
        fmt = f"{{:.{casas}f}}"
        return fmt.format(f).replace(".", ",")
    except Exception:
        return str(val)


templates.env.filters["horas_br"] = formatar_horas_br
templates.env.filters["pct_br"] = formatar_pct_br
templates.env.filters["numero_br"] = formatar_numero_br


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


BANCOS_DISPONIVEIS = [
    {"codigo": "mercadopago.svg", "nome": "Mercado Pago"},
    {"codigo": "99pay.svg", "nome": "99Pay"},
    {"codigo": "carteira.svg", "nome": "Dinheiro / Carteira"},
    {"codigo": "nubank.svg", "nome": "Nubank"},
    {"codigo": "inter.svg", "nome": "Banco Inter"},
    {"codigo": "caixa.svg", "nome": "Caixa Econômica"},
    {"codigo": "itau.svg", "nome": "Itaú"},
    {"codigo": "bradesco.svg", "nome": "Bradesco"},
    {"codigo": "santander.svg", "nome": "Santander"},
    {"codigo": "bb.svg", "nome": "Banco do Brasil"},
    {"codigo": "c6.svg", "nome": "C6 Bank"},
    {"codigo": "picpay.svg", "nome": "PicPay"},
    {"codigo": "pagbank.svg", "nome": "PagBank"},
    {"codigo": "stone.svg", "nome": "Stone"},
    {"codigo": "sicoob.svg", "nome": "Sicoob"},
    {"codigo": "sicredi.svg", "nome": "Sicredi"},
    {"codigo": "cora.svg", "nome": "Cora"},
    {"codigo": "btg.svg", "nome": "BTG Pactual"},
    {"codigo": "xp.svg", "nome": "XP Investimentos"},
    {"codigo": "safra.svg", "nome": "Safra"},
    {"codigo": "bmg.svg", "nome": "BMG"},
    {"codigo": "original.svg", "nome": "Banco Original"},
    {"codigo": "cofrinho.svg", "nome": "Cofrinho / Reserva"}
]


def resolver_icone_banco(nome_ou_icone: str) -> str:
    """Mapeia nome de conta, cartão ou texto para o nome do arquivo SVG correspondente em static/img/bancos/."""
    if not nome_ou_icone:
        return "carteira.svg"
    s = str(nome_ou_icone).strip().lower()
    if s.endswith(".svg"):
        return s
    if "mercado" in s:
        return "mercadopago.svg"
    if "99" in s:
        return "99pay.svg"
    if "carteira" in s or "dinheiro" in s or "espécie" in s:
        return "carteira.svg"
    if "nu" in s:
        return "nubank.svg"
    if "inter" in s:
        return "inter.svg"
    if "caixa" in s or "cef" in s:
        return "caixa.svg"
    if "itau" in s or "itaú" in s:
        return "itau.svg"
    if "bradesco" in s:
        return "bradesco.svg"
    if "santander" in s:
        return "santander.svg"
    if "brasil" in s or " bb" in s or s == "bb":
        return "bb.svg"
    if "c6" in s:
        return "c6.svg"
    if "picpay" in s:
        return "picpay.svg"
    if "pagbank" in s or "pagseguro" in s:
        return "pagbank.svg"
    if "stone" in s:
        return "stone.svg"
    if "sicoob" in s:
        return "sicoob.svg"
    if "sicredi" in s:
        return "sicredi.svg"
    if "cora" in s:
        return "cora.svg"
    if "btg" in s:
        return "btg.svg"
    if "xp" in s:
        return "xp.svg"
    if "safra" in s:
        return "safra.svg"
    if "bmg" in s:
        return "bmg.svg"
    if "original" in s:
        return "original.svg"
    if "cofrinho" in s or "reserva" in s:
        return "cofrinho.svg"
    return "carteira.svg"


templates.env.filters["icone_banco"] = resolver_icone_banco


def obter_foco_hoje(conn: sqlite3.Connection, hoje_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna os dados unificados e oficiais do 'Foco de Hoje' (meta diária e turnos realizados).
    Fórmula: horas_planejadas * R$ 35,00/h (ganho médio de referência da 99).
    Utilizado de forma consistente tanto na Visão Geral quanto no Oikos Drive.
    """
    if hoje_str is None:
        hoje_str = date.today().strftime("%Y-%m-%d")
    cur = conn.cursor()
    cur.execute("SELECT valor FROM config_dashboard WHERE chave = 'horas_hoje_planejadas'")
    row_h_cfg = cur.fetchone()
    horas_hoje_meta = float(row_h_cfg[0]) if row_h_cfg and row_h_cfg[0] else 5.0
    taxa_hora_mercado = 35.0
    meta_bruta_hoje = round(horas_hoje_meta * taxa_hora_mercado, 2)

    cur.execute("""
        SELECT COALESCE(SUM(ganho_bruto), 0), COALESCE(SUM(horas), 0), COUNT(*), COALESCE(SUM(combustivel), 0)
        FROM turnos
        WHERE data = ?
    """, (hoje_str,))
    row_t_hoje = cur.fetchone()
    bruto_hoje = round(float(row_t_hoje[0] or 0.0), 2)
    horas_hoje_real = round(float(row_t_hoje[1] or 0.0), 2)
    qtd_turnos_hoje = int(row_t_hoje[2] or 0)
    comb_hoje = round(float(row_t_hoje[3] or 0.0), 2)
    liquido_hoje = round(bruto_hoje - comb_hoje, 2)

    pct_meta_hoje = min(100.0, round((bruto_hoje / meta_bruta_hoje * 100.0), 1)) if meta_bruta_hoje > 0 else 0.0
    restante_meta_hoje = max(0.0, round(meta_bruta_hoje - bruto_hoje, 2))
    horas_restantes = round(restante_meta_hoje / taxa_hora_mercado, 1) if restante_meta_hoje > 0 else 0.0

    return {
        "horas_hoje_meta": horas_hoje_meta,
        "taxa_hora_mercado": taxa_hora_mercado,
        "meta_bruta_hoje": meta_bruta_hoje,
        "bruto_hoje": bruto_hoje,
        "horas_hoje_real": horas_hoje_real,
        "qtd_turnos_hoje": qtd_turnos_hoje,
        "comb_hoje": comb_hoje,
        "liquido_hoje": liquido_hoje,
        "pct_meta_hoje": pct_meta_hoje,
        "restante_meta_hoje": restante_meta_hoje,
        "horas_restantes": horas_restantes
    }


PALETA_CORES_CATEGORIA = [
    "#0284c7", "#0d9488", "#10b981", "#f59e0b", "#f97316",
    "#ef4444", "#8b5cf6", "#ec4899", "#64748b", "#a855f7"
]

def calcular_curva_saldo_dashboard(conn: sqlite3.Connection, hoje: date) -> Dict[str, Any]:
    hoje_str = hoje.strftime("%Y-%m-%d")
    res_hoje = saldo_service.calcular_saldo_consolidado(conn, data_referencia=hoje_str)
    saldo_hoje = float(res_hoje.get("saldo_consolidado", 0.0))
    
    pontos = []
    # 7 dias de histórico
    for i in range(7, 0, -1):
        dt = hoje - timedelta(days=i)
        dt_s = dt.strftime("%Y-%m-%d")
        try:
            s = float(saldo_service.calcular_saldo_consolidado(conn, data_referencia=dt_s).get("saldo_consolidado", 0.0))
        except Exception:
            s = saldo_hoje
        pontos.append({
            "data": dt.strftime("%d/%m"),
            "data_completa": dt_s,
            "saldo": s,
            "tipo": "realizado"
        })
    
    # Ponto de Hoje
    pontos.append({
        "data": hoje.strftime("%d/%m"),
        "data_completa": hoje_str,
        "saldo": saldo_hoje,
        "tipo": "hoje"
    })
    
    # 7 dias de Projeção
    cur = conn.cursor()
    limite_proj = hoje + timedelta(days=7)
    cur.execute("""
        SELECT data, tipo, valor FROM transacoes
        WHERE data > ? AND data <= ? AND (pago = 0 OR pago IS NULL)
        ORDER BY data ASC
    """, (hoje_str, limite_proj.strftime("%Y-%m-%d")))
    pendentes = cur.fetchall()
    
    saldo_acum = saldo_hoje
    for i in range(1, 8):
        df = hoje + timedelta(days=i)
        df_s = df.strftime("%Y-%m-%d")
        movs = [p for p in pendentes if p[0] == df_s]
        for m in movs:
            v = float(m[2] or 0.0)
            if m[1] == "receita":
                saldo_acum += v
            elif m[1] == "despesa":
                saldo_acum -= v
        pontos.append({
            "data": df.strftime("%d/%m"),
            "data_completa": df_s,
            "saldo": round(saldo_acum, 2),
            "tipo": "projetado"
        })
        
    valores = [p["saldo"] for p in pontos]
    min_v = min(valores) if valores else 0.0
    max_v = max(valores) if valores else 100.0
    
    return {
        "pontos": pontos,
        "saldo_hoje": saldo_hoje,
        "min_saldo": min_v,
        "max_saldo": max_v,
        "tem_historico": len(pontos) > 1
    }

def calcular_gastos_categoria_rosca(conn: sqlite3.Connection, inicio_mes: str, fim_mes: str) -> Dict[str, Any]:
    cur = conn.cursor()
    
    def apurar(filtro_pago=None):
        sql = """
            SELECT categoria, SUM(valor) as total, COUNT(*) as qtd
            FROM transacoes
            WHERE tipo = 'despesa' AND data >= ? AND data <= ?
        """
        params = [inicio_mes, fim_mes]
        if filtro_pago is not None:
            sql += " AND pago = ?"
            params.append(filtro_pago)
        sql += " GROUP BY categoria ORDER BY total DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        tot = sum(float(r[1] or 0.0) for r in rows)
        
        categorias = []
        acum_pct = 0.0
        
        for i, r in enumerate(rows):
            val = float(r[1] or 0.0)
            pct = round((val / tot * 100.0), 1) if tot > 0 else 0.0
            cor = PALETA_CORES_CATEGORIA[i % len(PALETA_CORES_CATEGORIA)]
            
            start_angle = acum_pct * 3.6
            acum_pct += pct
            end_angle = min(360.0, acum_pct * 3.6)
            
            categorias.append({
                "categoria": r[0] or "Sem Categoria",
                "valor": val,
                "pct": pct,
                "qtd": r[2],
                "cor": cor,
                "start_angle": start_angle,
                "end_angle": end_angle
            })
            
        return {
            "total": tot,
            "categorias": categorias,
            "tem_dados": len(categorias) > 0
        }

    return {
        "pagas": apurar(filtro_pago=1),
        "todas": apurar(filtro_pago=None)
    }

def calcular_detalhamento_entradas_dashboard(conn: sqlite3.Connection, inicio_mes: str, fim_mes: str) -> Dict[str, Any]:
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data, descricao, categoria, valor, conta
        FROM transacoes
        WHERE tipo = 'receita' AND pago = 1 AND data >= ? AND data <= ?
        ORDER BY data DESC
    """, (inicio_mes, fim_mes))
    rows = cur.fetchall()
    
    tot_rec = 0.0
    trabalho = 0.0
    emprestimos = 0.0
    outras = 0.0
    itens = []
    
    for r in rows:
        v = float(r[4] or 0.0)
        tot_rec += v
        desc = (r[2] or "").lower()
        cat = (r[3] or "").lower()
        
        if any(k in desc or k in cat for k in ["salário", "salario", "pró-labore", "pro-labore", "99", "uber", "turno", "chave"]):
            tp = "trabalho"
            trabalho += v
        elif any(k in desc or k in cat for k in ["empréstimo", "emprestimo", "financiamento", "crédito", "credito"]):
            tp = "emprestimo"
            emprestimos += v
        else:
            tp = "outras"
            outras += v
            
        itens.append({
            "id": r[0],
            "data": r[1],
            "descricao": r[2],
            "categoria": r[3],
            "valor": v,
            "conta": r[5],
            "tipo_classificacao": tp
        })
        
    return {
        "total_recebido": tot_rec,
        "trabalho_total": trabalho,
        "emprestimos_total": emprestimos,
        "outras_total": outras,
        "itens": itens,
        "qtd_itens": len(itens)
    }


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

    # 2. Receita Mensal Consolidada (Critério rigoroso idêntico ao Planejamento: transações financeiras reais recebidas)
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'receita' AND pago = 1 AND data >= ? AND data <= ?
    """, (inicio_mes_str, fim_mes_str))
    receita_mensal_total = float(cur.fetchone()[0] or 0.0)

    # Previsão explícita apenas se houver receita cadastrada a receber no período (sem suposições)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'receita' AND (pago = 0 OR pago IS NULL) AND data >= ? AND data <= ?
    """, (inicio_mes_str, fim_mes_str))
    receita_prevista_total = float(cur.fetchone()[0] or 0.0)

    # Discriminação informativa das receitas recebidas (se houver)
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM transacoes
        WHERE tipo = 'receita' AND pago = 1 AND data >= ? AND data <= ?
          AND (descricao LIKE '%Fernanda%' OR categoria LIKE '%Fernanda%')
    """, (inicio_mes_str, fim_mes_str))
    row_sal = cur.fetchone()
    sal_fernanda = float(row_sal[0]) if (row_sal and row_sal[0] > 0) else 0.0

    # Produção Operacional da 99 (métrica de atividade do módulo Drive, segregada do fluxo de receitas financeiras)
    prod_99 = saldo_service.obter_producao_consolidada_99(conn, data_ref=hoje)
    fat_99_mes = float(prod_99.get("total_mes_bruto", 0.0))
    fat_99_semana = float(prod_99.get("semana", {}).get("bruto", 0.0))

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

    # 4. Meta do Dia e Produção de Hoje (via fonte unificada)
    foco_hoje = obter_foco_hoje(conn, hoje_str)
    horas_hoje_meta = foco_hoje["horas_hoje_meta"]
    meta_bruta_hoje = foco_hoje["meta_bruta_hoje"]
    bruto_hoje = foco_hoje["bruto_hoje"]
    horas_hoje_real = foco_hoje["horas_hoje_real"]
    qtd_turnos_hoje = foco_hoje["qtd_turnos_hoje"]
    comb_hoje = foco_hoje["comb_hoje"]
    liquido_hoje = foco_hoje["liquido_hoje"]
    pct_meta_hoje = foco_hoje["pct_meta_hoje"]
    restante_meta_hoje = foco_hoje["restante_meta_hoje"]

    # 5. Contas Atrasadas (Vencidas)
    cur.execute("""
        SELECT id, data, descricao, categoria, valor, conta, conta_id, COALESCE(titular, '') as titular
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
        conta_raw = (r["conta"] or "").strip()
        conta_def = bool(conta_raw and conta_raw not in ("None", "A Confirmar"))
        atrasadas.append({
            "id": r["id"],
            "data": dt_obj.strftime("%d/%m"),
            "data_completa": dt_obj.strftime("%d/%m/%Y"),
            "descricao": r["descricao"],
            "categoria": r["categoria"],
            "valor": val,
            "conta": conta_raw if conta_def else "Mercado Pago",
            "conta_id": r["conta_id"],
            "conta_definida": conta_def,
            "dias_atraso": dias_atraso
        })

    # 6. Contas que Vencem Hoje
    cur.execute("""
        SELECT id, data, descricao, categoria, valor, conta, conta_id, COALESCE(titular, '') as titular
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
        conta_raw = (r["conta"] or "").strip()
        conta_def = bool(conta_raw and conta_raw not in ("None", "A Confirmar"))
        vence_hoje.append({
            "id": r["id"],
            "data": hoje.strftime("%d/%m"),
            "descricao": r["descricao"],
            "categoria": r["categoria"],
            "valor": val,
            "conta": conta_raw if conta_def else "Mercado Pago",
            "conta_id": r["conta_id"],
            "conta_definida": conta_def
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

    # 10. Resumo Patrimonial
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
        resumo_despesas_anuais = None

    # 12. Curva de Saldo (Histórico 7d + Projeção 7d)
    curva_saldo = calcular_curva_saldo_dashboard(conn, hoje)

    # 13. Gastos por Categoria (Rosca interativa Pagas vs Todas)
    gastos_categoria = calcular_gastos_categoria_rosca(conn, inicio_mes_str, fim_mes_str)

    # 14. Detalhamento e Segregação de Entradas Externas
    detalhes_entradas = calcular_detalhamento_entradas_dashboard(conn, inicio_mes_str, fim_mes_str)

    # 15. Resumo Consolidado Paga Leve
    try:
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0), COUNT(*)
            FROM transacoes
            WHERE grupo_parcelamento IS NOT NULL AND (pago = 0 OR pago IS NULL) AND data >= ? AND data <= ?
        """, (inicio_mes_str, fim_mes_str))
        r_pl_mes = cur.fetchone()
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0), COUNT(*)
            FROM transacoes
            WHERE grupo_parcelamento IS NOT NULL AND (pago = 0 OR pago IS NULL)
        """, ())
        r_pl_tot = cur.fetchone()
        pagaleve_resumo = {
            "mes_valor": float(r_pl_mes[0] or 0.0),
            "mes_qtd": int(r_pl_mes[1] or 0),
            "total_valor": float(r_pl_tot[0] or 0.0),
            "total_qtd": int(r_pl_tot[1] or 0),
            "limite_carlos": 300.0,
            "tem_compras": int(r_pl_tot[1] or 0) > 0
        }
    except Exception:
        pagaleve_resumo = {"mes_valor": 0.0, "mes_qtd": 0, "total_valor": 0.0, "total_qtd": 0, "limite_carlos": 300.0, "tem_compras": False}

    conn.close()

    dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    nome_dia_hoje = dias_semana_pt[hoje.weekday()]
    meses_pt_dashboard = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome_atual = meses_pt_dashboard[mes_atual] if 1 <= mes_atual <= 12 else "Mês"

    return {
        "hoje_str": hoje_str,
        "hoje_formatado": hoje.strftime("%d/%m/%Y"),
        "dia_semana": nome_dia_hoje,
        "mes_nome": mes_nome_atual,
        "ano": ano_atual,
        # Resumo da Casa
        "receita_mensal": receita_mensal_total,
        "receita_prevista": receita_prevista_total,
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
        "cartao": cartao_info,
        "resumo_patrimonio": resumo_patrimonio,
        "resumo_despesas_anuais": resumo_despesas_anuais,
        "curva_saldo": curva_saldo,
        "gastos_categoria": gastos_categoria,
        "detalhes_entradas": detalhes_entradas,
        "pagaleve_resumo": pagaleve_resumo
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
    cur.execute("PRAGMA table_info(transacoes)")
    cols_tr = [c["name"] for c in cur.fetchall()]
    if "data_liquidacao" not in cols_tr:
        cur.execute("ALTER TABLE transacoes ADD COLUMN data_liquidacao TEXT")
        conn.commit()
    if "subcategoria" not in cols_tr:
        cur.execute("ALTER TABLE transacoes ADD COLUMN subcategoria TEXT")
        conn.commit()

    cur.execute("""
        SELECT id, COALESCE(data_liquidacao, data) as data_efetiva, data, data_liquidacao, descricao, valor, tipo, categoria, COALESCE(subcategoria, '') as subcategoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra,
               titular, COALESCE(juros, 0) as juros, COALESCE(desconto, 0) as desconto, COALESCE(motivo_ajuste, '') as motivo_ajuste
        FROM transacoes
        WHERE (data >= ? AND data <= ?) OR (pago = 1 AND data_liquidacao >= ? AND data_liquidacao <= ?)
        ORDER BY COALESCE(data_liquidacao, data) DESC, id DESC
    """, (inicio_mes, fim_mes, inicio_mes, fim_mes))
    rows = cur.fetchall()

    hoje_str = hoje.strftime("%Y-%m-%d")
    transacoes = []
    tot_receitas = 0.0
    tot_despesas = 0.0

    # Mapa de abastecimentos vinculados para exibir badge de economia no extrato
    abast_map = {}
    try:
        cur.execute("PRAGMA table_info(veiculo_abastecimentos)")
        cols_ab = [c["name"] for c in cur.fetchall()]
        if "app_desconto" not in cols_ab:
            cur.execute("ALTER TABLE veiculo_abastecimentos ADD COLUMN app_desconto TEXT DEFAULT 'Nenhum'")
            conn.commit()
        cur.execute("""
            SELECT transacao_id, valor_bruto, valor_pago, desconto, litros, COALESCE(app_desconto, 'Nenhum') as app_desconto
            FROM veiculo_abastecimentos
            WHERE transacao_id IS NOT NULL
        """)
        for ab in cur.fetchall():
            tid_ab = ab["transacao_id"]
            vp = float(ab["valor_pago"] or 0.0)
            vb = float(ab["valor_bruto"] or vp)
            ec = round(max(0.0, vb - vp), 2) if vb > vp else round(float(ab["desconto"] or 0.0), 2)
            if vb < vp + ec:
                vb = round(vp + ec, 2)
            pct = round((ec / vb) * 100.0, 1) if (vb > 0 and ec > 0) else 0.0
            app_nm = (ab["app_desconto"] or "").strip()
            if not app_nm or app_nm == "Nenhum":
                app_nm = "Posto / Outro"
            if ec > 0:
                abast_map[tid_ab] = f"Economia de {formatar_moeda_br(ec)} ({pct:.1f}%) via {app_nm}"
    except Exception:
        abast_map = {}

    for r in rows:
        val = float(r["valor"] or 0.0)
        tipo = r["tipo"] or "despesa"
        if tipo == "receita":
            tot_receitas += val
        elif tipo == "despesa":
            tot_despesas += val

        dt_str = str(r["data_efetiva"] or r["data"])[:10]
        try:
            dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
            dt_fmt = dt_obj.strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str

        pago_flag = 1 if r["pago"] == 1 else 0
        is_atrasada = (tipo == "despesa" and pago_flag == 0 and dt_str < hoje_str)

        grp_str = str(r["grupo_parcelamento"] or "").strip()
        desc_str = str(r["descricao"] or "").strip()
        is_pl = bool("pagaleve" in grp_str.lower() or "paga leve" in desc_str.lower() or "pagaleve" in desc_str.lower())

        num_parc = r["numero_parcela"]
        tot_parc = r["total_parcelas_compra"]
        if is_pl:
            if not num_parc or not tot_parc:
                m_parc = re.search(r'(\d+)\s*/\s*(\d+)', desc_str)
                if m_parc:
                    num_parc = int(m_parc.group(1))
                    tot_parc = int(m_parc.group(2))
                else:
                    num_parc = 1
                    tot_parc = 4

        titular_str = str(r["titular"] or "").strip()
        if not titular_str or titular_str in ("A Confirmar", "None", ""):
            titular_str = "Carlos"

        cat_str = str(r["categoria"] or "").strip()
        if not cat_str or cat_str.lower() in ("none", "null"):
            cat_str = "Sem categoria"

        transacoes.append({
            "id": r["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": desc_str,
            "valor": val,
            "tipo": tipo,
            "categoria": cat_str,
            "subcategoria": r["subcategoria"] or "",
            "conta": r["conta"] or "Mercado Pago",
            "pago": pago_flag,
            "grupo_parcelamento": r["grupo_parcelamento"],
            "numero_parcela": num_parc,
            "total_parcelas_compra": tot_parc,
            "titular": titular_str,
            "is_pagaleve": is_pl,
            "pagaleve_link": f"/pagaleve#{grp_str}" if grp_str else "/pagaleve",
            "juros": float(r["juros"] or 0.0),
            "desconto": float(r["desconto"] or 0.0),
            "motivo_ajuste": r["motivo_ajuste"] or "",
            "eh_passada": False,
            "is_atrasada": is_atrasada,
            "economia_badge": abast_map.get(r["id"], "")
        })

    # Contas atrasadas de meses anteriores: despesas pendentes com vencimento anterior ao mês selecionado
    cur.execute("""
        SELECT id, data, descricao, valor, tipo, categoria, COALESCE(subcategoria, '') as subcategoria, conta, pago, grupo_parcelamento, numero_parcela, total_parcelas_compra,
               titular, COALESCE(juros, 0) as juros, COALESCE(desconto, 0) as desconto, COALESCE(motivo_ajuste, '') as motivo_ajuste
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

        grp_str = str(r["grupo_parcelamento"] or "").strip()
        desc_str = str(r["descricao"] or "").strip()
        is_pl = bool("pagaleve" in grp_str.lower() or "paga leve" in desc_str.lower() or "pagaleve" in desc_str.lower())

        num_parc = r["numero_parcela"]
        tot_parc = r["total_parcelas_compra"]
        if is_pl:
            if not num_parc or not tot_parc:
                m_parc = re.search(r'(\d+)\s*/\s*(\d+)', desc_str)
                if m_parc:
                    num_parc = int(m_parc.group(1))
                    tot_parc = int(m_parc.group(2))
                else:
                    num_parc = 1
                    tot_parc = 4

        titular_str = str(r["titular"] or "").strip()
        if not titular_str or titular_str in ("A Confirmar", "None", ""):
            titular_str = "Carlos"

        cat_str = str(r["categoria"] or "").strip()
        if not cat_str or cat_str.lower() in ("none", "null"):
            cat_str = "Sem categoria"

        transacoes_atrasadas.append({
            "id": r["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": desc_str,
            "valor": val,
            "tipo": "despesa",
            "categoria": cat_str,
            "subcategoria": r["subcategoria"] or "",
            "conta": r["conta"] or "Mercado Pago",
            "pago": 0,
            "grupo_parcelamento": r["grupo_parcelamento"],
            "numero_parcela": num_parc,
            "total_parcelas_compra": tot_parc,
            "titular": titular_str,
            "is_pagaleve": is_pl,
            "pagaleve_link": f"/pagaleve#{grp_str}" if grp_str else "/pagaleve",
            "juros": float(r["juros"] or 0.0),
            "desconto": float(r["desconto"] or 0.0),
            "motivo_ajuste": r["motivo_ajuste"] or "",
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
            "hoje_formatado": hoje.strftime("%d/%m/%Y"),
            "mes_nome": mes_nome,
            "mes_ant": mes_ant,
            "ano_ant": ano_ant,
            "mes_prox": mes_prox,
            "ano_prox": ano_prox,
            "eh_mes_atual": eh_mes_atual,
            "opcoes_periodo": opcoes_periodo,
            "filtro_inicial": filtro or "",
            "hoje_str": hoje_str,
            "categorias_subcategorias": CATEGORIAS_SUBCATEGORIAS,
            "categorias_subcategorias_json": json.dumps(CATEGORIAS_SUBCATEGORIAS, ensure_ascii=False),
            "active_tab": "lancamentos"
        }
    )


# Estrutura hierárquica Categoria -> Subcategoria (Categorias e subcategorias)
CATEGORIAS_SUBCATEGORIAS: Dict[str, List[str]] = {
    "Alimentação": [
        "Supermercado",
        "Padaria",
        "Feira/Sacolão",
        "Almoço/Marmitex",
        "Lanche",
        "Restaurante"
    ],
    "Transporte": [
        "Combustível",
        "Transporte Fernanda/Escola",
        "Manutenção",
        "Estacionamento",
        "Taxa Operação"
    ],
    "Moradia/Contas": [
        "Energia/CEMIG",
        "Telefone/Internet/Claro",
        "Assinaturas/Google One",
        "Água/Copasa",
        "PagaLeve",
        "Acordo BV",
        "Outros"
    ],
    "Pessoal": [
        "Doces/Mimos",
        "Saúde/Farmácia",
        "PagaLeve",
        "Barbearia/Cuidados",
        "Outros"
    ],
    "Saúde": [
        "Saúde/Farmácia",
        "Medicamentos",
        "Consultas/Exames"
    ],
    "Combustível": [
        "Etanol",
        "Gasolina",
        "GNV"
    ],
    "Transferência": [
        "Dívida Cartão PicPay",
        "Transferência Entre Contas",
        "Aporte Cofrinho"
    ],
    "99 Produção": [
        "Corridas Online (99Pay)",
        "Corridas Dinheiro/Pix",
        "Bônus / Incentivos"
    ],
    "Salário": [
        "Salário Mensal",
        "Adiantamento / Vale",
        "Renda Extra"
    ]
}


def converter_valor_monetario(val: Any, default: float = 0.0) -> float:
    """Converte valores com vírgula ou ponto (ex: '50,00', '1.250,50', '50.00', 50) para float seguro."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return default
    val_str = val_str.replace("R$", "").replace("r$", "").strip()
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
    try:
        return round(float(val_str), 2)
    except (ValueError, TypeError):
        return default


@app.post("/api/lancamentos")
async def api_criar_lancamento(
    data: str = Form(...),
    tipo: str = Form(...),
    valor: Any = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    subcategoria: Optional[str] = Form(""),
    conta: str = Form(...),
    pago: Optional[int] = Form(0),
    id: Optional[int] = Form(None),
    juros: Optional[Any] = Form(0.0),
    desconto: Optional[Any] = Form(0.0),
    motivo_ajuste: Optional[str] = Form("")
):
    """Insere ou atualiza transação de receita ou despesa no banco SQLite com Categoria, Subcategoria, Juros, Desconto e Motivo."""
    valor_num = converter_valor_monetario(valor)
    if valor_num <= 0:
        return JSONResponse(status_code=400, content={"status": "erro", "sucesso": False, "erro": "Valor deve ser maior que zero."})

    juros_num = round(converter_valor_monetario(juros), 2) if juros is not None else 0.0
    desconto_num = round(converter_valor_monetario(desconto), 2) if desconto is not None else 0.0
    motivo_ajuste_str = (motivo_ajuste or "").strip()

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(transacoes)")
        cols_tr = [c["name"] for c in cur.fetchall()]
        if "subcategoria" not in cols_tr:
            cur.execute("ALTER TABLE transacoes ADD COLUMN subcategoria TEXT")
            conn.commit()
        if "juros" not in cols_tr:
            cur.execute("ALTER TABLE transacoes ADD COLUMN juros REAL DEFAULT 0")
            conn.commit()
        if "desconto" not in cols_tr:
            cur.execute("ALTER TABLE transacoes ADD COLUMN desconto REAL DEFAULT 0")
            conn.commit()
        if "motivo_ajuste" not in cols_tr:
            cur.execute("ALTER TABLE transacoes ADD COLUMN motivo_ajuste TEXT")
            conn.commit()

        conta_input = str(conta).strip()
        cur.execute("SELECT id, nome FROM contas_config WHERE nome = ? OR id = ?", (conta_input, conta_input))
        row_c = cur.fetchone()
        if row_c:
            conta_id = row_c["id"]
            conta_nome = row_c["nome"]
        else:
            c_low = conta_input.lower()
            if "carteira" in c_low or "dinheiro" in c_low:
                conta_id = 2
                conta_nome = "Dinheiro / Carteira"
            elif "99" in c_low:
                conta_id = 1779
                conta_nome = "99Pay"
            elif "mercado" in c_low and "card" not in c_low:
                conta_id = 1
                conta_nome = "Mercado Pago"
            else:
                conta_id = 1
                conta_nome = conta_input

        pago_int = 1 if (pago == 1 or str(pago).strip() in ["1", "true", "True"]) else 0
        afeta_saldo = 1 if pago_int == 1 else 0
        subcat_str = (subcategoria or "").strip()

        if id and int(id) > 0:
            cur.execute("""
                UPDATE transacoes
                SET data = ?, descricao = ?, valor = ?, tipo = ?, categoria = ?, subcategoria = ?, conta = ?, conta_id = ?, pago = ?, afeta_saldo_bancario = ?, juros = ?, desconto = ?, motivo_ajuste = ?
                WHERE id = ?
            """, (str(data)[:10], descricao.strip(), valor_num, tipo, categoria, subcat_str, conta_nome, conta_id, pago_int, afeta_saldo, juros_num, desconto_num, motivo_ajuste_str, int(id)))
            
            # Sincroniza veiculo_abastecimentos caso haja vínculo
            try:
                cur.execute("""
                    UPDATE veiculo_abastecimentos
                    SET data = ?, valor_pago = ?, conta = ?, conta_id = ?
                    WHERE transacao_id = ?
                """, (str(data)[:10], valor_num, conta_nome, conta_id, int(id)))
            except Exception:
                pass

            conn.commit()

            # Recalcula saldo consolidado imediatamente
            res_saldo = saldo_service.calcular_saldo_consolidado(conn)

            return {
                "status": "sucesso",
                "sucesso": True,
                "mensagem": f"Lançamento '{descricao.strip()}' atualizado com sucesso!",
                "saldo_consolidado": float(res_saldo.get("saldo_consolidado", 0.0))
            }

        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, subcategoria, conta, conta_id, pago, afeta_saldo_bancario, juros, desconto, motivo_ajuste)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(data)[:10], descricao.strip(), valor_num, tipo, categoria, subcat_str, conta_nome, conta_id, pago_int, afeta_saldo, juros_num, desconto_num, motivo_ajuste_str))
        conn.commit()

        res_saldo = saldo_service.calcular_saldo_consolidado(conn)
        return {
            "status": "sucesso",
            "sucesso": True,
            "mensagem": f"{tipo.capitalize()} '{descricao.strip()}' de {formatar_moeda_br(valor_num)} lançada com sucesso!",
            "saldo_consolidado": float(res_saldo.get("saldo_consolidado", 0.0))
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"status": "erro", "sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/lancamentos/editar")
async def api_editar_lancamento(
    id: Optional[Any] = Form(None),
    data: str = Form(...),
    tipo: str = Form("despesa"),
    valor: Any = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    subcategoria: Optional[str] = Form(""),
    conta: str = Form("Mercado Pago"),
    pago: Optional[int] = Form(0),
    juros: Optional[Any] = Form(0.0),
    desconto: Optional[Any] = Form(0.0),
    motivo_ajuste: Optional[str] = Form("")
):
    if not id:
        raise HTTPException(status_code=400, detail="ID do lançamento não informado.")
    return await api_criar_lancamento(
        data=data,
        tipo=tipo,
        valor=valor,
        descricao=descricao,
        categoria=categoria,
        subcategoria=subcategoria,
        conta=conta,
        pago=pago,
        id=int(id),
        juros=juros,
        desconto=desconto,
        motivo_ajuste=motivo_ajuste
    )


@app.post("/api/lancamentos/{transacao_id}")
async def api_editar_lancamento_por_id(
    transacao_id: str,
    id: Optional[Any] = Form(None),
    data: str = Form(...),
    tipo: str = Form("despesa"),
    valor: Any = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    subcategoria: Optional[str] = Form(""),
    conta: str = Form("Mercado Pago"),
    pago: Optional[int] = Form(0),
    juros: Optional[Any] = Form(0.0),
    desconto: Optional[Any] = Form(0.0),
    motivo_ajuste: Optional[str] = Form("")
):
    tid = id if (id and str(id).strip()) else (transacao_id if transacao_id != "editar" else None)
    if not tid:
        raise HTTPException(status_code=400, detail="ID do lançamento não informado.")
    return await api_criar_lancamento(
        data=data,
        tipo=tipo,
        valor=valor,
        descricao=descricao,
        categoria=categoria,
        subcategoria=subcategoria,
        conta=conta,
        pago=pago,
        id=int(tid),
        juros=juros,
        desconto=desconto,
        motivo_ajuste=motivo_ajuste
    )


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
            "bancos_disponiveis": BANCOS_DISPONIVEIS,
            "active_tab": "contas"
        }
    )


@app.post("/contas")
@app.post("/api/contas")
@app.post("/contas/nova")
@app.post("/api/contas/nova")
@app.post("/contas/editar/{conta_id}")
@app.put("/contas/editar/{conta_id}")
@app.post("/api/contas/editar/{conta_id}")
@app.put("/api/contas/editar/{conta_id}")
@app.post("/contas/{conta_id}/editar")
@app.put("/contas/{conta_id}/editar")
@app.post("/api/contas/{conta_id}/editar")
@app.put("/api/contas/{conta_id}/editar")
@app.post("/contas/editar")
@app.post("/api/contas/editar")
@app.post("/contas/salvar")
@app.post("/api/contas/salvar")
async def api_salvar_conta(request: Request, conta_id: Optional[int] = None):
    """
    Cria ou edita uma conta em contas_config (refletida na view contas) e registra
    o ajuste/marco inicial de saldo se aplicável. Suporta JSON e formulários HTML padrão.
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
            raw_icone = str(payload.get("icone", "")).strip() or "banco_default.svg"
            icone = os.path.basename(raw_icone)
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
            raw_icone = str(form.get("icone", "")).strip() or "banco_default.svg"
            icone = os.path.basename(raw_icone)
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

        is_ajax = ("application/json" in content_type or 
                   "application/json" in request.headers.get("accept", "") or
                   request.headers.get("x-requested-with") == "XMLHttpRequest")

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
            if is_ajax:
                return JSONResponse({
                    "success": True,
                    "sucesso": True,
                    "conta_id": target_id,
                    "mensagem": f"Conta '{nome}' atualizada com sucesso!"
                })
            else:
                return RedirectResponse(url="/contas", status_code=303)
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
            if is_ajax:
                return JSONResponse({
                    "success": True,
                    "sucesso": True,
                    "conta_id": nova_id,
                    "mensagem": f"Conta '{nome}' cadastrada com sucesso!"
                })
            else:
                return RedirectResponse(url="/contas", status_code=303)
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
            # Se for exclusão de transação/conta a pagar enviada para /contas/excluir
            tem_transacao = False
            if "application/json" in content_type and payload.get("transacao_id"):
                tem_transacao = True
            elif "form" in content_type and form.get("transacao_id"):
                tem_transacao = True
            if tem_transacao:
                conn.close()
                return await api_excluir_conta(request)
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

def garantir_schema_cartoes(conn: sqlite3.Connection) -> None:
    """Garante colunas estendidas na tabela cartoes e remove cartões fictícios."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cartoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            bandeira TEXT DEFAULT 'Mastercard',
            limite_total REAL NOT NULL DEFAULT 0.0,
            dia_fechamento INTEGER DEFAULT 1,
            dia_vencimento INTEGER DEFAULT 7,
            cor TEXT DEFAULT '#ea580c',
            ultimos_digitos TEXT DEFAULT '0000',
            titular TEXT DEFAULT 'Carlos'
        )
    """)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(cartoes)").fetchall()]
    if "ultimos_digitos" not in cols:
        cur.execute("ALTER TABLE cartoes ADD COLUMN ultimos_digitos TEXT DEFAULT '0000'")
    if "titular" not in cols:
        cur.execute("ALTER TABLE cartoes ADD COLUMN titular TEXT DEFAULT 'Carlos'")
    if "icone" not in cols:
        cur.execute("ALTER TABLE cartoes ADD COLUMN icone TEXT DEFAULT ''")
    # Garante exclusão do cartão fictício Mercado Pago Card
    cur.execute("DELETE FROM cartoes WHERE nome = 'Mercado Pago Card'")
    conn.commit()


@app.get("/cartoes", response_class=HTMLResponse)
async def pagina_cartoes(request: Request, c: Optional[int] = None):
    conn = conectar_db()
    hoje = date.today()
    mes = hoje.month

    garantir_schema_cartoes(conn)
    cur = conn.cursor()

    # Busca apenas os cartões reais cadastrados
    cur.execute("""
        SELECT id, nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor,
               COALESCE(ultimos_digitos, '0000') AS ultimos_digitos,
               COALESCE(titular, 'Carlos') AS titular,
               COALESCE(icone, '') AS icone
        FROM cartoes
        ORDER BY id ASC
    """)
    rows_crd = cur.fetchall()

    cartoes_dados = []
    cartao_ativo = None

    for r in rows_crd:
        cid = r["id"]
        nome = r["nome"]
        bandeira = r["bandeira"] or "Mastercard"
        lim_total = float(r["limite_total"] or 0.0)
        dia_fech = int(r["dia_fechamento"] or 1)
        dia_venc = int(r["dia_vencimento"] or 7)
        cor = r["cor"] or "#ea580c"
        digitos_raw = str(r["ultimos_digitos"] or "0000").strip()
        ultimos_digitos = digitos_raw[-4:].zfill(4) if digitos_raw else "0000"
        titular_cartao = (r["titular"] or "Carlos").strip()
        icone_cartao = (r["icone"] or "").strip() or resolver_icone_banco(nome)

        # Compras estritamente vinculadas a este cartão de crédito
        if "inter" in nome.lower() or "aparecida" in nome.lower():
            cur.execute("""
                SELECT id, data, descricao, valor, categoria, conta, pago,
                       grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
                FROM transacoes
                WHERE tipo = 'despesa'
                  AND (conta = ? OR conta_id = ? OR conta = 'Cartão Inter Aparecida' OR descricao LIKE '%Inter Aparecida%')
                  AND COALESCE(categoria, '') != 'Pagamento de fatura'
                  AND descricao NOT LIKE 'Pagamento de fatura%'
                  AND (grupo_parcelamento IS NULL OR grupo_parcelamento NOT LIKE 'pagaleve%')
                ORDER BY data ASC, id ASC
            """, (nome, cid))
        else:
            cur.execute("""
                SELECT id, data, descricao, valor, categoria, conta, pago,
                       grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
                FROM transacoes
                WHERE tipo = 'despesa'
                  AND (conta = ? OR conta_id = ?)
                  AND COALESCE(categoria, '') != 'Pagamento de fatura'
                  AND descricao NOT LIKE 'Pagamento de fatura%'
                  AND (grupo_parcelamento IS NULL OR grupo_parcelamento NOT LIKE 'pagaleve%')
                ORDER BY data ASC, id ASC
            """, (nome, cid))

        raw_compras = cur.fetchall()
        compras = []
        tot_fatura = 0.0

        for it in raw_compras:
            val = float(it["valor"] or 0.0)
            tot_fatura += val
            dt_str = str(it["data"])[:10]
            try:
                dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m/%Y")
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
                "titular": it["titular"] or titular_cartao
            })

        lim_disp = max(0.0, lim_total - tot_fatura) if lim_total > 0 else 0.0
        pct_uso = (tot_fatura / lim_total * 100.0) if lim_total > 0 else (100.0 if tot_fatura > 0 else 0.0)

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
            "ultimos_digitos": ultimos_digitos,
            "titular": titular_cartao,
            "icone": icone_cartao,
            "compras": compras
        }
        cartoes_dados.append(c_info)

        if c is not None and cid == c:
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
            "bancos_disponiveis": BANCOS_DISPONIVEIS,
            "active_tab": "cartoes"
        }
    )


@app.post("/api/cartoes/salvar")
@app.post("/cartoes/salvar")
async def api_salvar_cartao(request: Request):
    """Cria ou edita um cartão de crédito real."""
    conn = conectar_db()
    try:
        garantir_schema_cartoes(conn)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        cartao_id_raw = data.get("id") or data.get("cartao_id")
        cartao_id = int(cartao_id_raw) if (cartao_id_raw and str(cartao_id_raw).strip().isdigit() and int(cartao_id_raw) > 0) else None

        nome = str(data.get("nome") or "").strip()
        if not nome:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Informe o nome do cartão."})

        bandeira = str(data.get("bandeira") or "Mastercard").strip()
        limite_raw = str(data.get("limite") if data.get("limite") is not None else (data.get("limite_total") or "0")).strip()
        if "," in limite_raw and "." in limite_raw:
            limite_raw = limite_raw.replace(".", "").replace(",", ".")
        elif "," in limite_raw:
            limite_raw = limite_raw.replace(",", ".")
        limite_total = float(limite_raw or 0.0)

        dia_fechamento = max(1, min(31, int(data.get("fechamento") or data.get("dia_fechamento") or 1)))
        dia_vencimento = max(1, min(31, int(data.get("vencimento") or data.get("dia_vencimento") or 7)))

        digitos_raw = re.sub(r"\D", "", str(data.get("ultimos_digitos") or "0000"))
        ultimos_digitos = digitos_raw[-4:].zfill(4) if digitos_raw else "0000"

        titular = str(data.get("titular") or "Carlos").strip() or "Carlos"
        cor = str(data.get("cor") or "#ea580c").strip() or "#ea580c"
        icone = str(data.get("icone") or "").strip() or resolver_icone_banco(nome)

        cur = conn.cursor()
        if cartao_id:
            cur.execute("SELECT nome FROM cartoes WHERE id = ?", (cartao_id,))
            row_ant = cur.fetchone()
            nome_antigo = row_ant["nome"] if row_ant else None

            cur.execute("""
                UPDATE cartoes
                SET nome = ?, bandeira = ?, limite_total = ?, dia_fechamento = ?,
                    dia_vencimento = ?, cor = ?, ultimos_digitos = ?, titular = ?, icone = ?
                WHERE id = ?
            """, (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor, ultimos_digitos, titular, icone, cartao_id))

            if nome_antigo and nome_antigo != nome:
                cur.execute("UPDATE transacoes SET conta = ? WHERE conta = ? OR conta_id = ?", (nome, nome_antigo, cartao_id))

            conn.commit()
            return JSONResponse({
                "sucesso": True,
                "success": True,
                "cartao_id": cartao_id,
                "mensagem": f"Cartão '{nome}' atualizado com sucesso!"
            })
        else:
            cur.execute("""
                INSERT INTO cartoes (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor, ultimos_digitos, titular, icone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nome, bandeira, limite_total, dia_fechamento, dia_vencimento, cor, ultimos_digitos, titular, icone))
            novo_id = cur.lastrowid
            conn.commit()
            return JSONResponse({
                "sucesso": True,
                "success": True,
                "cartao_id": novo_id,
                "mensagem": f"Cartão '{nome}' cadastrado com sucesso!"
            })
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/cartoes/{cartao_id}/excluir")
@app.post("/cartoes/{cartao_id}/excluir")
@app.post("/api/cartoes/excluir")
async def api_excluir_cartao(request: Request, cartao_id: Optional[int] = None):
    """Remove o cartão e limpa vínculos sem apagar transações financeiras."""
    conn = conectar_db()
    try:
        target_id = cartao_id
        if not target_id:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                payload = await request.json()
                target_id = int(payload.get("id") or payload.get("cartao_id") or 0)
            else:
                form = await request.form()
                target_id = int(form.get("id") or form.get("cartao_id") or 0)

        if not target_id:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "ID do cartão não informado."})

        cur = conn.cursor()
        cur.execute("SELECT nome FROM cartoes WHERE id = ?", (target_id,))
        row = cur.fetchone()
        nome_cartao = row["nome"] if row else ""

        # Limpa vínculo de ID sem apagar nenhuma transação financeira
        cur.execute("UPDATE transacoes SET conta_id = NULL WHERE conta_id = ?", (target_id,))
        cur.execute("DELETE FROM cartoes WHERE id = ?", (target_id,))
        conn.commit()

        return JSONResponse({
            "sucesso": True,
            "success": True,
            "mensagem": f"Cartão '{nome_cartao}' removido com sucesso (transações preservadas)."
        })
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


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

    # Contas bancárias disponíveis para débito
    cur.execute("""
        SELECT id, nome, tipo
        FROM contas_config
        WHERE COALESCE(tipo, '') != 'cofrinho'
        ORDER BY id ASC
    """)
    contas_bancarias = [dict(r) for r in cur.fetchall()]

    # 2. Metadados de compras cadastradas em pagaleve_compras
    cur.execute("SELECT * FROM pagaleve_compras ORDER BY id ASC")
    compras_meta = {r["grupo_parcelamento"]: dict(r) for r in cur.fetchall()}

    # 3. Transações de Paga Leve
    cur.execute("""
        SELECT id, data, descricao, valor, categoria, conta, conta_id, pago,
               grupo_parcelamento, numero_parcela, total_parcelas_compra, titular
        FROM transacoes
        WHERE tipo = 'despesa'
          AND (grupo_parcelamento LIKE 'pagaleve%' OR descricao LIKE '%Paga Leve%' OR descricao LIKE '%PagaLeve%')
        ORDER BY data ASC, id ASC
    """)
    trans_pl = [dict(r) for r in cur.fetchall()]

    grupos = {}
    for t in trans_pl:
        grp = t.get("grupo_parcelamento")
        if not grp:
            grp = re.sub(r' - Paga\s*Leve.*', '', t["descricao"], flags=re.I).strip()
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
        nome = meta.get("descricao") or re.sub(r' - Paga\s*Leve.*', '', itens[0]["descricao"], flags=re.I).strip()
        total_parc = int(meta.get("total_parcelas") or max(len(itens), 4))
        titular = meta.get("titular") or itens[0].get("titular") or "Carlos"
        if titular in ("A Confirmar", "None", ""):
            titular = "Carlos"

        itens_sorted = sorted(itens, key=lambda x: (str(x["data"]), int(x["id"])))
        pago_itens = sum(float(r["valor"] or 0.0) for r in itens_sorted if r["pago"] == 1)
        aberto_itens = sum(float(r["valor"] or 0.0) for r in itens_sorted if r["pago"] != 1)

        # 1ª parcela no ato quitada antes do banco (para contratos históricos com menos de 4 itens registrados)
        parc_reg = len(itens_sorted)
        parc_anteriores_quitadas = max(0, total_parc - parc_reg)
        val_meta_orig = float(meta.get("valor_original") or 0.0)
        val_parc = float(meta.get("valor_parcela") or (val_meta_orig / total_parc if (total_parc > 0 and val_meta_orig > 0) else (itens_sorted[0]["valor"] if itens_sorted else 0.0)))
        valor_quitado_anterior = round(parc_anteriores_quitadas * val_parc, 2)

        pago_total = round(valor_quitado_anterior + pago_itens, 2)
        aberto_total = round(aberto_itens, 2)
        val_orig = round(pago_total + aberto_total, 2) if (pago_total + aberto_total) > 0 else val_meta_orig

        tot_aberto_geral += aberto_total
        tot_pago_geral += pago_total

        if "fernanda" in titular.lower():
            aberto_fernanda += aberto_total
        else:
            aberto_carlos += aberto_total

        pct = min(100.0, (pago_total / val_orig * 100.0)) if val_orig > 0 else 100.0

        parcelas_formatadas = []
        for idx, it in enumerate(itens_sorted, start=parc_anteriores_quitadas + 1):
            dt_s = str(it["data"])[:10]
            try:
                dt_f = datetime.datetime.strptime(dt_s, "%Y-%m-%d").strftime("%d/%m/%Y")
                dt_curta = datetime.datetime.strptime(dt_s, "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                dt_f = dt_s
                dt_curta = dt_s

            num_p = it.get("numero_parcela") or idx
            tot_p = it.get("total_parcelas_compra") or total_parc

            parcelas_formatadas.append({
                "id": it["id"],
                "data": dt_s,
                "data_formatada": dt_curta,
                "data_completa": dt_f,
                "descricao": it["descricao"],
                "valor": float(it["valor"]),
                "pago": 1 if it["pago"] == 1 else 0,
                "numero_parcela": num_p,
                "total_parcelas": tot_p,
                "conta": it.get("conta") or "Mercado Pago",
                "categoria": it.get("categoria") or "Moradia/Contas"
            })
            if it["pago"] != 1:
                proximas_parcelas.append({
                    "data": dt_s,
                    "data_formatada": dt_curta,
                    "valor": float(it["valor"]),
                    "nome": nome,
                    "id": it["id"],
                    "titular": titular
                })

        contratos.append({
            "grupo_id": grp_id,
            "nome": nome,
            "titular": titular,
            "categoria": itens_sorted[0].get("categoria") or "Sem categoria",
            "conta": itens_sorted[0].get("conta") or "Mercado Pago",
            "valor_original": val_orig,
            "total_parcelas": total_parc,
            "valor_parcela": val_parc,
            "pago_total": pago_total,
            "aberto_total": aberto_total,
            "percentual_pago": pct,
            "status": "Quitada" if aberto_total <= 0.009 else "Ativa",
            "parcelas": parcelas_formatadas
        })

    conn.close()

    proximas_parcelas.sort(key=lambda x: x["data"])
    prox_venc = proximas_parcelas[0] if proximas_parcelas else None

    proximas_carlos = [p for p in proximas_parcelas if "fernanda" not in p["titular"].lower()]
    proximas_fernanda = [p for p in proximas_parcelas if "fernanda" in p["titular"].lower()]
    prox_venc_carlos = proximas_carlos[0] if proximas_carlos else None
    prox_venc_fernanda = proximas_fernanda[0] if proximas_fernanda else None

    contratos_ativos = [c for c in contratos if c["status"] == "Ativa"]
    contratos_quitados = [c for c in contratos if c["status"] == "Quitada"]

    contratos_carlos_ativos = [c for c in contratos_ativos if "fernanda" not in c["titular"].lower()]
    contratos_fernanda_ativos = [c for c in contratos_ativos if "fernanda" in c["titular"].lower()]

    contratos_carlos_quitados = [c for c in contratos_quitados if "fernanda" not in c["titular"].lower()]
    contratos_fernanda_quitados = [c for c in contratos_quitados if "fernanda" in c["titular"].lower()]

    hoje_iso = date.today().strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        request=request,
        name="pagaleve.html",
        context={
            "contratos": contratos,
            "contratos_ativos": contratos_ativos,
            "contratos_quitados": contratos_quitados,
            "contratos_carlos_ativos": contratos_carlos_ativos,
            "contratos_fernanda_ativos": contratos_fernanda_ativos,
            "contratos_carlos_quitados": contratos_carlos_quitados,
            "contratos_fernanda_quitados": contratos_fernanda_quitados,
            "total_aberto_geral": tot_aberto_geral,
            "total_pago_geral": tot_pago_geral,
            "aberto_carlos": aberto_carlos,
            "aberto_fernanda": aberto_fernanda,
            "limite_carlos": 300.0,
            "disponivel_carlos": round(300.0 - aberto_carlos, 2),
            "proximo_vencimento": prox_venc,
            "prox_venc_carlos": prox_venc_carlos,
            "prox_venc_fernanda": prox_venc_fernanda,
            "contas_bancarias": contas_bancarias,
            "hoje_iso": hoje_iso,
            "categorias_subcategorias": CATEGORIAS_SUBCATEGORIAS,
            "categorias_subcategorias_json": json.dumps(CATEGORIAS_SUBCATEGORIAS, ensure_ascii=False),
            "active_tab": "pagaleve"
        }
    )


@app.post("/api/pagaleve/nova")
@app.post("/api/pagaleve/salvar")
async def api_pagaleve_nova_compra(request: Request):
    """
    Cadastra nova compra Paga Leve em 4x quinzenais:
    - 1ª parcela (entrada) quitada no ato e debitada da conta escolhida
    - 3 parcelas quinzenais pendentes com datas/valores editáveis
    """
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        descricao = str(data.get("descricao") or "").strip()
        if not descricao:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Informe a descrição da compra."})

        titular = str(data.get("titular") or "Carlos").strip()
        if titular not in ("Carlos", "Fernanda"):
            titular = "Carlos"

        categoria_raw = str(data.get("categoria") or "").strip()
        if not categoria_raw or categoria_raw.lower() in ("sem categoria", "none"):
            categoria = "Sem categoria"
        else:
            categoria = categoria_raw
        subcategoria = str(data.get("subcategoria") or "PagaLeve").strip() or "PagaLeve"

        val_raw = str(data.get("valor_total") or "0").strip()
        if "," in val_raw and "." in val_raw:
            val_raw = val_raw.replace(".", "").replace(",", ".")
        elif "," in val_raw:
            val_raw = val_raw.replace(",", ".")
        valor_total = round(float(val_raw or 0.0), 2)
        if valor_total <= 0:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "O valor total deve ser maior que zero."})

        # Processa Juros, Desconto e Motivo de Ajuste
        juros = round(converter_valor_monetario(data.get("juros") or 0.0), 2)
        desconto = round(converter_valor_monetario(data.get("desconto") or 0.0), 2)
        motivo_ajuste = str(data.get("motivo_ajuste") or "").strip()

        # O valor final é a base real para geração e divisão das parcelas
        valor_final = round(valor_total + juros - desconto, 2)
        if valor_final <= 0:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "O valor final após juros e descontos deve ser maior que zero."})

        data_entrada = str(data.get("data_entrada") or date.today().strftime("%Y-%m-%d"))[:10]
        try:
            dt_base = datetime.datetime.strptime(data_entrada, "%Y-%m-%d").date()
        except Exception:
            dt_base = date.today()
            data_entrada = dt_base.strftime("%Y-%m-%d")

        cur = conn.cursor()
        # Resolve conta de débito
        cur.execute("SELECT id, nome FROM contas_config WHERE COALESCE(tipo, '') != 'cofrinho' ORDER BY id ASC")
        contas_disp = cur.fetchall()
        mapa_id = {int(c["id"]): c["nome"] for c in contas_disp}
        mapa_nome = {str(c["nome"]).strip().lower(): int(c["id"]) for c in contas_disp}

        conta_req = data.get("conta_id") or data.get("conta") or "Mercado Pago"
        conta_id = None
        if str(conta_req).isdigit() and int(conta_req) in mapa_id:
            conta_id = int(conta_req)
        else:
            conta_id = mapa_nome.get(str(conta_req).strip().lower(), 1)
        conta_nome = mapa_id.get(conta_id, "Mercado Pago")

        # Gera ou lê as 4 parcelas enviadas pelo formulário calculadas em cima do valor final
        parcelas_req = data.get("parcelas")
        val_base = round(valor_final / 4.0, 2)
        val_p1_padrao = round(valor_final - (val_base * 3), 2)

        parcelas_final = []
        if isinstance(parcelas_req, list) and len(parcelas_req) == 4:
            for idx, p in enumerate(parcelas_req, start=1):
                dt_p = str(p.get("data") or (dt_base + timedelta(days=14 * (idx - 1))).strftime("%Y-%m-%d"))[:10]
                vp_raw = str(p.get("valor") if p.get("valor") is not None else (val_p1_padrao if idx == 1 else val_base))
                if "," in vp_raw and "." in vp_raw:
                    vp_raw = vp_raw.replace(".", "").replace(",", ".")
                elif "," in vp_raw:
                    vp_raw = vp_raw.replace(",", ".")
                vp = round(float(vp_raw or 0.0), 2)
                parcelas_final.append({
                    "numero": idx,
                    "data": dt_p,
                    "valor": vp,
                    "pago": 1 if idx == 1 else 0
                })
        else:
            for idx in range(1, 5):
                dt_p = (dt_base + timedelta(days=14 * (idx - 1))).strftime("%Y-%m-%d")
                vp = val_p1_padrao if idx == 1 else val_base
                parcelas_final.append({
                    "numero": idx,
                    "data": dt_p,
                    "valor": vp,
                    "pago": 1 if idx == 1 else 0
                })

        soma_parcelas = round(sum(p["valor"] for p in parcelas_final), 2)
        slug = re.sub(r"[^a-z0-9]+", "_", descricao.lower()).strip("_")[:20] or "compra"
        grp_id = f"pagaleve_{slug}_{int(datetime.datetime.now().timestamp())}"

        # Garante colunas em pagaleve_compras
        cur.execute("PRAGMA table_info(pagaleve_compras)")
        cols_plc = [c["name"] for c in cur.fetchall()]
        if "juros" not in cols_plc:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN juros REAL DEFAULT 0")
        if "desconto" not in cols_plc:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN desconto REAL DEFAULT 0")
        if "motivo_ajuste" not in cols_plc:
            cur.execute("ALTER TABLE pagaleve_compras ADD COLUMN motivo_ajuste TEXT")
        conn.commit()

        # 1. Registra contrato em pagaleve_compras
        cur.execute("""
            INSERT INTO pagaleve_compras (
                grupo_parcelamento, descricao, titular, valor_original,
                total_parcelas, valor_parcela, valor_financiado_total, data_compra, status,
                juros, desconto, motivo_ajuste
            ) VALUES (?, ?, ?, ?, 4, ?, ?, ?, 'ativa', ?, ?, ?)
        """, (grp_id, descricao, titular, valor_total, val_base, soma_parcelas, data_entrada, juros, desconto, motivo_ajuste))

        # 2. Insere as 4 parcelas em transacoes com divisão proporcional de juros/desconto
        j_base = round(juros / 4.0, 2)
        j_p1 = round(juros - (j_base * 3), 2)
        d_base = round(desconto / 4.0, 2)
        d_p1 = round(desconto - (d_base * 3), 2)

        ids_inseridos = []
        for p in parcelas_final:
            num = p["numero"]
            dt_p = p["data"]
            val_p = p["valor"]
            eh_paga = (num == 1)
            desc_parc = f"{descricao} - Paga Leve {num}/4"
            parc_juros = j_p1 if num == 1 else j_base
            parc_desconto = d_p1 if num == 1 else d_base

            cur.execute("""
                INSERT INTO transacoes (
                    data, data_liquidacao, descricao, valor, tipo, categoria, subcategoria,
                    conta, conta_id, pago, status_pagamento, grupo_parcelamento,
                    numero_parcela, total_parcelas_compra, titular, afeta_saldo_bancario,
                    juros, desconto, motivo_ajuste
                ) VALUES (?, ?, ?, ?, 'despesa', ?, ?, ?, ?, ?, ?, ?, ?, 4, ?, ?, ?, ?, ?)
            """, (
                dt_p,
                dt_p if eh_paga else None,
                desc_parc,
                val_p,
                categoria,
                subcategoria,
                conta_nome,
                conta_id,
                1 if eh_paga else 0,
                "PAGA" if eh_paga else "pendente",
                grp_id,
                num,
                titular,
                1 if eh_paga else 0,
                parc_juros,
                parc_desconto,
                motivo_ajuste
            ))
            tid = cur.lastrowid
            ids_inseridos.append(tid)

            # Registra o pagamento auditável da 1ª parcela (entrada paga no ato)
            if eh_paga:
                try:
                    saldo_service.registrar_pagamento(
                        conn=conn,
                        transacao_id=tid,
                        data_pagamento=dt_p,
                        valor_pago=val_p,
                        conta_id=conta_id,
                        afeta_saldo_bancario=1,
                        considerado_no_marco=0,
                        forma_pagamento="Pix",
                        observacao=f"Entrada 1/4 Paga Leve no ato: {descricao}"
                    )
                except Exception:
                    pass

        conn.commit()
        return JSONResponse({
            "sucesso": True,
            "grupo_id": grp_id,
            "ids": ids_inseridos,
            "mensagem": f"Compra '{descricao}' cadastrada com sucesso (1ª parcela quitada no ato e 3 quinzenais geradas)!"
        })
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/pagaleve/parcela/editar")
@app.post("/api/pagaleve/parcela/{parcela_id}/editar")
async def api_pagaleve_editar_parcela(request: Request, parcela_id: Optional[int] = None):
    """Permite editar individualmente a data de vencimento, o valor ou a descrição de uma parcela Paga Leve."""
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        tid = parcela_id or int(data.get("id") or data.get("parcela_id") or 0)
        if not tid:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "ID da parcela não informado."})

        nova_data = str(data.get("data") or "").strip()[:10]
        if not nova_data:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Informe a data de vencimento."})

        val_raw = str(data.get("valor") or "0").strip()
        if "," in val_raw and "." in val_raw:
            val_raw = val_raw.replace(".", "").replace(",", ".")
        elif "," in val_raw:
            val_raw = val_raw.replace(",", ".")
        novo_valor = round(float(val_raw or 0.0), 2)
        if novo_valor <= 0:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "O valor da parcela deve ser maior que zero."})

        nova_desc = str(data.get("descricao") or "").strip()

        cur = conn.cursor()
        cur.execute("SELECT id, descricao, pago, grupo_parcelamento FROM transacoes WHERE id = ?", (tid,))
        row = cur.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Parcela não encontrada."})

        desc_final = nova_desc if nova_desc else row["descricao"]
        grp_id = row["grupo_parcelamento"]

        if row["pago"] == 1:
            cur.execute("""
                UPDATE transacoes
                SET data = ?, data_liquidacao = COALESCE(data_liquidacao, ?), valor = ?, descricao = ?
                WHERE id = ?
            """, (nova_data, nova_data, novo_valor, desc_final, tid))
        else:
            cur.execute("""
                UPDATE transacoes
                SET data = ?, valor = ?, descricao = ?
                WHERE id = ?
            """, (nova_data, novo_valor, desc_final, tid))

        # Atualiza valor_original em pagaleve_compras se todas as parcelas estiverem vinculadas
        if grp_id:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(valor), 0) FROM transacoes WHERE grupo_parcelamento = ?", (grp_id,))
            cnt, soma = cur.fetchone()
            cur.execute("SELECT total_parcelas, valor_parcela FROM pagaleve_compras WHERE grupo_parcelamento = ?", (grp_id,))
            meta_row = cur.fetchone()
            if meta_row:
                tot_p = int(meta_row["total_parcelas"] or 4)
                vp_ant = float(meta_row["valor_parcela"] or 0.0)
                faltantes = max(0, tot_p - int(cnt or 0))
                novo_total_contrato = round(float(soma or 0.0) + (faltantes * vp_ant), 2)
                cur.execute("""
                    UPDATE pagaleve_compras
                    SET valor_original = ?, valor_financiado_total = ?
                    WHERE grupo_parcelamento = ?
                """, (novo_total_contrato, novo_total_contrato, grp_id))

        conn.commit()
        return JSONResponse({
            "sucesso": True,
            "id": tid,
            "data": nova_data,
            "valor": novo_valor,
            "mensagem": "Parcela atualizada com sucesso!"
        })
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/pagaleve/pagar-selecionadas")
@app.post("/api/pagaleve/antecipar")
async def api_pagaleve_pagar_selecionadas(request: Request):
    """
    Liquida em lote as parcelas Paga Leve selecionadas (pagamento / antecipação),
    registrando a saída correspondente na conta informada.
    """
    conn = conectar_db()
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        raw_ids = data.get("parcela_ids") or data.get("ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()]
        else:
            raw_ids = [int(x) for x in raw_ids if str(x).isdigit()]

        if not raw_ids:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "Selecione ao menos uma parcela pendente."})

        data_pagamento = str(data.get("data_pagamento") or date.today().strftime("%Y-%m-%d"))[:10]

        cur = conn.cursor()
        cur.execute("SELECT id, nome FROM contas_config WHERE COALESCE(tipo, '') != 'cofrinho' ORDER BY id ASC")
        contas_disp = cur.fetchall()
        mapa_id = {int(c["id"]): c["nome"] for c in contas_disp}
        mapa_nome = {str(c["nome"]).strip().lower(): int(c["id"]) for c in contas_disp}

        conta_req = data.get("conta_id") or data.get("conta") or "Mercado Pago"
        if str(conta_req).isdigit() and int(conta_req) in mapa_id:
            conta_id = int(conta_req)
        else:
            conta_id = mapa_nome.get(str(conta_req).strip().lower(), 1)
        conta_nome = mapa_id.get(conta_id, "Mercado Pago")

        placeholders = ",".join("?" for _ in raw_ids)
        cur.execute(f"""
            SELECT id, descricao, valor, pago, grupo_parcelamento
            FROM transacoes
            WHERE id IN ({placeholders})
        """, tuple(raw_ids))
        parcelas_rows = cur.fetchall()

        pendentes = [r for r in parcelas_rows if r["pago"] != 1]
        if not pendentes:
            return JSONResponse(status_code=400, content={"sucesso": False, "erro": "As parcelas selecionadas já estão quitadas."})

        total_liquidado = round(sum(float(r["valor"] or 0.0) for r in pendentes), 2)
        qtd_liquidadas = len(pendentes)
        obs_lote = f"Saída única Paga Leve ({qtd_liquidadas} parcela(s) - {formatar_moeda_br(total_liquidado)}) debitada em {conta_nome}"

        grupos_afetados = set()
        for r in pendentes:
            pid = int(r["id"])
            val_p = float(r["valor"] or 0.0)
            if r["grupo_parcelamento"]:
                grupos_afetados.add(r["grupo_parcelamento"])

            saldo_service.registrar_pagamento(
                conn=conn,
                transacao_id=pid,
                data_pagamento=data_pagamento,
                valor_pago=val_p,
                conta_id=conta_id,
                afeta_saldo_bancario=1,
                considerado_no_marco=0,
                forma_pagamento="Pix",
                observacao=obs_lote,
                tipo_ajuste_valor="normal"
            )

        # Atualiza status para 'quitada' nos contratos que não possuem mais parcelas pendentes
        for grp in grupos_afetados:
            cur.execute("""
                SELECT COUNT(*) FROM transacoes
                WHERE grupo_parcelamento = ? AND (pago = 0 OR pago IS NULL)
            """, (grp,))
            restantes = cur.fetchone()[0]
            if restantes == 0:
                cur.execute("UPDATE pagaleve_compras SET status = 'quitada' WHERE grupo_parcelamento = ?", (grp,))

        conn.commit()
        return JSONResponse({
            "sucesso": True,
            "quantidade": qtd_liquidadas,
            "valor_total": total_liquidado,
            "valor_total_formatado": formatar_moeda_br(total_liquidado),
            "conta_nome": conta_nome,
            "mensagem": f"{qtd_liquidadas} parcela(s) liquidada(s) ({formatar_moeda_br(total_liquidado)}) com débito em {conta_nome}!"
        })
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


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


# =============================================================================
# ROTAS: PLANEJAMENTO & ANÁLISE FINANCEIRA
# =============================================================================

@app.get("/planejamento", response_class=HTMLResponse)
async def pagina_planejamento(
    request: Request,
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    periodo: Optional[str] = Query(None)
):
    conn = conectar_db()
    hoje = date.today()

    if periodo and "-" in str(periodo):
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

    opcoes_periodo = []
    anos_disp = sorted(list({hoje.year - 1, hoje.year, ano, ano + 1}))
    for a in anos_disp:
        for m in range(1, 13):
            opcoes_periodo.append({
                "valor": f"{a}-{m:02d}",
                "label": f"{MESES_PT[m]} {a}",
                "mes": m,
                "ano": a,
                "selecionado": (a == ano and m == mes)
            })

    cur = conn.cursor()

    # 1. Receitas e Despesas do Mês Selecionado
    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN tipo = 'receita' AND pago = 1 THEN valor ELSE 0 END), 0) as receitas_pagas,
            COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END), 0) as total_receitas,
            COALESCE(SUM(CASE WHEN tipo = 'despesa' AND pago = 1 THEN valor ELSE 0 END), 0) as despesas_pagas,
            COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END), 0) as total_despesas
        FROM transacoes
        WHERE data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    tot_row = cur.fetchone()
    receitas_pagas = float(tot_row[0]) if tot_row else 0.0
    total_receitas = float(tot_row[1]) if tot_row else 0.0
    despesas_pagas = float(tot_row[2]) if tot_row else 0.0
    total_despesas = float(tot_row[3]) if tot_row else 0.0

    resultado_operacional = round(receitas_pagas - despesas_pagas, 2)

    # 2. Compromissos e Atrasadas
    hoje_iso = hoje.strftime("%Y-%m-%d")
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0), COUNT(*)
        FROM transacoes
        WHERE tipo = 'despesa' AND pago = 0 AND data < ?
    """, (hoje_iso,))
    row_atr = cur.fetchone()
    total_atrasadas = float(row_atr[0]) if row_atr else 0.0
    qtd_atrasadas = int(row_atr[1]) if row_atr else 0

    cur.execute("""
        SELECT COALESCE(SUM(valor), 0), COUNT(*)
        FROM transacoes
        WHERE tipo = 'despesa' AND pago = 0 AND data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    row_pend_mes = cur.fetchone()
    total_pendente_mes = float(row_pend_mes[0]) if row_pend_mes else 0.0

    # 3. Saldo em Caixa Livre Consolidado
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    saldo_caixa = float(res_saldo.get("saldo_consolidado", 0.0))

    # 4. INDICADOR DE SAÚDE FINANCEIRA (Score 0 a 100)
    # A) Superávit / Margem de Poupança (0 a 40 pts)
    if receitas_pagas > 0:
        tx_poupanca = (receitas_pagas - despesas_pagas) / receitas_pagas
        if tx_poupanca >= 0.20:
            pts_poupanca = 40
        elif tx_poupanca >= 0.10:
            pts_poupanca = 32
        elif tx_poupanca >= 0.0:
            pts_poupanca = 24
        elif tx_poupanca >= -0.20:
            pts_poupanca = 14
        else:
            pts_poupanca = 5
    else:
        pts_poupanca = 20 if despesas_pagas == 0 else 5

    # B) Dívidas e Atrasadas (0 a 30 pts)
    if total_atrasadas == 0:
        pts_dividas = 30
    elif total_atrasadas < 150:
        pts_dividas = 22
    elif total_atrasadas < 500:
        pts_dividas = 12
    else:
        pts_dividas = 5

    # C) Caixa Livre / Liquidez (0 a 30 pts)
    if saldo_caixa >= 300:
        pts_caixa = 30
    elif saldo_caixa >= 100:
        pts_caixa = 22
    elif saldo_caixa > 0:
        pts_caixa = 15
    else:
        pts_caixa = 2

    score_saude = min(100, max(0, pts_poupanca + pts_dividas + pts_caixa))

    if score_saude >= 80:
        status_saude = "Excelente"
        cor_saude = "emerald"
        msg_saude = "Finanças com superávit consistente e liquidez positiva. Excelente momento para fortalecer reservas e cofrinhos."
    elif score_saude >= 60:
        status_saude = "Equilibrada"
        cor_saude = "amber"
        msg_saude = "Contas sob controle com margem operacional estável. Mantenha os limites de orçamento para expandir o caixa."
    elif score_saude >= 40:
        status_saude = "Atenção"
        cor_saude = "orange"
        msg_saude = "Despesas próximas da receita ou compromissos pendentes. Monitore os limites das categorias para evitar deficit."
    else:
        status_saude = "Crítica"
        cor_saude = "rose"
        msg_saude = "Alerta de pressão no fluxo de caixa. Priorize a quitação de atrasadas e contenção imediata de gastos variáveis."

    # 5. ORÇAMENTO POR CATEGORIA (Budget vs Realizado)
    cur.execute("CREATE TABLE IF NOT EXISTS limites_categoria (categoria TEXT PRIMARY KEY, limite REAL NOT NULL)")
    cur.execute("SELECT categoria, limite FROM limites_categoria")
    limites_db = {r[0]: float(r[1]) for r in cur.fetchall()}

    cur.execute("""
        SELECT categoria, COALESCE(SUM(valor), 0) as gasto_real, COUNT(*) as qtd
        FROM transacoes
        WHERE tipo = 'despesa' AND data BETWEEN ? AND ?
        GROUP BY categoria
        ORDER BY gasto_real DESC
    """, (inicio_mes, fim_mes))
    rows_cats = cur.fetchall()

    gastos_por_cat = {}
    for r in rows_cats:
        c_orig = (r[0] or "Outros").strip()
        gastos_por_cat[c_orig] = {
            "gasto_real": round(float(r[1]), 2),
            "qtd": int(r[2])
        }

    todas_categorias = sorted(list(set(list(gastos_por_cat.keys()) + list(limites_db.keys()))))

    orcamento_categorias = []
    total_orcado_geral = 0.0
    total_gasto_com_limite = 0.0
    total_gasto_geral = 0.0
    qtd_sem_limite = 0

    for cat in todas_categorias:
        gasto_info = gastos_por_cat.get(cat, {"gasto_real": 0.0, "qtd": 0})
        g_real = gasto_info["gasto_real"]
        total_gasto_geral += g_real

        tem_limite = cat in limites_db
        if tem_limite:
            limite = limites_db[cat]
            total_orcado_geral += limite
            total_gasto_com_limite += g_real
            pct = round((g_real / limite) * 100, 1) if limite > 0 else 0.0
            pct_barra = min(100.0, pct)
            dif = round(limite - g_real, 2)

            if pct < 80:
                status_cor = "emerald"
                status_texto = "Dentro do Orçamento"
            elif pct <= 100:
                status_cor = "amber"
                status_texto = "Perto do Limite"
            else:
                status_cor = "rose"
                status_texto = "Orçamento Estourado!"
        else:
            limite = None
            pct = None
            pct_barra = 0.0
            dif = None
            status_cor = "slate"
            status_texto = "Sem limite definido"
            qtd_sem_limite += 1

        cat_lower = cat.lower()
        if "combust" in cat_lower or "abast" in cat_lower:
            icone = "⛽"
        elif "supermerc" in cat_lower or "feira" in cat_lower or "alimen" in cat_lower:
            icone = "🛒"
        elif "habit" in cat_lower or "moradia" in cat_lower or "contas" in cat_lower:
            icone = "🏠"
        elif "saude" in cat_lower or "saúde" in cat_lower or "medic" in cat_lower:
            icone = "💊"
        elif "veic" in cat_lower or "veíc" in cat_lower or "manut" in cat_lower or "ipva" in cat_lower:
            icone = "🚗"
        elif "restaur" in cat_lower or "padaria" in cat_lower or "lanche" in cat_lower:
            icone = "🍔"
        elif "stream" in cat_lower or "assina" in cat_lower:
            icone = "📺"
        elif "pessoal" in cat_lower or "barbearia" in cat_lower:
            icone = "✂️"
        elif "acordo" in cat_lower or "divida" in cat_lower or "dívida" in cat_lower or "emprést" in cat_lower:
            icone = "📑"
        else:
            icone = "📦"

        orcamento_categorias.append({
            "categoria": cat,
            "icone": icone,
            "gasto_real": g_real,
            "orcado": limite,
            "tem_limite": tem_limite,
            "diferenca": dif,
            "percentual": pct,
            "percentual_barra": pct_barra,
            "status_cor": status_cor,
            "status_texto": status_texto,
            "qtd_transacoes": gasto_info["qtd"]
        })

    orcamento_categorias.sort(key=lambda x: x["gasto_real"], reverse=True)
    pct_geral_orcamento = round((total_gasto_com_limite / total_orcado_geral) * 100, 1) if total_orcado_geral > 0 else 0.0

    # 6. JUROS E DESCONTOS NO MÊS SELECIONADO
    # Descontos de despesas gerais (tabela transacoes)
    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN juros > 0 THEN juros ELSE 0 END), 0) as total_juros_mes,
            COALESCE(SUM(CASE WHEN desconto > 0 AND (categoria != 'Combustível (Trabalho)' OR categoria IS NULL) THEN desconto ELSE 0 END), 0) as total_descontos_transacoes
        FROM transacoes
        WHERE data BETWEEN ? AND ?
    """, (inicio_mes, fim_mes))
    row_jd = cur.fetchone()
    total_juros_mes = round(float(row_jd[0]), 2) if row_jd else 0.0
    total_descontos_transacoes = round(float(row_jd[1]), 2) if row_jd else 0.0

    # Descontos da tabela veiculo_abastecimentos (Economia 99 Abastece, SouTag, Shell Box, etc.)
    cur.execute("""
        SELECT COALESCE(SUM(desconto), 0) as total_descontos_abast
        FROM veiculo_abastecimentos
        WHERE SUBSTR(data, 1, 10) BETWEEN ? AND ? AND desconto > 0
    """, (inicio_mes, fim_mes))
    row_ab_desc = cur.fetchone()
    total_descontos_abast = round(float(row_ab_desc[0]), 2) if row_ab_desc else 0.0

    total_descontos_mes = round(total_descontos_transacoes + total_descontos_abast, 2)

    cur.execute("""
        SELECT id, data, descricao, categoria, valor, juros, desconto, COALESCE(motivo_ajuste, '') as motivo_ajuste, pago, conta
        FROM transacoes
        WHERE (juros > 0 OR (desconto > 0 AND (categoria != 'Combustível (Trabalho)' OR categoria IS NULL))) AND data BETWEEN ? AND ?
        ORDER BY data DESC, id DESC
    """, (inicio_mes, fim_mes))
    rows_aj = cur.fetchall()
    lancamentos_ajustes = []
    for r in rows_aj:
        dt_str = str(r[1])[:10]
        try:
            dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str
        lancamentos_ajustes.append({
            "id": r[0],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": r[2] or "Sem descrição",
            "categoria": r[3] or "Geral",
            "valor": float(r[4] or 0.0),
            "juros": float(r[5] or 0.0),
            "desconto": float(r[6] or 0.0),
            "motivo_ajuste": r[7] or "",
            "pago": int(r[8] or 0),
            "conta": r[9] or "Mercado Pago"
        })

    # Inclui no detalhamento dos descontos os abastecimentos com economia do mês
    cur.execute("""
        SELECT id, data, combustivel, litros, preco_litro, valor_pago, desconto, app_desconto, posto, conta
        FROM veiculo_abastecimentos
        WHERE SUBSTR(data, 1, 10) BETWEEN ? AND ? AND desconto > 0
        ORDER BY data DESC, id DESC
    """, (inicio_mes, fim_mes))
    rows_ab = cur.fetchall()
    for ab in rows_ab:
        dt_str = str(ab[1])[:10]
        try:
            dt_fmt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            dt_fmt = dt_str
        comb = ab[2] or "Combustível"
        app_origem = ab[7] or "99 Abastece"
        val_desc = float(ab[6] or 0.0)
        lancamentos_ajustes.append({
            "id": f"abast-{ab[0]}",
            "data": dt_str,
            "data_formatada": dt_fmt,
            "descricao": f"Abastecimento {comb} - Economia {app_origem}: {formatar_moeda_br(val_desc)}",
            "categoria": "Combustível (Trabalho)",
            "valor": float(ab[5] or 0.0),
            "juros": 0.0,
            "desconto": val_desc,
            "motivo_ajuste": f"Economia via {app_origem}",
            "pago": 1,
            "conta": ab[9] or "Mercado Pago"
        })

    # Ordena todos os lançamentos com juros ou descontos por data decrescente
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
            "naturezas_disponiveis": naturezas_disponiveis,
            "mes": mes,
            "ano": ano,
            "hoje_formatado": hoje.strftime("%d/%m/%Y"),
            "mes_nome": mes_nome,
            "mes_ant": mes_ant,
            "ano_ant": ano_ant,
            "mes_prox": mes_prox,
            "ano_prox": ano_prox,
            "eh_mes_atual": eh_mes_atual,
            "opcoes_periodo": opcoes_periodo,
            "receitas_pagas": receitas_pagas,
            "total_receitas": total_receitas,
            "despesas_pagas": despesas_pagas,
            "total_despesas": total_despesas,
            "resultado_operacional": resultado_operacional,
            "total_atrasadas": total_atrasadas,
            "qtd_atrasadas": qtd_atrasadas,
            "total_pendente_mes": total_pendente_mes,
            "saldo_caixa": saldo_caixa,
            "score_saude": score_saude,
            "pts_poupanca": pts_poupanca,
            "pts_dividas": pts_dividas,
            "pts_caixa": pts_caixa,
            "status_saude": status_saude,
            "cor_saude": cor_saude,
            "msg_saude": msg_saude,
            "orcamento_categorias": orcamento_categorias,
            "total_orcado_geral": total_orcado_geral,
            "total_gasto_com_limite": total_gasto_com_limite,
            "total_gasto_geral": total_gasto_geral,
            "qtd_sem_limite": qtd_sem_limite,
            "pct_geral_orcamento": pct_geral_orcamento,
            "total_juros_mes": total_juros_mes,
            "total_descontos_mes": total_descontos_mes,
            "lancamentos_ajustes": lancamentos_ajustes,
            "active_tab": "planejamento"
        }
    )


@app.post("/api/planejamento/limite")
async def api_salvar_limite_categoria(
    categoria: str = Form(...),
    limite: Any = Form(...)
):
    val_limite = converter_valor_monetario(limite)
    if val_limite < 0:
        return JSONResponse(status_code=400, content={"status": "erro", "erro": "Limite não pode ser negativo."})

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS limites_categoria (categoria TEXT PRIMARY KEY, limite REAL NOT NULL)")
        cur.execute("""
            INSERT INTO limites_categoria (categoria, limite)
            VALUES (?, ?)
            ON CONFLICT(categoria) DO UPDATE SET limite = excluded.limite
        """, (categoria.strip(), val_limite))
        conn.commit()
        return {"status": "sucesso", "sucesso": True, "mensagem": f"Orçamento da categoria '{categoria}' atualizado para {formatar_moeda_br(val_limite)}!"}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"status": "erro", "erro": str(e)})
    finally:
        conn.close()


@app.get("/drive", response_class=HTMLResponse)
@app.get("/motorista", response_class=HTMLResponse)
@app.get("/oikos-drive", response_class=HTMLResponse)
async def pagina_motorista(
    request: Request,
    filtro: Optional[str] = "semana",
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    periodo: Optional[str] = Query(None)
):
    conn = conectar_db()
    hoje = date.today()

    if periodo and "-" in str(periodo):
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

    # Início e fim do mês selecionado
    inicio_mes = f"{ano}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    fim_mes = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

    # Dropdown de seleção de mês/ano
    opcoes_periodo = []
    anos_disp = sorted(list({hoje.year - 1, hoje.year, ano, ano + 1}))
    for a in anos_disp:
        for m in range(1, 13):
            opcoes_periodo.append({
                "valor": f"{a}-{m:02d}",
                "label": f"{MESES_PT[m]} {a}",
                "mes": m,
                "ano": a,
                "selecionado": (a == ano and m == mes)
            })

    hoje_str = hoje.strftime("%Y-%m-%d")

    cur = conn.cursor()

    # Início e fim da semana estritamente de SEGUNDA a DOMINGO usando lógica padrão ISO SQLite
    cur.execute("SELECT date(?, 'weekday 0', '-6 days'), date(?, 'weekday 0')", (hoje_str, hoje_str))
    row_sem = cur.fetchone()
    inicio_semana = row_sem[0] if row_sem else (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
    fim_semana = row_sem[1] if row_sem else (hoje + timedelta(days=6 - hoje.weekday())).strftime("%Y-%m-%d")

    # Produção 99 consolidada oficial respeitando o mês de referência consultado
    dia_ref = min(hoje.day if eh_mes_atual else ultimo_dia, ultimo_dia)
    data_ref_drive = date(ano, mes, dia_ref)
    prod_99 = saldo_service.obter_producao_consolidada_99(conn, data_ref=data_ref_drive)
    total_mes_bruto = float(prod_99.get("total_mes_bruto", 0.0))
    marco_bruto = float(prod_99.get("marco", {}).get("faturamento_bruto", 0.0) if prod_99.get("marco") else 0.0)
    semana_bruto = float(prod_99.get("semana", {}).get("bruto", 0.0))
    recebido_online = float(prod_99.get("total_mes_online", 0.0))
    recebido_dinheiro = float(prod_99.get("total_mes_dinheiro", 0.0))

    # Obter saldos das contas para transferências rápidas
    res_saldo = saldo_service.calcular_saldo_consolidado(conn)
    contas_lista = res_saldo.get("contas", [])
    
    cart_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["dinheiro", "carteira"])), None)
    cart_saldo = float(cart_conta["saldo_atual"]) if cart_conta else 7.0

    app_99_conta = next((c for c in contas_lista if any(k in c["conta_nome"].lower() for k in ["99pay", "99 pay", "saldo 99"])), None)
    saldo_99_app = float(app_99_conta["saldo_atual"]) if app_99_conta else 0.0

    # Todos os turnos com todos os campos de controle operacional
    cur.execute("""
        SELECT id, data, horas, km, ganho_bruto, combustivel, observacao, periodo, plataforma,
               ganho_dinheiro_pix, ganho_online, hora_inicio, hora_fim, km_inicial, km_final,
               status_turno, status_conciliacao, created_at
        FROM turnos
        ORDER BY 
            CASE WHEN UPPER(COALESCE(status_turno, '')) IN ('EM_ANDAMENTO', 'PAUSADO') THEN 0 ELSE 1 END,
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
            st_turno_norm = "EM_ANDAMENTO"
            tag_codigo = "EM_ANDAMENTO"
            tag_label = "● Em Andamento"
            tag_badge = "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20 animate-pulse font-bold"
        elif st_upper == "PAUSADO":
            st_turno_norm = "PAUSADO"
            tag_codigo = "PAUSADO"
            tag_label = "⏸️ Pausado"
            tag_badge = "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20 animate-pulse font-bold"
        elif km_val <= 0:
            st_turno_norm = st_turno
            tag_codigo = "PENDENTE_KM"
            tag_label = "⚠️ Pendente KM"
            tag_badge = "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20 font-bold"
        elif bruto_val <= 0:
            st_turno_norm = st_turno
            tag_codigo = "A_CONFIRMAR"
            tag_label = "⚠️ A Confirmar"
            tag_badge = "bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20 font-bold"
        else:
            st_turno_norm = st_turno
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
            "status_turno": st_turno_norm,
            "status_conciliacao": r["status_conciliacao"] or "conciliado",
            "tag_codigo": tag_codigo,
            "tag_label": tag_label,
            "tag_badge": tag_badge,
            "prod_hora": prod_hora,
            "created_at": r["created_at"] or ""
        })

    # Detecta se há turno ativo rodando em tempo real (EM_ANDAMENTO ou PAUSADO)
    turno_ativo = next((t for t in turnos if t["status_turno"].upper() in ("EM_ANDAMENTO", "PAUSADO")), None)

    pausas_turno = []
    pausa_ativa = None
    total_segundos_pausa_anteriores = 0

    if turno_ativo:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS turnos_pausas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turno_id INTEGER NOT NULL,
                inicio_pausa TEXT NOT NULL,
                fim_pausa TEXT,
                duracao_minutos INTEGER DEFAULT 0,
                duracao_programada_minutos INTEGER DEFAULT 0,
                motivo TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (turno_id) REFERENCES turnos(id)
            )
        """)
        conn.commit()

        cur.execute("""
            SELECT id, inicio_pausa, fim_pausa, duracao_minutos, duracao_programada_minutos, motivo, created_at
            FROM turnos_pausas
            WHERE turno_id = ?
            ORDER BY id ASC
        """, (turno_ativo["id"],))
        rows_p = cur.fetchall()
        for rp in rows_p:
            p_dict = {
                "id": rp["id"],
                "inicio_pausa": rp["inicio_pausa"],
                "fim_pausa": rp["fim_pausa"],
                "duracao_minutos": int(rp["duracao_minutos"] or 0),
                "duracao_programada_minutos": int(rp["duracao_programada_minutos"] or 0),
                "motivo": rp["motivo"] or "Descanso",
                "created_at": rp["created_at"] or ""
            }
            pausas_turno.append(p_dict)
            if not p_dict["fim_pausa"]:
                pausa_ativa = p_dict
            else:
                total_segundos_pausa_anteriores += p_dict["duracao_minutos"] * 60

        turno_ativo["pausas"] = pausas_turno
        turno_ativo["pausa_ativa"] = pausa_ativa
        turno_ativo["total_minutos_pausa"] = total_segundos_pausa_anteriores // 60
        turno_ativo["total_segundos_pausa"] = total_segundos_pausa_anteriores

        # Formata hora de início com segundos para garantir timestamp ISO sem NaN
        h_ini_c = str(turno_ativo.get("hora_inicio") or "00:00").strip()
        if len(h_ini_c) == 5:
            h_ini_c += ":00"
        elif len(h_ini_c) == 4:
            h_ini_c = f"0{h_ini_c}:00"
        elif not h_ini_c:
            h_ini_c = "00:00:00"

        turno_ativo["hora_inicio_completa"] = h_ini_c
        turno_ativo["timestamp_inicio_iso"] = f"{turno_ativo.get('data')}T{h_ini_c}"
        turno_ativo["data_hora_inicio"] = f"{turno_ativo.get('data')}T{h_ini_c}"

    turno_ativo_json = json.dumps(turno_ativo, default=str) if turno_ativo else "null"

    # Abastecimentos reais registrados (Drivvo)
    cur.execute("PRAGMA table_info(veiculo_abastecimentos)")
    cols_abast = [c["name"] for c in cur.fetchall()]
    if "app_desconto" not in cols_abast:
        cur.execute("ALTER TABLE veiculo_abastecimentos ADD COLUMN app_desconto TEXT DEFAULT 'Nenhum'")
        conn.commit()

    cur.execute("""
        SELECT id, data, valor_bruto, desconto, valor_pago, litros, combustivel,
               preco_litro, posto, hodometro, observacao, COALESCE(app_desconto, '') as app_desconto,
               COALESCE(conta, 'Dinheiro / Carteira') as conta
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

        val_pago = round(float(a["valor_pago"] or 0.0), 2)
        val_bomba = round(float(a["valor_bruto"] or val_pago), 2)
        economia = round(max(0.0, val_bomba - val_pago), 2) if val_bomba > val_pago else round(float(a["desconto"] or 0.0), 2)
        if val_bomba < val_pago + economia:
            val_bomba = round(val_pago + economia, 2)

        pct_economia = round((economia / val_bomba) * 100.0, 1) if (val_bomba > 0 and economia > 0) else 0.0
        lits = round(float(a["litros"] or 0.0), 3)
        # Preço Real por Litro = Valor Pago Real / Litros
        preco_real_litro = round(val_pago / lits, 3) if lits > 0 else float(a["preco_litro"] or 0.0)
        preco_bomba_litro = round(val_bomba / lits, 3) if lits > 0 else preco_real_litro

        app_raw = (a["app_desconto"] or "").strip()
        obs_str = a["observacao"] or ""
        if not app_raw or app_raw == "Nenhum":
            if economia > 0:
                obs_low = obs_str.lower()
                if "99" in obs_low:
                    app_nome = "99 Abastece"
                elif "shell" in obs_low:
                    app_nome = "Shell Box"
                elif "soutag" in obs_low:
                    app_nome = "SouTag"
                elif "premmia" in obs_low:
                    app_nome = "Premmia"
                else:
                    app_nome = "Posto / Outro"
            else:
                app_nome = "Nenhum"
        else:
            app_nome = app_raw

        economia_badge = f"Economia de {formatar_moeda_br(economia)} ({pct_economia:.1f}%) via {app_nome}" if economia > 0 else ""

        abastecimentos.append({
            "id": a["id"],
            "data": dt_str,
            "data_formatada": dt_fmt,
            "valor_bomba": val_bomba,
            "valor_pago": val_pago,
            "economia": economia,
            "pct_economia": pct_economia,
            "app_desconto": app_nome,
            "economia_badge": economia_badge,
            "litros": lits,
            "combustivel": a["combustivel"] or "Etanol",
            "preco_litro": preco_real_litro,
            "preco_bomba_litro": preco_bomba_litro,
            "posto": a["posto"] or "Posto de Combustível",
            "conta": a["conta"] or "Dinheiro / Carteira",
            "hodometro": float(a["hodometro"] or 0.0),
            "observacao": obs_str
        })

    # Totais globais de abastecimento real para referência de consumo (km/L e custo/km)
    tot_litros_global = sum(a["litros"] for a in abastecimentos)
    tot_pago_global = sum(a["valor_pago"] for a in abastecimentos)
    tot_km_global = sum(t["km"] for t in turnos)
    custo_km_global = round(tot_pago_global / tot_km_global, 2) if (tot_km_global > 0 and tot_pago_global > 0) else 0.28
    kml_global = round(tot_km_global / tot_litros_global, 2) if (tot_litros_global > 0 and tot_km_global > 0) else 0.0

    # CÁLCULO DOS 4 INDICADORES OPERACIONAIS POR PERÍODO
    def calcular_metricas(p_tipo):
        if p_tipo == "hoje":
            t_filtro = [t for t in turnos if t["data"] == hoje_str]
            a_filtro = [a for a in abastecimentos if a["data"] == hoje_str]
            bruto = sum(t["ganho_bruto"] for t in t_filtro)
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_litros = sum(a["litros"] for a in a_filtro)
            tot_econ = sum(a["economia"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = round(abast_real / tot_km, 2) if (tot_km > 0 and abast_real > 0) else (custo_km_global if tot_km > 0 else 0.0)
            kml_periodo = round(tot_km / tot_litros, 2) if (tot_km > 0 and tot_litros > 0) else kml_global
            caixa_liquido = bruto - abast_real
            sub_bruto = f"{len(t_filtro)} turno(s) hoje"
            sub_abast = f"{tot_litros:.2f} L • Econ: {formatar_moeda_br(tot_econ)}" if tot_econ > 0 else f"{len(a_filtro)} abastecimento(s) hoje"
            sub_km = f"{kml_periodo:.1f} km/L • {round(tot_km, 1)} km hoje" if kml_periodo > 0 else f"{round(tot_km, 1)} km hoje"
            sub_liq = "Bruto (-) Valor Pago Real"

        elif p_tipo == "semana":
            t_filtro = [t for t in turnos if inicio_semana <= t["data"] <= fim_semana]
            a_filtro = [a for a in abastecimentos if inicio_semana <= a["data"] <= fim_semana]
            bruto = sum(t["ganho_bruto"] for t in t_filtro) if t_filtro else semana_bruto
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_litros = sum(a["litros"] for a in a_filtro)
            tot_econ = sum(a["economia"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = round(abast_real / tot_km, 2) if (tot_km > 0 and abast_real > 0) else custo_km_global
            kml_periodo = round(tot_km / tot_litros, 2) if (tot_km > 0 and tot_litros > 0) else kml_global
            caixa_liquido = bruto - abast_real
            sub_bruto = f"{formatar_moeda_br(bruto)} na semana"
            sub_abast = f"{tot_litros:.2f} L • Econ: {formatar_moeda_br(tot_econ)}" if tot_econ > 0 else f"{tot_litros:.2f} L abastecidos"
            sub_km = f"{kml_periodo:.1f} km/L em {round(tot_km, 1)} km" if kml_periodo > 0 else f"R$ {comb_est:.2f} em {round(tot_km, 1)} km"
            sub_liq = f"R$ {bruto:.2f} - R$ {abast_real:.2f}"

        elif p_tipo == "mes":
            t_filtro = [t for t in turnos if inicio_mes <= t["data"] <= fim_mes]
            a_filtro = [a for a in abastecimentos if inicio_mes <= a["data"] <= fim_mes]
            soma_turnos_mes = sum(t["ganho_bruto"] for t in t_filtro)
            if eh_mes_atual:
                bruto = total_mes_bruto if total_mes_bruto > soma_turnos_mes else soma_turnos_mes
            else:
                bruto = soma_turnos_mes
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_litros = sum(a["litros"] for a in a_filtro)
            tot_econ = sum(a["economia"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = round(abast_real / tot_km, 2) if (tot_km > 0 and abast_real > 0) else custo_km_global
            kml_periodo = round(tot_km / tot_litros, 2) if (tot_km > 0 and tot_litros > 0) else kml_global
            caixa_liquido = bruto - abast_real
            sub_bruto = f"{formatar_moeda_br(bruto)} em {mes_nome}"
            sub_abast = f"{tot_litros:.2f} L • Econ: {formatar_moeda_br(tot_econ)}" if tot_econ > 0 else f"{tot_litros:.2f} L abastecidos"
            sub_km = f"{kml_periodo:.1f} km/L em {round(tot_km, 1)} km" if kml_periodo > 0 else f"R$ {comb_est:.2f} em {round(tot_km, 1)} km"
            sub_liq = f"R$ {bruto:.2f} - R$ {abast_real:.2f}"

        else: # todos
            t_filtro = turnos
            a_filtro = abastecimentos
            bruto = total_mes_bruto
            abast_real = sum(a["valor_pago"] for a in a_filtro)
            tot_litros = sum(a["litros"] for a in a_filtro)
            tot_econ = sum(a["economia"] for a in a_filtro)
            tot_km = sum(t["km"] for t in t_filtro)
            tot_horas = sum(t["horas"] for t in t_filtro if t["status_turno"].upper() != "EM_ANDAMENTO")
            comb_est = sum(t["combustivel"] for t in t_filtro)
            consumo_km = round(abast_real / tot_km, 2) if (tot_km > 0 and abast_real > 0) else custo_km_global
            kml_periodo = round(tot_km / tot_litros, 2) if (tot_km > 0 and tot_litros > 0) else kml_global
            caixa_liquido = bruto - abast_real
            sub_bruto = "Acumulado Histórico"
            sub_abast = f"{tot_litros:.2f} L • Econ: {formatar_moeda_br(tot_econ)}" if tot_econ > 0 else f"{tot_litros:.2f} L abastecidos"
            sub_km = f"{kml_periodo:.1f} km/L • {round(tot_km, 1)} km" if kml_periodo > 0 else f"{round(tot_km, 1)} km registrados"
            sub_liq = "Bruto (-) Valor Pago Real"

        h_fechadas = round(tot_horas, 2)
        ganho_hora = round(bruto / h_fechadas, 2) if (h_fechadas > 0 and bruto > 0) else 0.0
        sub_horas = f"Ganho Médio: {formatar_moeda_br(ganho_hora)}/h" if ganho_hora > 0 else "Sem horas fechadas"

        return {
            "bruto": bruto,
            "abastecido_real": abast_real,
            "consumo_estimado_km": consumo_km,
            "km_por_litro": kml_periodo,
            "economia_total": tot_econ,
            "litros_total": round(tot_litros, 2),
            "caixa_liquido": caixa_liquido,
            "total_km": round(tot_km, 1),
            "total_horas": round(tot_horas, 1),
            "ganho_hora": ganho_hora,
            "ganho_hora_formatado": formatar_moeda_br(ganho_hora) + "/h" if ganho_hora > 0 else "--",
            "sub_horas": sub_horas,
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

    # Foco de Hoje unificado para o Oikos Drive
    foco_hoje = obter_foco_hoje(conn, hoje_str)

    # Veículo associado ao Drive em Bens & Patrimônio (apenas se ativo)
    try:
        cur.execute("SELECT id, nome, valor_atual_estimado FROM bens WHERE is_veiculo_drive = 1 AND status = 'ativo' LIMIT 1")
        row_vb = cur.fetchone()
        veiculo_drive_bem = {
            "id": row_vb[0],
            "nome": row_vb[1],
            "valor_atual_estimado": float(row_vb[2] or 0.0)
        } if row_vb else None
    except Exception:
        veiculo_drive_bem = None

    conn.close()

    tpl_drive = "oikos_drive.html" if os.path.exists("templates/oikos_drive.html") else "motorista.html"

    return templates.TemplateResponse(
        request=request,
        name=tpl_drive,
        context={
            "filtro_ativo": filtro_ativo,
            "metricas": metricas_ativas,
            "periodos_dados": periodos_dados,
            "periodos_json": json.dumps(periodos_dados),
            "foco_hoje": foco_hoje,
            "veiculo_drive_bem": veiculo_drive_bem,
            "inicio_semana": inicio_semana,
            "fim_semana": fim_semana,
            "inicio_mes": inicio_mes,
            "fim_mes": fim_mes,
            "mes": mes,
            "ano": ano,
            "hoje_formatado": hoje.strftime("%d/%m/%Y"),
            "mes_nome": mes_nome,
            "mes_ant": mes_ant,
            "ano_ant": ano_ant,
            "mes_prox": mes_prox,
            "ano_prox": ano_prox,
            "eh_mes_atual": eh_mes_atual,
            "opcoes_periodo": opcoes_periodo,
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
            "turno_ativo_json": turno_ativo_json,
            "pausa_ativa": pausa_ativa,
            "abastecimentos": abastecimentos,
            "hoje_str": hoje_str,
            "active_tab": "drive"
        }
    )


@app.post("/motorista/turnos/salvar")
@app.post("/motorista/turnos/iniciar")
@app.post("/motorista/turnos/encerrar")
@app.post("/motorista/turnos/registrar")
@app.post("/motorista/turnos/manual")
@app.post("/motorista/turnos/editar")
@app.post("/api/turnos")
async def api_salvar_turno(
    data: Optional[str] = Form(None),
    hora_inicio: Optional[str] = Form(None),
    hora_fim: Optional[str] = Form(None),
    horas: Optional[Any] = Form(0.0),
    km_inicial: Optional[Any] = Form(None),
    km_final: Optional[Any] = Form(None),
    km: Optional[Any] = Form(None),
    ganho_online: Optional[Any] = Form(0.0),
    ganho_dinheiro_pix: Optional[Any] = Form(0.0),
    ganho_bruto: Optional[Any] = Form(None),
    combustivel: Optional[Any] = Form(None),
    observacao: Optional[str] = Form(""),
    periodo: Optional[str] = Form(None),
    status_turno: Optional[str] = Form(None),
    id: Optional[int] = Form(None)
):
    """
    Cria, inicia, edita ou encerra um turno operacional:
    - Se 'hora_fim' estiver vazio/nulo (e horas <= 0), salva o turno com status 'EM_ANDAMENTO' (turno aberto).
    - Se 'hora_fim' for informado no fechamento/edição, calcula as horas trabalhadas e salva como 'encerrado'.
    """
    conn = conectar_db()
    try:
        cur = conn.cursor()
        data_turno = str(data).strip() if (data and str(data).strip() != "") else date.today().strftime("%Y-%m-%d")

        # 1. Tratar Horários & Horas Trabalhadas
        h_ini_str = str(hora_inicio).strip() if (hora_inicio and str(hora_inicio).strip() != "") else None
        h_fim_str = str(hora_fim).strip() if (hora_fim and str(hora_fim).strip() != "") else None

        h_val = converter_valor_monetario(horas, default=0.0)

        if h_ini_str and h_fim_str:
            try:
                hi, mi = map(int, h_ini_str.split(":")[:2])
                hf, mf = map(int, h_fim_str.split(":")[:2])
                diff_m = (hf * 60 + mf) - (hi * 60 + mi)
                if diff_m < 0:
                    diff_m += 24 * 60  # virada de meia-noite
                h_val = round(diff_m / 60.0, 2)
            except Exception:
                pass
        elif not h_fim_str:
            # Se hora_fim não foi informada, trata como turno aberto se horas não tiver sido forçado
            if not status_turno or str(status_turno).upper() == "EM_ANDAMENTO":
                h_val = 0.0

        # Determinar status do turno (EM_ANDAMENTO vs encerrado)
        if status_turno and str(status_turno).strip().upper() == "EM_ANDAMENTO" and not h_fim_str:
            st_turno_db = "EM_ANDAMENTO"
        elif not h_fim_str and h_val <= 0:
            st_turno_db = "EM_ANDAMENTO"
        else:
            st_turno_db = "encerrado"

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
        k_ini_val = converter_valor_monetario(km_inicial, default=-1.0)
        if k_ini_val < 0:
            k_ini_val = None

        k_fim_val = converter_valor_monetario(km_final, default=-1.0)
        if k_fim_val < 0:
            k_fim_val = None

        if k_ini_val is not None and k_fim_val is not None and k_fim_val >= k_ini_val:
            km_val = round(k_fim_val - k_ini_val, 1)
        elif km is not None and str(km).strip() != "" and converter_valor_monetario(km) > 0:
            km_val = round(converter_valor_monetario(km), 1)
        else:
            km_val = 0.0

        # 3. Tratar Ganhos (Faturamento Bruto travado: Online + Dinheiro)
        g_onl = converter_valor_monetario(ganho_online, default=0.0)
        g_din = converter_valor_monetario(ganho_dinheiro_pix, default=0.0)
        g_bruto = round(g_onl + g_din, 2) if (g_onl + g_din > 0) else converter_valor_monetario(ganho_bruto, default=0.0)

        # 4. Combustível estimado (R$ 0,38/km)
        if st_turno_db == "EM_ANDAMENTO":
            c_val = round(km_val * 0.38, 2) if km_val > 0 else 0.0
            st_conciliacao = "em_andamento"
        elif km_val > 0:
            c_val = round(km_val * 0.38, 2)
            st_conciliacao = "conciliado" if (g_bruto > 0 and h_val > 0) else "pendente"
        else:
            c_val = 0.0
            st_conciliacao = "pendente"

        if id and int(id) > 0:
            target_id = int(id)

            # Se o turno estiver sendo encerrado, fecha qualquer pausa em aberto
            if st_turno_db == "encerrado":
                agora_iso = datetime.datetime.now().isoformat()
                cur.execute("SELECT id, inicio_pausa FROM turnos_pausas WHERE turno_id = ? AND fim_pausa IS NULL", (target_id,))
                for pa in cur.fetchall():
                    try:
                        ini_p = datetime.datetime.fromisoformat(pa["inicio_pausa"])
                        dur_p = max(1, int((datetime.datetime.now() - ini_p).total_seconds() // 60))
                    except Exception:
                        dur_p = 0
                    cur.execute("UPDATE turnos_pausas SET fim_pausa = ?, duracao_minutos = ? WHERE id = ?", (agora_iso, dur_p, pa["id"]))

                # Desconta o total de minutos pausados do tempo trabalhado se houver horários
                if h_ini_str and h_fim_str:
                    cur.execute("SELECT SUM(duracao_minutos) FROM turnos_pausas WHERE turno_id = ?", (target_id,))
                    row_sum = cur.fetchone()
                    tot_p_min = row_sum[0] if (row_sum and row_sum[0]) else 0
                    diff_m_liq = max(0, diff_m - tot_p_min)
                    h_val = round(diff_m_liq / 60.0, 2)

            cur.execute("""
                UPDATE turnos
                SET data = ?, periodo = ?, hora_inicio = ?, hora_fim = ?, horas = ?,
                    km_inicial = ?, km_final = ?, km = ?, ganho_bruto = ?,
                    ganho_online = ?, ganho_dinheiro_pix = ?, combustivel = ?,
                    observacao = ?, status_turno = ?, status_conciliacao = ?
                WHERE id = ?
            """, (data_turno, periodo_val, h_ini_str, h_fim_str, h_val,
                  k_ini_val, k_fim_val, km_val, g_bruto, g_onl, g_din, c_val,
                  observacao or "", st_turno_db, st_conciliacao, id))
            conn.commit()
            if st_turno_db == "EM_ANDAMENTO":
                msg = f"Turno #{id} atualizado (Em Andamento)!"
            else:
                msg = f"Turno #{id} encerrado/atualizado com sucesso ({h_val}h)!"
            novo_id = id
        else:
            cur.execute("""
                INSERT INTO turnos (
                    data, periodo, hora_inicio, hora_fim, horas, km_inicial, km_final, km,
                    ganho_bruto, ganho_online, ganho_dinheiro_pix, combustivel, observacao,
                    plataforma, status_turno, status_conciliacao, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '99', ?, ?, ?)
            """, (
                data_turno, periodo_val, h_ini_str, h_fim_str, h_val,
                k_ini_val, k_fim_val, km_val, g_bruto, g_onl, g_din,
                c_val, observacao or "", st_turno_db, st_conciliacao, datetime.datetime.now().isoformat()
            ))
            conn.commit()
            novo_id = cur.lastrowid
            if st_turno_db == "EM_ANDAMENTO":
                msg = f"Turno #{novo_id} iniciado às {h_ini_str or 'agora'} (Em Andamento)!"
            else:
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
                """, (data_turno, desc_onl, g_onl, c_id_99, tr_onl[0]))
            else:
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', '99Pay', ?, 1, 1, ?)
                """, (data_turno, desc_onl, g_onl, c_id_99, novo_id))
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
                """, (data_turno, desc_din, g_din, c_id_din, tr_din[0]))
            else:
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, turno_id)
                    VALUES (?, ?, ?, 'receita', '99 / Chaves (Carlos)', 'Dinheiro / Carteira', ?, 1, 1, ?)
                """, (data_turno, desc_din, g_din, c_id_din, novo_id))
        else:
            if tr_din:
                cur.execute("DELETE FROM transacoes WHERE id = ?", (tr_din[0],))

        conn.commit()

        if st_turno_db != "EM_ANDAMENTO" and km_val <= 0:
            msg += " (⚠️ Pendente KM)"

        return {
            "sucesso": True,
            "mensagem": msg,
            "id": novo_id,
            "dados": {
                "id": novo_id,
                "data": data_turno,
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
                "status_turno": st_turno_db,
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


@app.post("/api/turnos/pausar")
@app.post("/motorista/turnos/pausar")
async def api_pausar_turno(
    turno_id: int = Form(...),
    motivo: str = Form("Almoço"),
    duracao_programada: int = Form(0)
):
    """Registra o início de uma pausa programada ou livre para o turno ativo."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        agora_iso = datetime.datetime.now().isoformat()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS turnos_pausas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turno_id INTEGER NOT NULL,
                inicio_pausa TEXT NOT NULL,
                fim_pausa TEXT,
                duracao_minutos INTEGER DEFAULT 0,
                duracao_programada_minutos INTEGER DEFAULT 0,
                motivo TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (turno_id) REFERENCES turnos(id)
            )
        """)

        # Fecha pausas anteriores que ainda estivessem sem fim_pausa
        cur.execute("SELECT id, inicio_pausa FROM turnos_pausas WHERE turno_id = ? AND fim_pausa IS NULL", (turno_id,))
        for pa in cur.fetchall():
            try:
                ini_dt = datetime.datetime.fromisoformat(pa["inicio_pausa"])
                dur_m = max(1, int((datetime.datetime.now() - ini_dt).total_seconds() // 60))
            except Exception:
                dur_m = 0
            cur.execute("UPDATE turnos_pausas SET fim_pausa = ?, duracao_minutos = ? WHERE id = ?", (agora_iso, dur_m, pa["id"]))

        cur.execute("""
            INSERT INTO turnos_pausas (turno_id, inicio_pausa, duracao_programada_minutos, motivo, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (turno_id, agora_iso, duracao_programada, motivo, agora_iso))
        pausa_id = cur.lastrowid

        cur.execute("UPDATE turnos SET status_turno = 'PAUSADO' WHERE id = ?", (turno_id,))
        conn.commit()

        return {
            "success": True,
            "pausa_id": pausa_id,
            "turno_id": turno_id,
            "inicio_pausa": agora_iso,
            "motivo": motivo,
            "duracao_programada": duracao_programada,
            "mensagem": f"Pausa '{motivo}' iniciada com sucesso!"
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"success": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/turnos/retomar")
@app.post("/motorista/turnos/retomar")
async def api_retomar_turno(turno_id: int = Form(...)):
    """Encerra a pausa ativa e retorna o status do turno para EM_ANDAMENTO."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        agora = datetime.datetime.now()
        agora_iso = agora.isoformat()

        cur.execute("""
            SELECT id, inicio_pausa FROM turnos_pausas
            WHERE turno_id = ? AND fim_pausa IS NULL
            ORDER BY id DESC LIMIT 1
        """, (turno_id,))
        p = cur.fetchone()
        duracao_efetiva = 0
        if p:
            try:
                ini = datetime.datetime.fromisoformat(p["inicio_pausa"])
                duracao_efetiva = max(1, int((agora - ini).total_seconds() // 60))
            except Exception:
                duracao_efetiva = 0
            cur.execute("UPDATE turnos_pausas SET fim_pausa = ?, duracao_minutos = ? WHERE id = ?", (agora_iso, duracao_efetiva, p["id"]))

        cur.execute("UPDATE turnos SET status_turno = 'EM_ANDAMENTO' WHERE id = ?", (turno_id,))
        conn.commit()

        return {
            "success": True,
            "turno_id": turno_id,
            "duracao_minutos": duracao_efetiva,
            "mensagem": f"Turno retomado! (Pausa durou {duracao_efetiva} min)"
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"success": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/turnos/pausa/adicionar-tempo")
@app.post("/motorista/turnos/pausa/adicionar-tempo")
async def api_adicionar_tempo_pausa(
    turno_id: int = Form(...),
    minutos: int = Form(5)
):
    """Adiciona minutos à contagem regressiva da pausa ativa programada."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, duracao_programada_minutos FROM turnos_pausas
            WHERE turno_id = ? AND fim_pausa IS NULL
            ORDER BY id DESC LIMIT 1
        """, (turno_id,))
        p = cur.fetchone()
        if p:
            nova_duracao = int(p["duracao_programada_minutos"] or 0) + minutos
            cur.execute("UPDATE turnos_pausas SET duracao_programada_minutos = ? WHERE id = ?", (nova_duracao, p["id"]))
            conn.commit()
            return {"success": True, "duracao_programada": nova_duracao, "mensagem": f"+{minutos} min adicionados à pausa!"}
        return {"success": False, "erro": "Nenhuma pausa ativa encontrada."}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"success": False, "erro": str(e)})
    finally:
        conn.close()



@app.post("/motorista/abastecer")
@app.post("/api/abastecer")
async def api_motorista_abastecer(
    data: str = Form(...),
    valor_pago: Any = Form(...),
    litros: Any = Form(...),
    valor_bomba: Optional[Any] = Form(None),
    valor_bruto: Optional[Any] = Form(None),
    app_desconto: Optional[str] = Form(None),
    origem_desconto: Optional[str] = Form(None),
    preco_litro: Optional[Any] = Form(None),
    combustivel: Optional[str] = Form("Etanol"),
    posto: Optional[str] = Form("Posto de Combustível"),
    hodometro: Optional[Any] = Form(None),
    conta: Optional[str] = Form(None),
    conta_pagamento: Optional[str] = Form(None),
    desconto: Optional[Any] = Form(0.0),
    tanque_cheio: Optional[int] = Form(0),
    observacao: Optional[str] = Form("")
):
    """
    Registra abastecimento real do veículo e gera transação de saída:
    - Economia = Valor da Bomba - Valor Pago Real
    - Preço Real por Litro = Valor Pago Real / Litros
    - Débito financeiro na conta selecionada = estritamente o Valor Pago Real
    """
    val_pago = converter_valor_monetario(valor_pago)
    lits = converter_valor_monetario(litros)

    if val_pago <= 0 or lits <= 0:
        raise HTTPException(status_code=400, detail="Valor pago real e litros abastecidos devem ser maiores que zero.")

    # Tratar Valor Total da Bomba e Economia (Valor da Bomba - Valor Pago Real)
    raw_bomba = valor_bomba if (valor_bomba is not None and not hasattr(valor_bomba, 'default')) else valor_bruto
    try:
        val_bomba = round(float(raw_bomba), 2) if (raw_bomba is not None and not hasattr(raw_bomba, 'default') and str(raw_bomba).strip() != "") else 0.0
    except (TypeError, ValueError):
        val_bomba = 0.0

    try:
        desc_in = round(float(desconto), 2) if (desconto is not None and not hasattr(desconto, 'default')) else 0.0
    except (TypeError, ValueError):
        desc_in = 0.0

    raw_app = app_desconto if (app_desconto and not hasattr(app_desconto, 'default')) else origem_desconto
    app_nome = str(raw_app).strip() if (raw_app and not hasattr(raw_app, 'default') and str(raw_app).strip() != "") else "Nenhum"

    if desc_in > 0 and ("soutag" in app_nome.lower() or "soutag" in str(origem_desconto or '').lower()):
        desc_val = desc_in
        val_bomba = round(val_pago + desc_val, 2)
    elif val_bomba >= val_pago and val_bomba > 0:
        desc_val = round(max(0.0, val_bomba - val_pago), 2)
    else:
        desc_val = round(max(0.0, desc_in), 2)
        val_bomba = round(val_pago + desc_val, 2)

    pct_economia = round((desc_val / val_bomba) * 100.0, 1) if (val_bomba > 0 and desc_val > 0) else 0.0

    # Preço Real por Litro = Valor Pago Real / Litros
    calc_preco = round(val_pago / lits, 3)

    if desc_val > 0 and app_nome == "Nenhum":
        app_nome = "Posto / Outro"

    raw_conta = conta if (conta and not hasattr(conta, 'default')) else conta_pagamento
    conta_nome = str(raw_conta).strip() if (raw_conta and not hasattr(raw_conta, 'default') and str(raw_conta).strip() != "") else "Mercado Pago"
    if "Mercado" in conta_nome:
        conta_id = 1
        conta_nome = "Mercado Pago"
    elif "99" in conta_nome:
        conta_id = 1779
        conta_nome = "99Pay"
    else:
        conta_id = 2
        conta_nome = "Dinheiro / Carteira"

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

    badge_economia = f"Economia de {formatar_moeda_br(desc_val)} ({pct_economia:.1f}%) via {app_nome}" if desc_val > 0 else ""
    if badge_economia and badge_economia not in obs_txt:
        obs_txt = f"{badge_economia}" + (f" • {obs_txt}" if obs_txt else "")

    data_raw_str = str(data).strip()
    data_iso = data_raw_str[:10]

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(veiculo_abastecimentos)")
        cols_ab = [c["name"] for c in cur.fetchall()]
        if "app_desconto" not in cols_ab:
            cur.execute("ALTER TABLE veiculo_abastecimentos ADD COLUMN app_desconto TEXT DEFAULT 'Nenhum'")
            conn.commit()

        # 1. Registrar transação financeira de despesa estritamente pelo Valor Pago Real
        desc_trans = f"Abastecimento {comb_nome} ({lits:.2f}L) - {posto_nome}"
        motivo_desc = f"Economia via {app_nome}" if desc_val > 0 else ""
        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, desconto, motivo_ajuste)
            VALUES (?, ?, ?, 'despesa', 'Combustível (Trabalho)', ?, ?, 1, 1, ?, ?)
        """, (data_iso, desc_trans, val_pago, conta_nome, conta_id, desc_val, motivo_desc))
        trans_id = cur.lastrowid

        # 2. Registrar na tabela veiculo_abastecimentos (Drivvo)
        cur.execute("""
            INSERT INTO veiculo_abastecimentos (
                data, hodometro, combustivel, litros, preco_litro, valor_bruto,
                desconto, valor_pago, conta, conta_id, tanque_cheio, posto,
                observacao, transacao_id, app_desconto, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (data_raw_str, hodo_val, comb_nome, lits, calc_preco, val_bomba,
              desc_val, val_pago, conta_nome, conta_id, tq_cheio,
              posto_nome, obs_txt, trans_id, app_nome))

        conn.commit()
        msg_extra = f" • {badge_economia}" if badge_economia else ""
        return {
            "sucesso": True,
            "mensagem": f"Abastecimento de {formatar_moeda_br(val_pago)} ({lits:.2f}L a R$ {calc_preco:.3f}/L){msg_extra} registrado com sucesso!",
            "economia": desc_val,
            "pct_economia": pct_economia,
            "preco_real_litro": calc_preco,
            "app_desconto": app_nome,
            "economia_badge": badge_economia
        }
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
@app.post("/missoes/definir")
@app.post("/api/missoes/remover")
@app.post("/missoes/remover")
async def api_definir_missao(request: Request, transacao_id: Optional[int] = Form(None)):
    """Define ou remove/troca a obrigação selecionada como Missão Ativa da Semana."""
    conn = conectar_db()
    try:
        tid = transacao_id
        if tid is None:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    payload = await request.json()
                    tid = int(payload.get("transacao_id") or 0)
                except Exception:
                    tid = 0
            else:
                try:
                    form = await request.form()
                    tid = int(form.get("transacao_id") or 0)
                except Exception:
                    tid = 0
        if request.url.path.endswith("/remover"):
            tid = 0

        hoje = date.today()
        mes_ano = f"{hoje.year}-{hoje.month:02d}"
        ok, msg = planejamento_service.definir_missao_ativa_semana(conn, transacao_id=tid, mes_ano=mes_ano)
        if ok:
            return {"sucesso": True, "mensagem": msg, "transacao_id": tid}
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
@app.post("/api/contas_pagar/pagar")
@app.post("/api/contas_pagar/pagar/{transacao_id}")
@app.post("/api/obrigacoes/baixar")
@app.post("/api/obrigacoes/baixar/{transacao_id}")
async def api_baixar_conta(request: Request, transacao_id: Optional[int] = None):
    """
    Executa a baixa imediata e oficial de uma conta a pagar no banco SQLite:
    - Identifica a conta financeira de débito (ex: Mercado Pago, 99Pay, Dinheiro / Carteira)
    - Deduz o valor pago diretamente do saldo dessa conta financeira
    - Registra a saída (Despesa) liquidada no extrato/lançamentos com a data do pagamento,
      categoria correspondente e referência à conta paga
    - Atualiza o status da obrigação para 'PAGA' e registra a data de liquidação
    """
    conn = conectar_db()
    try:
        payload = {}
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                payload = await request.json()
            elif "form" in content_type:
                form_data = await request.form()
                payload = dict(form_data)
        except Exception:
            payload = {}

        if transacao_id is None:
            raw_id = payload.get("transacao_id") or payload.get("id") or payload.get("obrigacao_id")
            if raw_id is not None:
                transacao_id = int(raw_id)

        if not transacao_id:
            raise HTTPException(status_code=400, detail="ID da obrigação não informado.")

        resumo = saldo_service.obter_resumo_obrigacao(conn, transacao_id)
        if not resumo:
            raise HTTPException(status_code=404, detail="Obrigação não encontrada.")

        val_devedor = float(resumo["saldo_devedor"])
        if val_devedor <= 0:
            val_devedor = float(resumo.get("valor_original") or 0.0)

        hoje_str = str(payload.get("data_pagamento") or date.today().strftime("%Y-%m-%d"))[:10]

        # Identificar conta financeira de débito válida em contas_config
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nome, tipo
            FROM contas_config
            WHERE COALESCE(tipo, '') != 'cofrinho'
            ORDER BY id ASC
        """)
        contas_disp = cur.fetchall()
        mapa_id = {int(c["id"]): c["nome"] for c in contas_disp}
        mapa_nome = {str(c["nome"]).strip().lower(): int(c["id"]) for c in contas_disp}

        conta_id_req = payload.get("conta_id")
        conta_nome_req = (payload.get("conta") or payload.get("conta_debito") or "").strip()

        conta_id = None
        if conta_id_req:
            try:
                cid = int(conta_id_req)
                if cid in mapa_id:
                    conta_id = cid
            except Exception:
                pass

        if not conta_id and conta_nome_req:
            conta_id = mapa_nome.get(conta_nome_req.lower())

        # Caso não tenha vindo no payload, usa a conta vinculada à obrigação
        if not conta_id:
            cid_obrig = resumo.get("conta_id")
            if cid_obrig and int(cid_obrig) in mapa_id:
                conta_id = int(cid_obrig)
            else:
                nome_obrig = str(resumo.get("conta") or "").strip().lower()
                if nome_obrig in mapa_nome:
                    conta_id = mapa_nome[nome_obrig]

        # Se a obrigação não tiver uma conta vinculada válida, usa a conta principal padrão (Mercado Pago)
        if not conta_id:
            conta_id = 1 if 1 in mapa_id else ( next(iter(mapa_id.keys())) if mapa_id else 1 )

        conta_nome = mapa_id.get(conta_id, "Mercado Pago")

        saldo_service.registrar_pagamento(
            conn=conn,
            transacao_id=transacao_id,
            data_pagamento=hoje_str,
            valor_pago=val_devedor,
            conta_id=conta_id,
            afeta_saldo_bancario=1,
            considerado_no_marco=0,
            forma_pagamento=str(payload.get("forma_pagamento") or "Pix"),
            observacao=f"Baixa de conta a pagar: {resumo['descricao']} ({resumo.get('categoria') or 'Geral'})",
            tipo_ajuste_valor="normal",
            valor_encargos=0.0,
            valor_desconto=0.0
        )
        conn.commit()

        # Recalcular saldos e métricas consolidadas após a baixa
        dados = coletar_dados_dashboard()
        contas_atualizadas = [
            {
                "id": c["id"],
                "nome": c["nome"],
                "saldo_atual": c["saldo_atual"],
                "saldo_formatado": formatar_moeda_br(c["saldo_atual"])
            }
            for c in dados["contas"]
        ]
        conta_debitada_info = next((c for c in contas_atualizadas if int(c["id"]) == int(conta_id)), None)
        novo_saldo_conta_fmt = conta_debitada_info["saldo_formatado"] if conta_debitada_info else formatar_moeda_br(0.0)

        return {
            "sucesso": True,
            "mensagem": f"Baixa de '{resumo['descricao']}' ({formatar_moeda_br(val_devedor)}) debitada de {conta_nome}!",
            "transacao_id": transacao_id,
            "status": "PAGA",
            "data_liquidacao": hoje_str,
            "valor_baixado": val_devedor,
            "conta_id": conta_id,
            "conta_nome": conta_nome,
            "novo_saldo_conta": novo_saldo_conta_fmt,
            "novo_saldo_caixa": formatar_moeda_br(dados["saldo_caixa"]),
            "contas": contas_atualizadas,
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
                "qtd_prox7": dados["qtd_prox7"],
                "contas": contas_atualizadas
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
async def api_salvar_meta_horas(request: Request, horas: Optional[float] = Form(None)):
    """
    Atualiza as horas de meta de hoje e retorna todos os indicadores dependentes recalculados
    (meta em reais a R$ 35/h, faturamento, restante, cobertura e horas restantes).
    Suporta Content-Type application/json e multipart/form-data.
    """
    valor_horas = horas
    if valor_horas is None:
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                payload = await request.json()
                valor_horas = float(payload.get("horas", 0.0))
            else:
                form = await request.form()
                valor_horas = float(form.get("horas", 0.0))
        except Exception:
            raise HTTPException(status_code=400, detail="Formato de requisição inválido.")

    if valor_horas is None or valor_horas < 0.5 or valor_horas > 16.0:
        raise HTTPException(status_code=400, detail="Horas inválidas (permitido entre 0.5h e 16h).")

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO config_dashboard (chave, valor) VALUES (?, ?)", ("horas_hoje_planejadas", str(valor_horas)))
        conn.commit()

        foco = obter_foco_hoje(conn)
        return {
            "sucesso": True,
            "horas": valor_horas,
            "nova_meta": formatar_moeda_br(foco["meta_bruta_hoje"]),
            "meta_bruta_hoje": foco["meta_bruta_hoje"],
            "meta_bruta_formatada": formatar_moeda_br(foco["meta_bruta_hoje"]),
            "bruto_hoje": foco["bruto_hoje"],
            "bruto_formatado": formatar_moeda_br(foco["bruto_hoje"]),
            "restante_meta_hoje": foco["restante_meta_hoje"],
            "restante_formatado": formatar_moeda_br(foco["restante_meta_hoje"]),
            "pct_meta_hoje": foco["pct_meta_hoje"],
            "horas_restantes": foco["horas_restantes"],
            "qtd_turnos": foco["qtd_turnos_hoje"],
            "horas_real": foco["horas_hoje_real"]
        }
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


# ============================================================================
# ROTAS DO MÓDULO DE PATRIMÔNIO & BENS
# ============================================================================
import patrimonio_service



# =============================================================================
# ROTAS DA API: PLANEJAMENTO DE RENDA VARIÁVEL E DESPESAS ANUAIS / EVENTUAIS
# =============================================================================

@app.post("/api/planejamento/meses-amostra")
async def api_salvar_meses_amostra(request: Request):
    dados = await request.json()
    meses_ativos = dados.get("meses_ativos", [])
    meses_confirmados = dados.get("meses_confirmados", [])
    qualidade_map = dados.get("qualidade_map", {})
    conn = conectar_db()
    try:
        import planejamento_anual_service
        ok = planejamento_anual_service.salvar_selecao_meses_amostra(
            conn, meses_ativos, meses_confirmados, qualidade_map
        )
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


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


@app.get("/patrimonio", response_class=HTMLResponse)
async def pagina_patrimonio(request: Request):
    conn = conectar_db()
    try:
        resumo = patrimonio_service.obter_resumo_patrimonial(conn)
        return templates.TemplateResponse(
            request=request,
            name="patrimonio.html",
            context={
                "active_tab": "patrimonio",
                "resumo": resumo,
            },
        )
    finally:
        conn.close()


@app.get("/bens", response_class=HTMLResponse)
async def pagina_bens(request: Request, arquivados: Optional[int] = 0):
    conn = conectar_db()
    try:
        incluir_arq = bool(arquivados == 1)
        resumo = patrimonio_service.obter_resumo_patrimonial(conn)
        bens = patrimonio_service.listar_bens(conn, incluir_arquivados=incluir_arq)
        return templates.TemplateResponse(
            request=request,
            name="bens.html",
            context={
                "active_tab": "bens",
                "bens": bens,
                "incluir_arquivados": incluir_arq,
                "total_bens": resumo["total_bens"],
                "por_tipo": resumo["por_tipo"],
                "por_proprietario": resumo["por_proprietario"],
                "metricas_veiculo_drive": resumo["metricas_veiculo_drive"],
            },
        )
    finally:
        conn.close()


@app.get("/api/patrimonio/bens/{bem_id}")
async def api_obter_bem(bem_id: int):
    conn = conectar_db()
    try:
        bem = patrimonio_service.obter_bem(conn, bem_id)
        if not bem:
            return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Bem não encontrado"})
        return JSONResponse(bem)
    finally:
        conn.close()


@app.post("/api/patrimonio/bens")
async def api_criar_bem(request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        bem_id = patrimonio_service.criar_bem(conn, dados)
        return JSONResponse({"sucesso": True, "id": bem_id})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/patrimonio/bens/{bem_id}/editar")
async def api_editar_bem(bem_id: int, request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        ok = patrimonio_service.atualizar_bem(conn, bem_id, dados)
        if not ok:
            return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Bem não encontrado"})
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/patrimonio/bens/{bem_id}/status")
async def api_status_bem(bem_id: int, request: Request):
    dados = await request.json()
    novo_status = dados.get("status", "ativo")
    conn = conectar_db()
    try:
        ok = patrimonio_service.alterar_status_bem(conn, bem_id, novo_status)
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/patrimonio/bens/{bem_id}/avaliacoes")
async def api_nova_avaliacao_bem(bem_id: int, request: Request):
    dados = await request.json()
    valor = float(dados.get("valor_estimado", 0))
    data_av = dados.get("data_avaliacao")
    obs = dados.get("observacoes")
    conn = conectar_db()
    try:
        ok = patrimonio_service.registrar_nova_avaliacao(conn, bem_id, valor, data_av, obs)
        return JSONResponse({"sucesso": ok})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()



# =====================================================================
# ROTAS DE OBJETIVOS E FINALIDADES DOS COFRINHOS (ETAPA 2)
# =====================================================================
import objetivos_service


@app.get("/objetivos", response_class=HTMLResponse)
async def pagina_objetivos(request: Request, status: Optional[str] = None):
    conn = conectar_db()
    try:
        filtro = status if status and status != "todos" else None
        objetivos = objetivos_service.listar_objetivos(conn, status_filtro=filtro)
        cofrinhos = objetivos_service.listar_cofrinhos(conn)
        dividas = objetivos_service.listar_dividas_disponiveis(conn)
        
        obj_ativos = [o for o in objetivos if o["status"] == "ativo"]
        total_destinado = sum(o["saldo_destinado"] for o in obj_ativos)
        total_alvo = sum(o["valor_alvo"] for o in obj_ativos if o["valor_alvo"])
        total_alcancados = len([o for o in objetivos if o["atingiu_alvo"] or o["status"] == "alcancado"])
        
        return templates.TemplateResponse(
            request=request,
            name="objetivos.html",
            context={
                "active_tab": "objetivos",
                "objetivos": objetivos,
                "cofrinhos": cofrinhos,
                "dividas": dividas,
                "status_filtro": status or "todos",
                "total_objetivos_ativos": len(obj_ativos),
                "total_destinado": total_destinado,
                "total_alvo": total_alvo,
                "total_alcancados": total_alcancados,
                "tipos_objetivo": objetivos_service.TIPOS_OBJETIVO,
                "finalidades_cofrinho": objetivos_service.FINALIDADES_COFRINHO,
            },
        )
    finally:
        conn.close()


@app.get("/api/objetivos/{objetivo_id}")
async def api_obter_objetivo(objetivo_id: int):
    conn = conectar_db()
    try:
        obj = objetivos_service.obter_objetivo(conn, objetivo_id)
        if not obj:
            return JSONResponse(status_code=404, content={"erro": "Objetivo não encontrado"})
        return JSONResponse(obj)
    finally:
        conn.close()


@app.post("/api/objetivos")
async def api_criar_objetivo(request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        novo_id = objetivos_service.criar_objetivo(conn, dados)
        return JSONResponse({"sucesso": True, "id": novo_id})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/objetivos/{objetivo_id}/editar")
async def api_editar_objetivo(objetivo_id: int, request: Request):
    dados = await request.json()
    conn = conectar_db()
    try:
        objetivos_service.atualizar_objetivo(conn, objetivo_id, dados)
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/objetivos/{objetivo_id}/status")
async def api_alterar_status_objetivo(objetivo_id: int, request: Request):
    dados = await request.json()
    novo_status = dados.get("status", "ativo")
    conn = conectar_db()
    try:
        objetivos_service.alterar_status_objetivo(conn, objetivo_id, novo_status)
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/objetivos/{objetivo_id}/excluir")
async def api_excluir_objetivo(objetivo_id: int):
    conn = conectar_db()
    try:
        objetivos_service.excluir_objetivo(conn, objetivo_id)
        return JSONResponse({"sucesso": True})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/cofrinhos/{cofrinho_id}/finalidade")
async def api_atualizar_finalidade_cofrinho(cofrinho_id: int, request: Request):
    dados = await request.json()
    finalidade = dados.get("finalidade", "outro")
    conn = conectar_db()
    try:
        objetivos_service.atualizar_finalidade_cofrinho(conn, cofrinho_id, finalidade)
        return JSONResponse({"sucesso": True, "finalidade": finalidade})
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()



@app.post("/api/pagamento/desfazer/{transacao_id}")
@app.post("/api/contas_pagar/desfazer/{transacao_id}")
@app.post("/api/estorno/{transacao_id}")
async def api_desfazer_pagamento(transacao_id: int, request: Request):
    """
    Reverte o pagamento de uma conta de forma auditável e segura:
    - Retorna a transação para o status 'pendente' (pago = 0)
    - Limpa data_liquidacao
    - Cancela o registro de pagamento em pagamentos_despesas (cancelado = 1)
    - Recompõe o saldo bancário da conta debitada
    - Recalcula e retorna os novos totais e saldos para atualização reativa da UI
    """
    conn = conectar_db()
    try:
        motivo = "Desfazer pagamento solicitado pelo usuário"
        try:
            payload = await request.json()
            if payload.get("motivo"):
                motivo = str(payload["motivo"]).strip()
        except Exception:
            pass

        res = saldo_service.desfazer_pagamento_transacao(conn, transacao_id, motivo=motivo)
        
        # Recalcular saldos e métricas consolidadas após a reversão
        dados = coletar_dados_dashboard()
        contas_atualizadas = [
            {
                "id": c["id"],
                "nome": c["nome"],
                "saldo_atual": c["saldo_atual"],
                "saldo_formatado": formatar_moeda_br(c["saldo_atual"])
            }
            for c in dados["contas"]
        ]

        return {
            "sucesso": True,
            "mensagem": f"Pagamento de '{res['descricao']}' revertido com sucesso! O valor de {formatar_moeda_br(res['valor_estornado'])} foi recomposto.",
            "transacao_id": transacao_id,
            "status": "pendente",
            "valor_estornado": res["valor_estornado"],
            "conta_id": res["conta_id"],
            "novo_saldo_caixa": formatar_moeda_br(dados["saldo_caixa"]),
            "contas": contas_atualizadas,
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
                "qtd_prox7": dados["qtd_prox7"],
                "contas": contas_atualizadas
            }
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"sucesso": False, "erro": str(e)})
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Servidor Web PWA em http://localhost:8000 ...")
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)


# =============================================================================
# ROTAS DO BOTÃO GLOBAL "+": TRANSFERÊNCIAS E RECORRÊNCIAS
# =============================================================================

@app.post("/api/transferencias")
async def api_criar_transferencia(
    conta_origem_id: int = Form(...),
    conta_destino_id: int = Form(...),
    valor: Any = Form(...),
    data: str = Form(...),
    descricao: Optional[str] = Form("")
):
    """
    Executa transferência financeira interna entre contas de saldo:
    - Debita a conta de origem e credita a conta de destino.
    - Afeta o saldo bancário de cada conta, mas anula-se no saldo consolidado livre.
    - Não gera duplicidade de receita ou despesa externa.
    """
    valor_num = converter_valor_monetario(valor)
    if valor_num <= 0:
        return JSONResponse(status_code=400, content={"status": "erro", "sucesso": False, "erro": "Valor deve ser maior que zero."})
    if int(conta_origem_id) == int(conta_destino_id):
        return JSONResponse(status_code=400, content={"status": "erro", "sucesso": False, "erro": "Conta de origem e conta de destino não podem ser a mesma."})

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome FROM contas_config WHERE id = ?", (conta_origem_id,))
        r_orig = cur.fetchone()
        cur.execute("SELECT id, nome FROM contas_config WHERE id = ?", (conta_destino_id,))
        r_dest = cur.fetchone()
        if not r_orig or not r_dest:
            return JSONResponse(status_code=404, content={"status": "erro", "sucesso": False, "erro": "Conta de origem ou destino não encontrada."})

        desc = (descricao or f"Transferência de {r_orig['nome']} para {r_dest['nome']}").strip()
        data_efetiva = str(data)[:10]

        cur.execute("""
            INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario, data_liquidacao)
            VALUES (?, ?, ?, 'transferencia', 'Transferência Interna', ?, ?, ?, 1, 1, ?)
        """, (data_efetiva, desc, valor_num, r_orig["nome"], conta_origem_id, conta_destino_id, data_efetiva))
        conn.commit()

        res_saldo = saldo_service.calcular_saldo_consolidado(conn)
        return {
            "status": "sucesso",
            "sucesso": True,
            "mensagem": f"Transferência de {formatar_moeda_br(valor_num)} de {r_orig['nome']} para {r_dest['nome']} realizada com sucesso!",
            "saldo_consolidado": float(res_saldo.get("saldo_consolidado", 0.0))
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"status": "erro", "sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.post("/api/recorrencias")
async def api_criar_recorrencia(
    descricao: str = Form(...),
    categoria: str = Form(...),
    valor: Any = Form(...),
    dia_vencimento: int = Form(...),
    conta: str = Form("Mercado Pago"),
    meses_duracao: int = Form(12),
    data_inicio: Optional[str] = Form(None)
):
    """
    Cadastra uma despesa recorrente mensal com vencimentos programados para os próximos meses:
    - Gera as ocorrências pendentes na tabela transações.
    - Permite controle determinístico sem estimativas fictícias.
    """
    valor_num = converter_valor_monetario(valor)
    if valor_num <= 0:
        return JSONResponse(status_code=400, content={"status": "erro", "sucesso": False, "erro": "Valor deve ser maior que zero."})

    dia = max(1, min(31, int(dia_vencimento)))
    meses = max(1, min(36, int(meses_duracao)))

    hoje = date.today()
    if data_inicio and len(str(data_inicio).strip()) >= 7:
        try:
            p = str(data_inicio).strip().split("-")
            ano_ini = int(p[0])
            mes_ini = int(p[1])
        except Exception:
            ano_ini, mes_ini = hoje.year, hoje.month
    else:
        ano_ini, mes_ini = hoje.year, hoje.month

    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome FROM contas_config WHERE nome = ? OR id = ?", (conta, conta))
        r_c = cur.fetchone()
        cid = r_c["id"] if r_c else 1
        cnome = r_c["nome"] if r_c else "Mercado Pago"

        inseridas = 0
        ano_corrente, mes_corrente = ano_ini, mes_ini

        for _ in range(meses):
            ultimo_d = calendar.monthrange(ano_corrente, mes_corrente)[1]
            d_efetivo = min(dia, ultimo_d)
            dt_str = f"{ano_corrente}-{mes_corrente:02d}-{d_efetivo:02d}"

            # Verifica se já existe transação idêntica no mês para evitar duplicação
            cur.execute("""
                SELECT COUNT(*) FROM transacoes
                WHERE LOWER(TRIM(descricao)) = LOWER(TRIM(?))
                  AND tipo = 'despesa'
                  AND data LIKE ?
            """, (descricao.strip(), f"{ano_corrente}-{mes_corrente:02d}-%"))
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO transacoes (data, descricao, valor, tipo, categoria, conta, conta_id, pago, status_pagamento)
                    VALUES (?, ?, ?, 'despesa', ?, ?, ?, 0, 'pendente')
                """, (dt_str, descricao.strip(), valor_num, categoria.strip(), cnome, cid))
                inseridas += 1

            # Avança mês
            if mes_corrente == 12:
                mes_corrente = 1
                ano_corrente += 1
            else:
                mes_corrente += 1

        conn.commit()
        return {
            "status": "sucesso",
            "sucesso": True,
            "mensagem": f"Regra recorrente '{descricao.strip()}' cadastrada com sucesso! {inseridas} parcelas mensais programadas.",
            "qtd_inseridas": inseridas
        }
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"status": "erro", "sucesso": False, "erro": str(e)})
    finally:
        conn.close()


@app.get("/api/recorrencias/listar")
async def api_listar_recorrencias():
    """Retorna lista de despesas recorrentes ativas baseada em descrições repetidas em meses futuros."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        hoje_str = date.today().strftime("%Y-%m-%d")
        cur.execute("""
            SELECT descricao, categoria, valor, conta, COUNT(*) as qtd_futuras, MIN(data) as proximo_vencimento
            FROM transacoes
            WHERE tipo = 'despesa' AND (pago = 0 OR pago IS NULL) AND data >= ?
            GROUP BY LOWER(TRIM(descricao)), valor
            HAVING COUNT(*) >= 1
            ORDER BY proximo_vencimento ASC
        """, (hoje_str,))
        rows = cur.fetchall()
        recorrencias = [
            {
                "descricao": r["descricao"],
                "categoria": r["categoria"],
                "valor": float(r["valor"] or 0.0),
                "conta": r["conta"],
                "qtd_futuras": r["qtd_futuras"],
                "proximo_vencimento": r["proximo_vencimento"]
            }
            for r in rows
        ]
        return {"sucesso": True, "recorrencias": recorrencias}
    finally:
        conn.close()


@app.get("/api/opcoes-transacao-global")
async def api_opcoes_transacao_global():
    """Retorna as opções reais e ativas para alimentar o modal global de transações."""
    conn = conectar_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, tipo, cor, COALESCE(icone, '🏦') as icone FROM contas_config WHERE id NOT IN (SELECT id FROM contas_config WHERE tipo = 'investimento') ORDER BY nome ASC")
        contas = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT categoria FROM transacoes WHERE tipo = 'despesa' AND categoria IS NOT NULL ORDER BY categoria ASC")
        cats_desp = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute("SELECT DISTINCT categoria FROM transacoes WHERE tipo = 'receita' AND categoria IS NOT NULL ORDER BY categoria ASC")
        cats_rec = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute("SELECT id, nome, bandeira, limite_total FROM cartoes ORDER BY nome ASC")
        cartoes = [dict(r) for r in cur.fetchall()]

        return {
            "sucesso": True,
            "hoje": date.today().strftime("%Y-%m-%d"),
            "contas": contas,
            "categorias_despesa": cats_desp,
            "categorias_receita": cats_rec,
            "cartoes": cartoes
        }
    finally:
        conn.close()
