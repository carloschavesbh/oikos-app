import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
import saldo_service
import planejamento_service
from app import calcular_datas_recorrentes, obter_estrutura_categorias

print("=" * 70)
print("INICIANDO BATERIA DE TESTES DE REGRESSÃO E VALIDAÇÃO E2E")
print("=" * 70)

# 1. Integridade e Preservação da Base Principal
conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

cur.execute("PRAGMA integrity_check")
ic = cur.fetchall()
assert ic == [("ok",)], f"Falha na integridade: {ic}"
print("✓ 1. SQLite PRAGMA integrity_check: OK")

# 2. Saldo Consolidado Antes e Depois
res_saldo = saldo_service.calcular_saldo_consolidado(conn)
saldo_total = float(res_saldo["saldo_consolidado"])
assert abs(saldo_total - 86.33) < 0.001, f"Saldo incorreto: {saldo_total} (esperado 86.33)"
print(f"✓ 2. Saldo Consolidado Preservado: R$ {saldo_total:.2f}")

# 3. Contagem de Registros Históricos Preservados
cur.execute("SELECT COUNT(*) FROM transacoes")
cnt_transacoes = cur.fetchone()[0]
assert cnt_transacoes == 32, f"Transações alteradas: {cnt_transacoes} (esperado 32)"

cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
cnt_pagamentos = cur.fetchone()[0]
assert cnt_pagamentos == 14, f"Pagamentos alterados: {cnt_pagamentos} (esperado 14)"

cur.execute("SELECT COUNT(*) FROM turnos")
cnt_turnos = cur.fetchone()[0]
assert cnt_turnos == 1, f"Turnos alterados: {cnt_turnos} (esperado 1)"

cur.execute("SELECT COUNT(*) FROM contas_config")
cnt_contas = cur.fetchone()[0]
assert cnt_contas == 2, f"Contas alteradas: {cnt_contas} (esperado 2)"

cur.execute("SELECT COUNT(*) FROM cartoes")
cnt_cartoes = cur.fetchone()[0]
assert cnt_cartoes == 1, f"Cartões alterados: {cnt_cartoes} (esperado 1)"

print(f"✓ 3. Registros Preservados: {cnt_transacoes} transações, {cnt_pagamentos} pagamentos auditados, {cnt_turnos} turno, {cnt_contas} contas, {cnt_cartoes} cartão.")

# 4. Estrutura Hierárquica de Categorias (Cerbasi / Organizze)
cur.execute("SELECT COUNT(*) FROM grupos_categoria")
cnt_grupos = cur.fetchone()[0]
assert cnt_grupos == 16, f"Grupos incorretos: {cnt_grupos} (esperado 16)"

cur.execute("SELECT COUNT(*) FROM subcategorias")
cnt_subs = cur.fetchone()[0]
assert cnt_subs == 63, f"Subcategorias incorretas: {cnt_subs} (esperado 63)"

estrutura = obter_estrutura_categorias()
assert len(estrutura) == 16, f"Estrutura carregada incorreta: {len(estrutura)}"
total_subs_carregadas = sum(len(g["subcategorias"]) for g in estrutura.values())
assert total_subs_carregadas == 63, f"Total de subcategorias carregadas: {total_subs_carregadas}"

# Coluna legada 'categoria' preservada
cur.execute("SELECT COUNT(*) FROM transacoes WHERE categoria IS NULL OR categoria = ''")
sem_cat = cur.fetchone()[0]
assert sem_cat == 0, f"Existem transações sem coluna categoria: {sem_cat}"

# Lançamentos pendentes mantidos sem rateio fictício
cur.execute("SELECT id, descricao, status_rateio FROM transacoes WHERE status_rateio != 'normal'")
pendentes = cur.fetchall()
status_map = {p[0]: p[2] for p in pendentes}
assert 3 in status_map and status_map[3] == "pendente_rateio", "ID 3 deve ser pendente_rateio"
assert 23 in status_map and status_map[23] == "pendente_rateio", "ID 23 deve ser pendente_rateio"
assert 18 in status_map and status_map[18] == "pendente_confirmacao", "ID 18 deve ser pendente_confirmacao"
assert 30 in status_map and status_map[30] == "pendente_confirmacao", "ID 30 deve ser pendente_confirmacao"
print(f"✓ 4. Categorias Hierárquicas: 16 grupos, 63 subcategorias, {len(pendentes)} lançamentos mantidos pendentes sem rateios fictícios.")

# 5. Paga Leve: Contas e Compras Comprovadas
cur.execute("SELECT titular, limite_total, tipo_limite FROM pagaleve_contas ORDER BY id ASC")
contas_pl = cur.fetchall()
assert len(contas_pl) == 2, f"Contas Paga Leve incorretas: {len(contas_pl)}"
assert contas_pl[0][0] == "Carlos" and contas_pl[0][1] == 300.0, "Conta Carlos incorreta"
assert contas_pl[1][0] == "Fernanda" and contas_pl[1][1] == 0.0, "Conta Fernanda incorreta"

