import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== 1. MARCOS DE CONCILIACAO (ajustes_saldo) ===")
cur.execute("SELECT id, conta_id, data, saldo_informado_centavos, saldo_calculado_centavos, diferenca_centavos, tipo, status, motivo, criado_em, transacoes_contempladas_ids FROM ajustes_saldo")
for r in cur.fetchall():
    print(r)

print("\n=== 2. REGISTROS DA TABELA TURNOS ===")
cur.execute("SELECT id, data, horas, km, ganho_bruto, combustivel, observacao, periodo FROM turnos")
for r in cur.fetchall():
    print(r)

print("\n=== 3. REGISTROS 34, 35 E 36 EM TRANSACOES ===")
cur.execute("SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, pago, afeta_saldo_bancario, grupo_parcelamento FROM transacoes WHERE id IN (34, 35, 36)")
for r in cur.fetchall():
    print(r)

print("\n=== 4. SQLITE_SEQUENCE (ÚLTIMOS IDS GERADOS) ===")
cur.execute("SELECT * FROM sqlite_sequence")
for r in cur.fetchall():
    print(r)

conn.close()
