import sqlite3

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

cur.execute("SELECT id, descricao, valor, pago, grupo_parcelamento FROM transacoes WHERE descricao LIKE '%Paga Leve%'")
rows = cur.fetchall()
tot = sum(r[2] for r in rows)
print("Soma das 9 transações Paga Leve:", tot)

# Check all tables and scripts for 399.78
import glob
print("\nBuscando 399.78 nos arquivos de scratch:")
for f in glob.glob('scratch/*.py'):
    with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
        content = fp.read()
        if '399.78' in content or '399,78' in content:
            print("Encontrado em:", f)

conn.close()
