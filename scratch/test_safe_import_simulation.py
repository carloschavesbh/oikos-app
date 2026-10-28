import sqlite3
import json
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

test_db = 'scratch/financas_casa_teste_migracao.db'
conn = sqlite3.connect(test_db)
cursor = conn.cursor()

# 1. Carregar registros classificados
with open('scratch/classified_all_113.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

print("=== SIMULAÇÃO DE CARGA SEGURA NO BANCO DE TESTE ===")
print(f"Total registros para análise: {len(items)}")

# Mapear subcategorias e grupos para garantir categorização hierárquica
cursor.execute("SELECT id, nome, grupo_id FROM subcategorias")
subcats = cursor.fetchall()
cursor.execute("SELECT id, nome FROM grupos_categoria")
grupos = cursor.fetchall()

# Estatísticas da simulação
stats = {
    'ja_existentes_preservados': 0,
    'historico_sem_efeito_bancario': 0,
    'incompletos_isolados_revisao': 0,
    'novos_futuros_importaveis': 0
}

novos_para_inserir = []

for i in items:
    cls = i['classificacao']
    
    if cls == "Já existente no aplicativo":
        stats['ja_existentes_preservados'] += 1
        # Não insere nada! Preserva o registro oficial intacto.
    elif cls == "Histórico anterior ao marco de conciliação":
        stats['historico_sem_efeito_bancario'] += 1
        # Pode ser gravado apenas para memória histórica / auditoria com afeta_saldo_bancario = 0
    elif cls == "Incompleto, exigindo confirmação":
        stats['incompletos_isolados_revisao'] += 1
        # Não insere automaticamente no fluxo de caixa sem confirmação do usuário
    else:
        # Novo e importável (Faturas futuras, Dívidas futuras, Despesas fixas futuras, Receitas futuras)
        stats['novos_futuros_importaveis'] += 1
        novos_para_inserir.append(i)

print("\nResultado da Análise da Carga:")
for k, v in stats.items():
    print(f"  - {k}: {v}")

print(f"\nTotal de registros futuros e novos prontos para o fluxo de caixa: {len(novos_para_inserir)}")
print("\nAmostra dos novos registros futuros a serem programados:")
for n in novos_para_inserir[:10]:
    print(f"  [{n['data']}] R$ {n['valor']:>9.2f} | {n['descricao']} ({n['classificacao']})")

conn.close()
