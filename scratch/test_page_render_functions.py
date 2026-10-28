import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd
from datetime import date

print("--- TESTANDO IMPORTAÇÃO E ROTEAMENTO DO APP.PY ---")
import app

# Testa conexão com o banco SQLite real de produção
conn = app.conectar()
df_transacoes = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data ASC, id ASC", conn)
df_turnos = pd.read_sql_query("SELECT * FROM turnos ORDER BY data DESC", conn)
conn.close()

print(f"Total de transações carregadas: {len(df_transacoes)}")
print(f"Total de turnos carregados: {len(df_turnos)}")

# Verifica se todas as funções esperadas existem no módulo
funcoes_esperadas = [
    "render_visao_geral",
    "render_lancamentos",
    "render_contas",
    "render_cartoes",
    "render_motorista_app",
    "render_paga_leve",
    "render_dividas",
    "render_categorias",
    "render_planejamento_metas",
    "render_relatorios",
    "render_configuracoes",
    "modal_nova_despesa",
    "modal_nova_divida_livre",
    "modal_novo_acordo_divida",
    "modal_pagamento_manual_divida",
    "modal_transformar_divida_negociada",
    "modal_novo_grupo",
    "modal_nova_subcategoria",
    "modal_classificar_transacao",
    "render_conteudo_bloco_paga_leve",
    "calcular_datas_recorrentes",
    "obter_estrutura_categorias",
]

for fn in funcoes_esperadas:
    assert hasattr(app, fn), f"Função {fn} não encontrada no módulo app!"
    print(f"✓ {fn} está presente e acessível.")

print("--- SUCESSO: TODAS AS FUNÇÕES DE ROTEAMENTO E RENDERIZAÇÃO ESTÃO PRESENTES ---")
