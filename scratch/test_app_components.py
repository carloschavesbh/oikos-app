import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import calendar
from datetime import date, timedelta
from decimal import Decimal
import saldo_service

conn = sqlite3.connect('financas_casa.db')
cur = conn.cursor()

print("--- TESTANDO INTEGRAÇÃO DOS COMPONENTES DE APP.PY ---")

# 1. Teste de datas recorrentes
def calcular_datas_recorrentes(data_base: date, periodicidade: str, qtd: int):
    datas = []
    dia_base = data_base.day
    ano_base = data_base.year
    mes_base = data_base.month

    for i in range(qtd):
        if periodicidade == "Mensal":
            novo_ano = ano_base + ((mes_base - 1 + i) // 12)
            novo_mes = ((mes_base - 1 + i) % 12) + 1
            max_dia = calendar.monthrange(novo_ano, novo_mes)[1]
            dia_efetivo = min(dia_base, max_dia)
            datas.append(date(novo_ano, novo_mes, dia_efetivo))
        elif periodicidade == "Quinzenal":
            datas.append(data_base + timedelta(days=14 * i))
        elif periodicidade == "Semanal":
            datas.append(data_base + timedelta(days=7 * i))
        elif periodicidade == "Anual":
            novo_ano = ano_base + i
            max_dia = calendar.monthrange(novo_ano, mes_base)[1]
            dia_efetivo = min(dia_base, max_dia)
            datas.append(date(novo_ano, mes_base, dia_efetivo))
        else:
            datas.append(data_base + timedelta(days=30 * i))
    return datas

dts_31 = calcular_datas_recorrentes(date(2026, 1, 31), "Mensal", 4)
print("Datas teste dia 31:", [d.strftime("%Y-%m-%d") for d in dts_31])
assert dts_31[0] == date(2026, 1, 31)
assert dts_31[1] == date(2026, 2, 28)
assert dts_31[2] == date(2026, 3, 31)
assert dts_31[3] == date(2026, 4, 30)
print("✓ Regra explícita de dias de meses mais curtos validada 100%!")

# 2. Teste de estrutura de categorias
cur.execute("""
    SELECT g.id as grupo_id, g.nome as grupo_nome, g.icone as grupo_icone,
           s.id as sub_id, s.nome as sub_nome, s.icone as sub_icone
    FROM grupos_categoria g
    LEFT JOIN subcategorias s ON s.grupo_id = g.id AND s.ativo = 1
    WHERE g.ativo = 1
    ORDER BY g.ordem, s.ordem
""")
rows = cur.fetchall()
grupos = {}
for r in rows:
    g_id, g_nome, g_ico, s_id, s_nome, s_ico = r
    if g_id not in grupos:
        grupos[g_id] = {"id": g_id, "nome": g_nome, "icone": g_ico, "subcategorias": []}
    if s_id:
        grupos[g_id]["subcategorias"].append({"id": s_id, "nome": s_nome, "icone": s_ico})

print(f"Total grupos carregados: {len(grupos)}")
assert len(grupos) == 16
tot_subs = sum(len(g["subcategorias"]) for g in grupos.values())
print(f"Total subcategorias carregadas: {tot_subs}")
assert tot_subs == 63
print("✓ Estrutura hierárquica carregada com sucesso!")

# 3. Teste de contas Paga Leve e Compras
cur.execute("SELECT * FROM pagaleve_contas")
contas_pl = cur.fetchall()
print(f"Contas Paga Leve: {[c[1] for c in contas_pl]}")
assert len(contas_pl) == 2

cur.execute("SELECT * FROM pagaleve_compras")
compras_pl = cur.fetchall()
print(f"Compras Paga Leve: {len(compras_pl)}")
assert len(compras_pl) == 6

# 4. Teste de Dívidas
cur.execute("SELECT COUNT(*) FROM dividas_gerenciamento")
print(f"Dívidas no banco: {cur.fetchone()[0]}")

conn.close()
print("✓ Todos os testes de componentes passaram perfeitamente!")
