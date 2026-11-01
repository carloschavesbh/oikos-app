# Script para auditar a logica de passivos sem duplicidade
import sys, os, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('financas_remodelacao.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Cartoes cadastrados
cur.execute("SELECT id, nome FROM cartoes")
cartoes_nomes = [r["nome"] for r in cur.fetchall()]
print(f"Cartões cadastrados: {cartoes_nomes}")

# 2. Transações pendentes em cartões
if cartoes_nomes:
    placeholders = ",".join("?" for _ in cartoes_nomes)
    cur.execute(f"""
        SELECT id, descricao, valor, data, conta
        FROM transacoes
        WHERE conta IN ({placeholders}) AND (pago = 0 OR pago IS NULL)
        ORDER BY data ASC
    """, cartoes_nomes)
    rows_crd = cur.fetchall()
else:
    rows_crd = []

tot_cartao = sum(float(r["valor"]) for r in rows_crd)
print(f"Total a vencer em Cartões de Crédito: R$ {tot_cartao:.2f} ({len(rows_crd)} lançamentos)")
for r in rows_crd:
    print(f"  - {r['descricao']}: R$ {r['valor']} ({r['conta']})")

# 3. Transações pendentes em Paga Leve (sem sobrepor com cartões)
ids_crd = {r["id"] for r in rows_crd}
cur.execute("""
    SELECT id, descricao, valor, data, grupo_parcelamento
    FROM transacoes
    WHERE grupo_parcelamento LIKE 'pagaleve_%' AND (pago = 0 OR pago IS NULL)
    ORDER BY data ASC
""")
rows_pl = [r for r in cur.fetchall() if r["id"] not in ids_crd]
tot_pagaleve = sum(float(r["valor"]) for r in rows_pl)
print(f"\nTotal a vencer no Paga Leve: R$ {tot_pagaleve:.2f} ({len(rows_pl)} parcelas)")
for r in rows_pl:
    print(f"  - {r['descricao']}: R$ {r['valor']} ({r['grupo_parcelamento']})")

# 4. Outros parcelamentos pendentes (sem sobrepor com cartões nem Paga Leve)
ids_ja_somados = ids_crd.union({r["id"] for r in rows_pl})
cur.execute("""
    SELECT id, descricao, valor, data, grupo_parcelamento
    FROM transacoes
    WHERE grupo_parcelamento IS NOT NULL AND (pago = 0 OR pago IS NULL)
    ORDER BY data ASC
""")
rows_outros_parc = [r for r in cur.fetchall() if r["id"] not in ids_ja_somados]
tot_outros_parc = sum(float(r["valor"]) for r in rows_outros_parc)
print(f"\nTotal de outros parcelamentos a vencer: R$ {tot_outros_parc:.2f} ({len(rows_outros_parc)} parcelas)")
for r in rows_outros_parc[:3]:
    print(f"  - {r['descricao']}: R$ {r['valor']} ({r['grupo_parcelamento']})")

# 5. Dívidas formais em dividas_gerenciamento
cur.execute("SELECT id, credor, descricao, saldo_atual, status FROM dividas_gerenciamento WHERE status = 'ativa'")
rows_div = cur.fetchall()
tot_dividas_formais = sum(float(r["saldo_atual"] or 0) for r in rows_div)
print(f"\nTotal Dívidas Formais (Acordos/Empréstimos): R$ {tot_dividas_formais:.2f} ({len(rows_div)} ativas)")

# Total Passivo Consolidado sem duplicação
tot_passivos = tot_dividas_formais + tot_cartao + tot_pagaleve + tot_outros_parc
print(f"\n===> TOTAL DE PASSIVOS CONSOLIDADO (SEM DUPLICIDADE): R$ {tot_passivos:.2f}")

conn.close()
