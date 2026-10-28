import sys, os
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import saldo_service

print("=== BACKUP DATABASE ===")
conn_bkp = sqlite3.connect('financas_casa_backup_20261020_pre_integracao.db')
contas_bkp = saldo_service.obter_contas(conn_bkp)
for c in contas_bkp:
    res = saldo_service.calcular_saldo_conta(conn_bkp, c["id"])
    print(f"Conta ID: {c['id']}, Nome: {c['nome']}, Saldo Atual: {res['saldo_atual']}, Saldo Centavos: {res['saldo_centavos']}")
    print(f"   Tem marco: {res['tem_marco']}, Marco data: {res['marco_data']}, Marco saldo: {res['marco_saldo']}")
    print(f"   Rec post: {res['total_receitas_posteriores']}, Desp post: {res['total_despesas_posteriores']}, Transf in: {res['total_transf_entradas']}, Transf out: {res['total_transf_saidas']}")
res_cons_bkp = saldo_service.calcular_saldo_consolidado(conn_bkp)
print("Consolidado Backup:", res_cons_bkp["saldo_consolidado"])
conn_bkp.close()

print("\n=== PRODUCTION DATABASE ===")
conn_prod = sqlite3.connect('financas_casa.db')
contas_prod = saldo_service.obter_contas(conn_prod)
for c in contas_prod:
    res = saldo_service.calcular_saldo_conta(conn_prod, c["id"])
    print(f"Conta ID: {c['id']}, Nome: {c['nome']}, Saldo Atual: {res['saldo_atual']}, Saldo Centavos: {res['saldo_centavos']}")
    print(f"   Tem marco: {res['tem_marco']}, Marco data: {res['marco_data']}, Marco saldo: {res['marco_saldo']}")
    print(f"   Rec post: {res['total_receitas_posteriores']}, Desp post: {res['total_despesas_posteriores']}, Transf in: {res['total_transf_entradas']}, Transf out: {res['total_transf_saidas']}")
res_cons_prod = saldo_service.calcular_saldo_consolidado(conn_prod)
print("Consolidado Produção:", res_cons_prod["saldo_consolidado"])
conn_prod.close()
