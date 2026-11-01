import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_remodelacao.db')

print("--- 1. TIPOS DE TRANSAÇÃO ---")
print(conn.execute("SELECT tipo, COUNT(*), SUM(valor) FROM transacoes GROUP BY tipo").fetchall())

print("\n--- 2. CATEGORIAS DE RECEITAS ---")
print(conn.execute("SELECT categoria, COUNT(*), MIN(data), MAX(data), SUM(valor) FROM transacoes WHERE tipo='Receita' GROUP BY categoria").fetchall())

print("\n--- 3. AMOSTRA DE RECEITAS ---")
rows = conn.execute("SELECT id, data, descricao, valor, categoria, conta FROM transacoes WHERE tipo='Receita' ORDER BY data DESC LIMIT 15").fetchall()
for r in rows:
    print(r)

print("\n--- 4. HISTÓRICO DE TURNOS (DRIVE) ---")
turnos_stat = conn.execute("SELECT COUNT(*), MIN(data), MAX(data), SUM(ganho_bruto), SUM(combustivel), SUM(horas) FROM turnos").fetchone()
print(f"Total turnos: {turnos_stat[0]}, De {turnos_stat[1]} a {turnos_stat[2]}, Ganho Bruto Total: R$ {turnos_stat[3]:,.2f}, Combustível: R$ {turnos_stat[4]:,.2f}, Horas: {turnos_stat[5]:.1f}h")

print("\n--- 5. COFRINHOS CADASTRADOS ---")
cofrinhos = conn.execute("SELECT id, nome, saldo_confirmado, meta_valor, objetivo FROM cofrinhos").fetchall()
for c in cofrinhos:
    print(c)

print("\n--- 6. TRANSFERÊNCIAS REGISTRADAS ---")
transf = conn.execute("SELECT COUNT(*), SUM(valor) FROM transacoes WHERE tipo LIKE '%transf%' OR categoria LIKE '%transf%'").fetchone()
print(f"Transferências: {transf}")

conn.close()
