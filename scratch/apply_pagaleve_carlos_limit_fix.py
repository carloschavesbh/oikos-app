import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("--- APLICANDO AJUSTE CONTROLADO NA CONTA PAGA LEVE CARLOS ---")

# 1. Verifica se coluna disponibilidade_atual existe em pagaleve_contas
cur.execute("PRAGMA table_info(pagaleve_contas)")
cols = [c[1] for c in cur.fetchall()]
if 'disponibilidade_atual' not in cols:
    cur.execute("ALTER TABLE pagaleve_contas ADD COLUMN disponibilidade_atual REAL DEFAULT NULL")
    print("✓ Coluna 'disponibilidade_atual' adicionada com sucesso em pagaleve_contas.")

# 2. Atualiza o limite de Carlos para R$ 300,00
cur.execute("""
    UPDATE pagaleve_contas
    SET limite_total = 300.0,
        tipo_limite = 'fixo',
        observacoes = 'Conta Carlos com limite de referência R$ 300,00 (permite compras acumuladas acima desse valor)'
    WHERE titular = 'Carlos'
""")
print(f"✓ Limite de Carlos atualizado para R$ 300,00 ({cur.rowcount} linha afetada).")

conn.commit()

# 3. Consulta e validação
cur.execute("SELECT id, titular, tipo_limite, limite_total, disponibilidade_atual, observacoes FROM pagaleve_contas")
for row in cur.fetchall():
    print("Conta PL:", row)

conn.close()
print("--- AJUSTE CONCLUÍDO COM SUCESSO ---")
