import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=" * 70)
print("AUDITORIA 1: CATEGORIAS E ESTRUTURA ATUAL (RECEITAS, DÍVIDAS, JUROS, CARTÃO)")
print("=" * 70)

# 1. Grupos relacionados a receitas e dívidas
cur.execute("""
    SELECT g.id, g.nome, g.tipo, g.icone, COUNT(s.id) as total_subs
    FROM grupos_categoria g
    LEFT JOIN subcategorias s ON s.grupo_id = g.id
    GROUP BY g.id
    ORDER BY g.tipo, g.ordem
""")
for r in cur.fetchall():
    print(f"Grupo ID {r[0]}: {r[3]} {r[1]} (Tipo: {r[2]}) - {r[4]} subcategorias")

print("\n--- SUBCATEGORIAS DO GRUPO RECEITAS E DÍVIDAS ---")
cur.execute("""
    SELECT s.id, g.nome as grupo, s.nome, s.icone, s.natureza_padrao, s.finalidade
    FROM subcategorias s
    JOIN grupos_categoria g ON s.grupo_id = g.id
    WHERE g.nome LIKE '%Receita%' OR g.nome LIKE '%Dívida%' OR g.nome LIKE '%Serviços Financeiros%' OR g.nome LIKE '%Eventual%'
    ORDER BY g.nome, s.nome
""")
for r in cur.fetchall():
    print(f"  Subcat #{r[0]}: [{r[1]}] {r[3]} {r[2]} | Natureza: {r[4]} | Finalidade: {r[5]}")

print("\n--- 2. RECEITAS HISTÓRICAS EM TRANSACOES ---")
cur.execute("""
    SELECT id, data, descricao, valor, categoria, conta, pago, grupo_id, subcategoria_id, natureza_gasto
    FROM transacoes
    WHERE tipo = 'receita'
    ORDER BY data ASC
""")
receitas = cur.fetchall()
print(f"Total de receitas cadastradas: {len(receitas)}")
for r in receitas:
    print(f"  Receita #{r[0]} ({r[1]}): {r[2]} -> R$ {r[3]:.2f} (Conta: {r[5]} | Cat: {r[4]} | Nat: {r[9]})")

print("\n--- 3. TRANSAÇÕES DE FATURA, EMPRÉSTIMO OU JUROS EM TRANSACOES ---")
cur.execute("""
    SELECT id, data, descricao, valor, tipo, categoria, conta, pago, status_conciliacao_fatura, status_rateio
    FROM transacoes
    WHERE descricao LIKE '%fatura%' OR descricao LIKE '%empréstimo%' OR descricao LIKE '%Crediserv%' OR descricao LIKE '%BV%' OR categoria LIKE '%Fatura%' OR categoria LIKE '%Dívida%'
    ORDER BY data ASC
""")
especiais = cur.fetchall()
print(f"Total de transações de dívida/fatura encontradas: {len(especiais)}")
for r in especiais:
    print(f"  Transação #{r[0]} ({r[1]}): [{r[4]}] {r[2]} -> R$ {r[3]:.2f} (Conta: {r[6]} | Cat: {r[5]} | Pago: {r[7]} | Fatura: {r[8]})")

print("\n--- 4. CARTÕES CADASTRADOS ---")
cur.execute("SELECT * FROM cartoes")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))

conn.close()
