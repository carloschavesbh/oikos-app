import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import saldo_service

conn = sqlite3.connect("financas_casa.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 1. CONTAS CONFIGURADAS E SALDOS ATUAIS ===")
for c in saldo_service.obter_contas(conn):
    res = saldo_service.calcular_saldo_conta(conn, c["id"])
    print(f"Conta ID {c['id']:2d} | {c['nome']:25s} | Saldo: R$ {res['saldo_atual']:10.2f}")

tot = saldo_service.calcular_saldo_consolidado(conn)
print(f"\nSaldo Total Consolidado Disponível: R$ {tot['saldo_consolidado']:.2f}")

print("\n=== 2. EXTRATO HISTÓRICO DA CARTEIRA (CONTA ID 2) ===")
cur.execute("""
    SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario
    FROM transacoes
    WHERE (conta_id = 2 OR conta LIKE '%Dinheiro%' OR conta LIKE '%Carteira%' OR conta_destino_id = 2)
    ORDER BY data ASC, id ASC
""")
saldo_cart = 0.0
for r in cur.fetchall():
    val = float(r["valor"])
    tipo = r["tipo"]
    pago = r["pago"]
    afeta = r["afeta_saldo_bancario"]
    imp = 0.0
    if pago == 1 and afeta == 1:
        if tipo == "receita":
            imp = +val
        elif tipo == "despesa":
            imp = -val
        elif tipo == "transferencia":
            if r["conta_id"] == 2:
                imp = -val
            elif r["conta_destino_id"] == 2:
                imp = +val
    saldo_cart += imp
    print(f"ID {r['id']:2d} | {r['data']} | {tipo:13s} | {r['categoria']:25s} | R$ {val:7.2f} | Imp: {imp:+7.2f} | Saldo: R$ {saldo_cart:+7.2f} | {r['descricao']}")

print(f"\nSaldo Final Carteira: R$ {saldo_cart:.2f}")

print("\n=== 3. AUDITORIA MERCADO PAGO (CONTA ID 1) ===")
cur.execute("""
    SELECT id, data, descricao, valor, tipo, categoria, conta, conta_id, conta_destino_id, pago, afeta_saldo_bancario
    FROM transacoes
    WHERE (conta_id = 1 OR conta LIKE '%Mercado Pago%' OR conta_destino_id = 1)
    ORDER BY data ASC, id ASC
""")
saldo_mp = 0.0
for r in cur.fetchall():
    val = float(r["valor"])
    tipo = r["tipo"]
    pago = r["pago"]
    afeta = r["afeta_saldo_bancario"]
    imp = 0.0
    if pago == 1 and afeta == 1:
        if tipo == "receita":
            imp = +val
        elif tipo == "despesa":
            imp = -val
        elif tipo == "transferencia":
            if r["conta_id"] == 1:
                imp = -val
            elif r["conta_destino_id"] == 1:
                imp = +val
    saldo_mp += imp
    print(f"ID {r['id']:2d} | {r['data']} | {tipo:13s} | {r['categoria']:25s} | R$ {val:7.2f} | Imp: {imp:+7.2f} | Saldo: R$ {saldo_mp:+7.2f} | {r['descricao']}")

print(f"\nSaldo Final Mercado Pago: R$ {saldo_mp:.2f}")
print(f"Consolidado (Mercado Pago + Carteira): R$ {saldo_mp + saldo_cart:.2f}")
conn.close()
