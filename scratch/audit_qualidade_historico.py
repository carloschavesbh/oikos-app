import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_remodelacao.db')

rows = conn.execute("""
    SELECT 
        strftime('%Y-%m', data) as mes,
        COUNT(*) as total_transacoes,
        SUM(CASE WHEN tipo='receita' THEN 1 ELSE 0 END) as qtd_receitas,
        SUM(CASE WHEN tipo='receita' THEN valor ELSE 0 END) as total_receitas,
        SUM(CASE WHEN tipo='despesa' THEN 1 ELSE 0 END) as qtd_despesas,
        SUM(CASE WHEN tipo='despesa' THEN valor ELSE 0 END) as total_despesas,
        MIN(data) as primeira_data,
        MAX(data) as ultima_data
    FROM transacoes
    GROUP BY mes
    ORDER BY mes DESC
""").fetchall()

print(f"{'Mês':<8} | {'Tot Tx':<6} | {'Qtd Rec':<7} | {'Total Rec (R$)':<15} | {'Qtd Desp':<8} | {'Total Desp (R$)':<15} | {'Período'}")
print("-" * 90)
for r in rows:
    print(f"{r[0]:<8} | {r[1]:<6} | {r[2]:<7} | {r[3] or 0:<15.2f} | {r[4]:<8} | {r[5] or 0:<15.2f} | {r[6]} a {r[7]}")

print("\n--- DETALHAMENTO DE RECEITAS POR MÊS ---")
recs = conn.execute("""
    SELECT 
        strftime('%Y-%m', data) as mes,
        categoria,
        COUNT(*) as qtd,
        SUM(valor) as total
    FROM transacoes
    WHERE tipo='receita'
    GROUP BY mes, categoria
    ORDER BY mes DESC, total DESC
""").fetchall()

for r in recs:
    print(f"{r[0]} | {r[1]:<25} | {r[2]} txs | R$ {r[3]:.2f}")

conn.close()
