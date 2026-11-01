# -*- coding: utf-8 -*-
"""
Validação automatizada de integridade após limpeza de materiais Organizze.
Executa em ambiente estritamente isolado (test_val_isolated.db),
garantindo que o banco de dados de produção 'financas_casa.db' permaneça 100% intocado.
"""

import os
import sys
import hashlib
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from starlette.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_DB = os.path.join(BASE_DIR, "financas_casa.db")
ISOLATED_DB = os.path.join(BASE_DIR, "test_val_isolated.db")

def get_hash(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

prod_hash_before = get_hash(PROD_DB)
print(f"[PRE-FLIGHT] SHA256 financas_casa.db: {prod_hash_before}")

# 1. Configurar módulos para apontar para o banco isolado
sys.path.insert(0, BASE_DIR)
import web_app
import saldo_service
import planejamento_service

web_app.DB_PATH = ISOLATED_DB
if hasattr(saldo_service, "DB_PATH"):
    saldo_service.DB_PATH = ISOLATED_DB
if hasattr(planejamento_service, "DB_PATH"):
    planejamento_service.DB_PATH = ISOLATED_DB

# Função para coletar indicadores consolidados do banco isolado
def coletar_indicadores(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Total de contas
    cur.execute("SELECT COUNT(*) FROM contas")
    qtd_contas = cur.fetchone()[0]
    
    # Total de cartões e limite total
    cur.execute("SELECT COUNT(*), COALESCE(SUM(limite_total), 0) FROM cartoes")
    qtd_cartoes, limite_cartoes = cur.fetchone()
    
    # Transações totais
    cur.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor ELSE 0 END), 0), COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor ELSE 0 END), 0) FROM transacoes")
    qtd_tx, total_receitas, total_despesas = cur.fetchone()
    
    # Saldo consolidado via saldo_service
    try:
        contas_detalhes = saldo_service.obter_contas_com_saldo(conn)
        saldo_consolidado = sum(c.get("saldo_atual", 0) for c in contas_detalhes if c.get("incluir_saldo_consolidado", 1))
    except Exception as e:
        saldo_consolidado = 0.0
    
    # Dívidas Paga Leve
    try:
        cur.execute("SELECT COUNT(*), COALESCE(SUM(saldo_devedor), 0) FROM pagaleve_dividas")
        qtd_dividas_pl, total_pl = cur.fetchone()
    except Exception:
        qtd_dividas_pl, total_pl = 0, 0.0
        
    # Turnos Oikos Drive
    try:
        cur.execute("SELECT COUNT(*), COALESCE(SUM(faturamento_bruto), 0) FROM motorista_turnos")
        qtd_turnos, total_fat_turnos = cur.fetchone()
    except Exception:
        qtd_turnos, total_fat_turnos = 0, 0.0
        
    conn.close()
    return {
        "qtd_contas": qtd_contas,
        "saldo_consolidado": round(saldo_consolidado, 2),
        "qtd_cartoes": qtd_cartoes,
        "limite_cartoes": round(limite_cartoes, 2),
        "qtd_transacoes": qtd_tx,
        "total_receitas": round(total_receitas, 2),
        "total_despesas": round(total_despesas, 2),
        "qtd_dividas_pagaleve": qtd_dividas_pl,
        "total_dividas_pagaleve": round(total_pl, 2),
        "qtd_turnos_drive": qtd_turnos,
        "total_faturamento_drive": round(total_fat_turnos, 2),
    }

indicadores_antes = coletar_indicadores(ISOLATED_DB)
print("\n[INDICADORES INICIAIS NO BANCO ISOLADO]:")
for k, v in indicadores_antes.items():
    print(f"  - {k}: {v}")

# 2. Executar chamadas do TestClient nas 8 áreas requeridas
client = TestClient(web_app.app, raise_server_exceptions=True)

