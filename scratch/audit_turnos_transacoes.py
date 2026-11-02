import sqlite3

conn = sqlite3.connect('financas_remodelacao.db')

print("--- 1. ÚLTIMOS TURNOS ---")
turnos = conn.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao FROM turnos ORDER BY data DESC LIMIT 10").fetchall()
for t in turnos:
    print(t)

print("\n--- 2. TRANSAÇÕES NA MESMA DATA DOS TURNOS ---")
for t in turnos[:3]:
    t_id, t_data, t_horas, t_km, t_bruto, t_comb, t_obs = t
    print(f"\nTurno ID {t_id} na data {t_data} (Bruto: R$ {t_bruto:.2f}, Combustível: R$ {t_comb:.2f}):")
    txs = conn.execute("SELECT id, data, descricao, valor, tipo, categoria, conta FROM transacoes WHERE data = ?", (t_data,)).fetchall()
    for tx in txs:
        print(f"  Tx #{tx[0]}: {tx[2]} | R$ {tx[3]:.2f} | {tx[4]} | Cat: {tx[5]} | Conta: {tx[6]}")

print("\n--- 3. VERIFICAR SE O GANHO DO TURNO VIRA TRANSAÇÃO AUTOMATICAMENTE ---")
# Vamos checar em web_app.py ou app.py onde turnos são inseridos
conn.close()

