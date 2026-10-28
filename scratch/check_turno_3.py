import sys
sys.path.insert(0, '.')
import sqlite3
import saldo_service

conn = sqlite3.connect('financas_casa.db')
conn.row_factory = sqlite3.Row

print("=== SALDOS DAS CONTAS ===")
contas = saldo_service.obter_contas(conn, incluir_cofrinhos=True)
for c in contas:
    cid = c['id']
    cnome = c['nome']
    saldo_info = saldo_service.calcular_saldo_conta(conn, cid)
    print(f"Conta #{cid} {cnome} (Tipo: {c.get('tipo', '')}, Cofrinho: {c.get('cofrinho', 0)}):")
    print(f"   Saldo Atual: R$ {saldo_info['saldo_atual']:.2f}")

cons = saldo_service.calcular_saldo_consolidado(conn)
print("\n=== CONSOLIDADO ===")
print(f"Saldo Consolidado Total: R$ {cons['saldo_consolidado']:.2f}")
print(f"Saldo Livre para Uso: R$ {cons['saldo_livre']:.2f}")
print(f"Saldo em Cofrinhos: R$ {cons['saldo_cofrinhos']:.2f}")

conn.close()