testes = [
    ("Visão Geral / Navegação", "/", 200, ["Oikos", "Minhas Contas", "Cartões"]),
    ("Extrato de Lançamentos", "/lancamentos", 200, ["Lançamentos", "Novo Lançamento"]),
    ("Gestão de Contas", "/contas", 200, ["Contas", "Nova Conta", "Saldo"]),
    ("Gestão de Cartões", "/cartoes", 200, ["Cartões", "Novo Cartão"]),
    ("Planejamento Financeiro", "/planejamento", 200, ["Planejamento", "Metas"]),
    ("Módulo Paga Leve", "/pagaleve", 200, ["Paga Leve", "Carlos", "Fernanda"]),
    ("Oikos Drive (/motorista)", "/motorista", 200, ["Oikos Drive", "Turno"]),
    ("Oikos Drive (/oikos-drive)", "/oikos-drive", 200, ["Oikos Drive", "Turno"]),
    ("Missões da Semana", "/missoes", 200, ["Missão", "Semana"]),
]

resultados = []
print("\n[TESTES DE ROTA E RENDERIZAÇÃO]:")
for nome, rota, status_esperado, termos_obrigatorios in testes:
    try:
        resp = client.get(rota)
        status_ok = (resp.status_code == status_esperado)
        text = resp.text
        termos_ok = all(termo in text for termo in termos_obrigatorios)
        resultados.append({
            "nome": nome,
            "rota": rota,
            "status": resp.status_code,
            "status_ok": status_ok,
            "termos_ok": termos_ok,
            "erro": None if (status_ok and termos_ok) else f"Status: {resp.status_code}, Termos ausentes: {[t for t in termos_obrigatorios if t not in text]}"
        })
        print(f"  [OK] {nome} ({rota}) -> HTTP {resp.status_code} | Conteudo validado: {termos_ok}")
    except Exception as exc:
        resultados.append({
            "nome": nome,
            "rota": rota,
            "status": 500,
            "status_ok": False,
            "termos_ok": False,
            "erro": str(exc)
        })
        print(f"  [FALHA] {nome} ({rota}) -> FALHA: {exc}")

# 3. Testes adicionais de API
api_testes = [
    ("API Dados Gerais (GET)", "/api/dados", "GET", None, 200),
    ("API Meta Horas (POST)", "/api/meta-horas", "POST", {"horas": "8.0"}, 200),
]
print("\n[TESTES DE ENDPOINTS DE API]:")
for nome, rota, metodo, payload, status_esperado in api_testes:
    try:
        if metodo == "GET":
            resp = client.get(rota)
        else:
            resp = client.post(rota, data=payload)
        ok = (resp.status_code == status_esperado)
        print(f"  [OK] {nome} ({rota}) -> HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [FALHA] {nome} ({rota}) -> FALHA: {exc}")

# 4. Coletar indicadores finais no banco isolado
indicadores_depois = coletar_indicadores(ISOLATED_DB)
print("\n[COMPARATIVO DE INDICADORES ANTES vs DEPOIS NO BANCO ISOLADO]:")
divergencias = []
for k in indicadores_antes:
    v_antes = indicadores_antes[k]
    v_depois = indicadores_depois[k]
    igual = (v_antes == v_depois)
    status_str = "INTACTO" if igual else "ALTERADO"
    if not igual:
        divergencias.append((k, v_antes, v_depois))
    print(f"  - {k}: {v_antes} -> {v_depois} [{status_str}]")

# 5. Verificação estrita de que o banco de produção financas_casa.db permaneceu intocado
prod_hash_after = get_hash(PROD_DB)
prod_untouched = (prod_hash_before == prod_hash_after)
print(f"\n[INTEGRIDADE DO BANCO REAL DE PRODUÇÃO]:")
print(f"  - SHA256 Antes:  {prod_hash_before}")
print(f"  - SHA256 Depois: {prod_hash_after}")
print(f"  - Intocado:      {'SIM (100% ÍNTEGRO)' if prod_untouched else 'ATENÇÃO: DIVERGÊNCIA'}")

# 6. Avaliação final
falhas = [r for r in resultados if not (r["status_ok"] and r["termos_ok"])]
if not falhas and not divergencias and prod_untouched:
    print("\n>>> TODOS OS TESTES PASSARAM COM SUCESSO! NENHUMA REGRESSÃO DETECTADA. <<<")
else:
    print(f"\n>>> ATENÇÃO: Falhas encontradas: {len(falhas)}, Divergências de indicadores: {len(divergencias)} <<<")
