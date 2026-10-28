import sqlite3
import pandas as pd

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("=== DETALHAMENTO DE CADA COMPRA PAGA LEVE ===")
cur.execute("SELECT id, grupo_parcelamento, descricao, titular, total_parcelas, valor_parcela, valor_original, status FROM pagaleve_compras")
compras = cur.fetchall()

tot_devido = 0
tot_original = 0
tot_pago_registrado = 0

for c in compras:
    c_id, grp, desc, titular, tot_parc, val_parc, val_orig, status = c
    tot_original += val_orig
    
    # Busca transações ligadas a esse grupo no banco
    cur.execute("""
        SELECT id, data, descricao, valor, pago, numero_parcela
        FROM transacoes
        WHERE grupo_parcelamento = ? OR descricao LIKE ?
        ORDER BY data ASC
    """, (grp, f"%{desc[:15]}%"))
    trans = cur.fetchall()
    
    qtd_registradas = len(trans)
    pagas = [t for t in trans if t[4] == 1]
    pendentes = [t for t in trans if t[4] == 0 or t[4] is None]
    
    soma_pago = sum(t[3] for t in pagas)
    soma_pendente = sum(t[3] for t in pendentes)
    tot_pago_registrado += soma_pago
    tot_devido += soma_pendente
    
    print(f"\n[Compra ID {c_id}] {desc}")
    print(f"  • Grupo: {grp} | Titular: {titular} | Status: {status}")
    print(f"  • Total Original da Operação: R$ {val_orig:.2f} ({tot_parc} parcelas de R$ {val_parc:.2f})")
    print(f"  • Parcelas Registradas no Banco: {qtd_registradas}")
    for t in trans:
        st_p = "Paga (1)" if t[4] == 1 else "Pendente (0)"
        print(f"      - Transação ID {t[0]} ({t[1]}): {t[2]} -> R$ {t[3]:.2f} [{st_p}]")
    print(f"  • Parcelas Pagas no Banco: {len(pagas)} (Soma: R$ {soma_pago:.2f})")
    print(f"  • Parcelas Pendentes no Banco: {len(pendentes)} (Soma: R$ {soma_pendente:.2f})")
    print(f"  • Valor Efetivamente Devido em Aberto: R$ {soma_pendente:.2f}")

print("\n" + "="*50)
print(f"TOTAL ORIGINAL RECONSTRUÍDO DAS 6 OPERAÇÕES: R$ {tot_original:.2f}")
print(f"TOTAL DE PARCELAS REGISTRADAS NO BANCO (PAGAS): R$ {tot_pago_registrado:.2f}")
print(f"TOTAL DE PARCELAS REGISTRADAS NO BANCO (PENDENTES/EM ABERTO): R$ {tot_devido:.2f}")
print(f"TOTAL GERAL DE TODAS AS PARCELAS NO BANCO: R$ {tot_pago_registrado + tot_devido:.2f}")

conn.close()
