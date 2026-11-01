import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_remodelacao.db')

print("--- 1. CATEGORIAS DE RECEITAS (tipo='receita') ---")
cats = conn.execute("SELECT categoria, COUNT(*), MIN(data), MAX(data), SUM(valor) FROM transacoes WHERE tipo='receita' GROUP BY categoria").fetchall()
for c in cats:
    print(c)

print("\n--- 2. AMOSTRA DE RECEITAS (tipo='receita') ---")
rows = conn.execute("SELECT id, data, descricao, valor, categoria, conta FROM transacoes WHERE tipo='receita' ORDER BY data DESC LIMIT 20").fetchall()
for r in rows:
    print(r)

print("\n--- 3. RECEITAS POR MÊS ---")
meses = conn.execute("SELECT strftime('%Y-%m', data) as mes, COUNT(*), SUM(valor) FROM transacoes WHERE tipo='receita' GROUP BY mes ORDER BY mes DESC").fetchall()
for m in meses:
    print(m)

print("\n--- 4. RELAÇÃO TURNOS (DRIVE) vs TRANSAÇÕES ---")
# Vamos checar se há transações criadas por turnos ou se o ganho de turnos é separado
turnos_receitas = conn.execute("SELECT id, data, descricao, valor, categoria, conta FROM transacoes WHERE tipo='receita' AND (descricao LIKE '%99%' OR descricao LIKE '%uber%' OR descricao LIKE '%turno%' OR categoria LIKE '%motorista%' OR categoria LIKE '%drive%')").fetchall()
print(f"Receitas com menção a 99/turno/drive: {len(turnos_receitas)}")
for tr in turnos_receitas[:10]:
    print(tr)

print("\n--- 5. MARCO DE PRODUÇÃO DO MOTORISTA ---")
marcos = conn.execute("SELECT * FROM motorista_marco_producao").fetchall()
for m in marcos:
    print(m)

conn.close()
