import sqlite3

conn = sqlite3.connect('financas_casa.db')
c = conn.cursor()
c.execute("SELECT id, nome, tipo, cor FROM contas_config")
print("Contas atuais:")
for r in c.fetchall():
    print(r)

c.execute("SELECT DISTINCT conta FROM transacoes")
print("\nContas em transacoes:")
for r in c.fetchall():
    print(r)

conn.close()