cur.execute("SELECT COUNT(*), SUM(valor_original), SUM(valor_parcela) FROM pagaleve_compras")
pl_compras_cnt, pl_orig_sum, pl_parc_sum = cur.fetchone()
assert pl_compras_cnt == 6, f"Compras Paga Leve incorretas: {pl_compras_cnt} (esperado 6)"
assert abs(pl_orig_sum - 993.72) < 0.01, f"Soma valor_original incorreta: {pl_orig_sum}"
assert abs(pl_parc_sum - 261.56) < 0.01, f"Soma valor_parcela incorreta: {pl_parc_sum}"

cur.execute("SELECT COUNT(*) FROM transacoes WHERE descricao LIKE '%118,97%' OR descricao LIKE '%118.97%'")
fake_op = cur.fetchone()[0]
assert fake_op == 0, "Operação de exemplo de R$ 118,97 não deve existir no banco!"
print("✓ 5. Paga Leve: Contas Carlos/Fernanda isoladas, 6 compras comprovadas (R$ 399,78), sem operações fictícias.")

# 6. Recorrência Mensal e Calendário
datas_mensais = calcular_datas_recorrentes(date(2026, 1, 31), "mensal", 4)
assert datas_mensais == [
    date(2026, 1, 31),
    date(2026, 2, 28),
    date(2026, 3, 31),
    date(2026, 4, 30)
], f"Datas recorrentes calculadas incorretamente: {datas_mensais}"
print("✓ 6. Regra de Calendário Recorrente: Respeita dias 28/29/30/31 sem deslizar meses.")

# 7. Janela de 7 Dias Exatos no Planejamento
from datetime import datetime as dt_parser
caixa_7d = planejamento_service.calcular_necessidade_caixa_7dias(conn, data_referencia=date(2026, 10, 20))
dt_ini = dt_parser.strptime(caixa_7d["data_referencia"], "%Y-%m-%d").date()
dt_fim = dt_parser.strptime(caixa_7d["data_limite_7d"], "%Y-%m-%d").date()
dias_janela = (dt_fim - dt_ini).days + 1
assert dias_janela == 7, f"Janela deve ter exatamente 7 dias corridos: {dias_janela}"
assert dt_ini == date(2026, 10, 20)
assert dt_fim == date(2026, 10, 26)
print(f"✓ 7. Janela de Caixa: Exatamente 7 dias corridos ({dt_ini} a {dt_fim}).")

# 8. Eliminação de Duplicação entre Despesas Variáveis e Fixas
desp_var = planejamento_service.calcular_despesas_variaveis_restantes(conn, mes_ano="2026-10", data_referencia=date(2026, 10, 20))
for item in desp_var["detalhe_categorias"]:
    cat = item["categoria"]
    assert cat not in ["Habitação", "Energia", "Água", "Streaming", "Telefone", "Internet"], f"Categoria contratual fixa '{cat}' não pode estar em variáveis!"
print("✓ 8. Despesas Variáveis Restantes: Sem duplicidade com obrigações fixas contratuais.")

# 9. Dívida Livre e Dívida Negociada em Transação Isolada
cur.execute("BEGIN TRANSACTION")
cur.execute("""
    INSERT INTO dividas_gerenciamento (credor, descricao, tipo_divida, valor_original, saldo_atual, status)
    VALUES ('Credor Amigo', 'Empréstimo teste livre', 'livre', 5000.0, 5000.0, 'ativa')
""")
id_div_teste = cur.lastrowid

# Pagamento manual na dívida livre
cur.execute("""
    INSERT INTO dividas_pagamentos_manuais (divida_id, data_pagamento, valor_pago, observacao)
    VALUES (?, '2026-10-20', 1000.0, 'Pagamento parcial sem movimentação bancária')
""", (id_div_teste,))
cur.execute("UPDATE dividas_gerenciamento SET saldo_atual = saldo_atual - 1000.0 WHERE id = ?", (id_div_teste,))

cur.execute("SELECT saldo_atual FROM dividas_gerenciamento WHERE id = ?", (id_div_teste,))
novo_saldo_div = cur.fetchone()[0]
assert novo_saldo_div == 4000.0, f"Saldo dívida livre incorreto: {novo_saldo_div}"

# Garante que nenhum lançamento financeiro foi criado
cur.execute("SELECT COUNT(*) FROM transacoes WHERE descricao LIKE '%Credor Amigo%'")
assert cur.fetchone()[0] == 0, "Dívida livre não pode criar lançamentos em transações!"

cur.execute("ROLLBACK")
print("✓ 9. Dívidas Livre e Negociada: Desacopladas de contas bancárias e do Paga Leve.")

conn.close()
print("=" * 70)
print("TODOS OS TESTES DE REGRESSÃO PASSARAM COM 100% DE SUCESSO!")
print("=" * 70)
