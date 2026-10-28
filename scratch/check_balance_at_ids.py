import sqlite3

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

cur.execute("""
    SELECT SUM(CASE WHEN tipo='receita' THEN valor ELSE -valor END)
    FROM transacoes
    WHERE id <= 33 AND pago = 1 AND (afeta_saldo_bancario = 1 OR afeta_saldo_bancario IS NULL)
      AND (conta = 'Mercado Pago' OR conta_id = 1)
""")
val_33 = cur.fetchone()[0]
print("Saldo calculado com transacoes id <= 33:", val_33)

cur.execute("""
    SELECT SUM(CASE WHEN tipo='receita' THEN valor ELSE -valor END)
    FROM transacoes
    WHERE id <= 36 AND pago = 1 AND (afeta_saldo_bancario = 1 OR afeta_saldo_bancario IS NULL)
      AND (conta = 'Mercado Pago' OR conta_id = 1)
""")
val_36 = cur.fetchone()[0]
print("Saldo calculado com transacoes id <= 36:", val_36)

conn.close()
