with open('planejamento_anual_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

ancora = "conn.commit()"
idx = text.find(ancora)
assert idx != -1, "conn.commit() não encontrado"

migracao = """    # Migração idempotente de colunas novas em planejamento_despesas_eventuais
    cur.execute("PRAGMA table_info(planejamento_despesas_eventuais)")
    colunas_dev = [c[1] for c in cur.fetchall()]
    if "valor_reservado_manual" not in colunas_dev:
        cur.execute("ALTER TABLE planejamento_despesas_eventuais ADD COLUMN valor_reservado_manual REAL DEFAULT 0.0")

"""

text = text[:idx] + migracao + text[idx:]

with open('planejamento_anual_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("SUCESSO: Migração idempotente adicionada a planejamento_anual_service.py!")
