import sqlite3
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
import saldo_service

db_path = 'financas_casa.db'
backup_path = 'financas_casa_backup_pre_saneamento_motorista.db'

# 1. Backup integral consistente
source = sqlite3.connect(db_path)
dest = sqlite3.connect(backup_path)
source.backup(dest)
dest.close()
source.close()
print(f"Backup integral criado com sucesso em: {backup_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 2. Verifica integridade antes
cur.execute("PRAGMA integrity_check")
check_antes = cur.fetchall()
print("Integridade pré-saneamento:", check_antes)
assert check_antes == [('ok',)]

# 3. Confere exatamente o conteúdo dos registros 34, 35 e 36 antes de remover
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, pago FROM transacoes WHERE id IN (34, 35, 36) ORDER BY id ASC")
rows = cur.fetchall()
print("\nRegistros identificados para remoção:")
for r in rows:
    print(r)

assert len(rows) == 3, f"Esperava 3 registros (34, 35, 36), encontrou {len(rows)}"
assert rows[0][0] == 34 and rows[0][3] == 17.6 and rows[0][4] == 'receita'
assert rows[1][0] == 35 and rows[1][3] == 60.0 and rows[1][4] == 'despesa'
assert rows[2][0] == 36 and rows[2][3] == 17.6 and rows[2][4] == 'receita'
print("Validação dos registros 34, 35 e 36: 100% conferida!")

# 4. Remove pontualmente os 3 registros indevidos
cur.execute("DELETE FROM transacoes WHERE id IN (34, 35, 36)")
conn.commit()
print("Registros 34, 35 e 36 removidos com sucesso.")

# 5. Confere preservação do Turno id=2
cur.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao FROM turnos WHERE id = 2")
turno_2 = cur.fetchone()
print("\nTurno id=2 preservado na tabela turnos:", turno_2)
assert turno_2 is not None
assert turno_2[0] == 2
assert turno_2[4] == 17.6
assert turno_2[5] == 0.0

# 6. Adiciona coluna turno_id em transacoes se não existir
cur.execute("PRAGMA table_info(transacoes)")
cols_t = [c[1] for c in cur.fetchall()]
if "turno_id" not in cols_t:
    cur.execute("ALTER TABLE transacoes ADD COLUMN turno_id INTEGER REFERENCES turnos(id)")
    print("Coluna turno_id adicionada em transacoes.")

# 7. Adiciona colunas operacionais em turnos se não existirem
cur.execute("PRAGMA table_info(turnos)")
cols_turnos = [c[1] for c in cur.fetchall()]
novas_cols_turnos = [
    ("plataforma", "TEXT DEFAULT '99'"),
    ("valor_transferido_banco", "REAL DEFAULT 0"),
    ("dinheiro_fisico_recebido", "REAL DEFAULT 0"),
    ("despesas_diretas_app", "REAL DEFAULT 0"),
    ("combustivel_consumido", "REAL DEFAULT 0"),
    ("status_conciliacao", "TEXT DEFAULT 'conciliado'")
]
for col, c_def in novas_cols_turnos:
    if col not in cols_turnos:
        cur.execute(f"ALTER TABLE turnos ADD COLUMN {col} {c_def}")
print("Colunas de conciliação adicionadas em turnos.")

conn.commit()

# 8. Verifica integridade pós-saneamento
cur.execute("PRAGMA integrity_check")
check_pos = cur.fetchall()
print("\nIntegridade pós-saneamento:", check_pos)
assert check_pos == [('ok',)]

# 9. Confere os saldos calculados pelo saldo_service
res_mp = saldo_service.calcular_saldo_conta(conn, 1)
res_cart = saldo_service.calcular_saldo_conta(conn, 2)
res_cons = saldo_service.calcular_saldo_consolidado(conn)

print("\n--- SALDOS RESTAURADOS EM FINANCAS_CASA.DB ---")
print(f"Mercado Pago (ID 1): R$ {res_mp['saldo_atual']} (esperado: R$ 8.83)")
print(f"Dinheiro / Carteira (ID 2): R$ {res_cart['saldo_atual']} (esperado: R$ 100.00)")
print(f"Saldo Consolidado Geral: R$ {res_cons['saldo_consolidado']} (esperado: R$ 108.83)")

assert res_mp['saldo_atual'] == Decimal("8.83"), f"Erro no saldo do Mercado Pago: {res_mp['saldo_atual']}"
assert res_cart['saldo_atual'] == Decimal("100.00"), f"Erro no saldo da Carteira: {res_cart['saldo_atual']}"
assert res_cons['saldo_consolidado'] == Decimal("108.83"), f"Erro no saldo Consolidado: {res_cons['saldo_consolidado']}"

cur.execute("SELECT COUNT(*) FROM transacoes")
print(f"Total de transações legítimas no banco: {cur.fetchone()[0]}")

conn.close()
print("\nSaneamento concluído com êxito absoluto!")
