import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cursor = conn.cursor()

print("=== VERIFICAÇÃO DE RENDA 99 (R$ 612,05) EM financas_casa.db ===")

# Buscar em turnos
df_turnos = pd.read_sql_query("SELECT * FROM turnos", conn)
print(f"\nTotal turnos cadastrados: {len(df_turnos)}")
if not df_turnos.empty:
    print(df_turnos.to_string())

# Buscar valor 612.05 em qualquer tabela
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall() if not r[0].startswith('sqlite_')]

found_any = False
for t in tables:
    cursor.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cursor.fetchall()]
    for c in cols:
        try:
            query = f"SELECT * FROM {t} WHERE cast({c} as text) LIKE '%612%'"
            res = cursor.execute(query).fetchall()
            if res:
                print(f"Encontrado em {t}.{c}: {res}")
                found_any = True
        except:
            pass

if not found_any:
    print("Nenhum registro com 612.05 foi encontrado em nenhuma tabela do banco!")

# Verificar lançamentos de motorista / turnos / receitas em outubro
print("\n=== RECEITAS EM transacoes ===")
df_rec = pd.read_sql_query("SELECT * FROM transacoes WHERE tipo = 'receita'", conn)
print(df_rec.to_string())

conn.close()
