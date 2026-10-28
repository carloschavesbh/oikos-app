import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath("."))
import app
import saldo_service
import planejamento_service

# Inicializa banco
app.inicializar_banco()

conn = app.conectar()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM transacoes")
transacoes_cnt = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM pagamentos_despesas")
pagamentos_cnt = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM turnos")
turnos_cnt = cur.fetchone()[0]

cur.execute("SELECT id, descricao, valor, status_conciliacao_fatura FROM transacoes WHERE descricao LIKE '%Acordo BV%'")
bv_info = cur.fetchone()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'planejamento_%' ORDER BY name")
tabelas_planejamento = [r[0] for r in cur.fetchall()]

s = saldo_service.calcular_saldo_consolidado(conn)

print(f"Transacoes: {transacoes_cnt} (Esperado 32)")
print(f"Pagamentos: {pagamentos_cnt} (Esperado 14)")
print(f"Turnos: {turnos_cnt} (Esperado 1)")
print(f"Acordo BV: id={bv_info[0]}, desc='{bv_info[1]}', valor={bv_info[2]}, status='{bv_info[3]}'")
print(f"Tabelas criadas: {tabelas_planejamento}")
print(f"Saldo Consolidado: R$ {s['saldo_consolidado']}")
for c in s['contas']:
    print(f"  Conta: {c['conta_nome']} | Saldo: R$ {c['saldo_atual']}")

assert transacoes_cnt == 32
assert pagamentos_cnt == 14
assert turnos_cnt == 1
assert bv_info[2] == 1428.82
assert bv_info[3] == "pendente_confirmacao"
assert s['saldo_consolidado'] == saldo_service.Decimal("86.33")

# Confere se os blocos novos são carregados
col_esq, col_dir, vis = app.carregar_layout_dashboard()
print(f"Blocos Coluna Esquerda: {col_esq}")
print(f"Blocos Coluna Direita: {col_dir}")
assert "missao_ipva" in col_esq or "missao_ipva" in col_dir
assert "caixa_7dias" in col_esq or "caixa_7dias" in col_dir
assert "projecao_mes" in col_esq or "projecao_mes" in col_dir
assert "capacidade_trabalho" in col_esq or "capacidade_trabalho" in col_dir

conn.close()
print("\n[VERIFICACAO FINAL CONCLUIDA COM 100% DE SUCESSO!]")
