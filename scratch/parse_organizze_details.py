import json
from pathlib import Path
from html.parser import HTMLParser
import re

print("=== 1. ANALISANDO CONTEXT_SOURCE ===")
with open('scratch/organizze_context_source.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Keys:", list(data.keys()))
print("\nContas:")
for acc in data.get('accounts', []):
    print(f"  ID: {acc.get('id')} | Nome: {acc.get('name')} | Arquivada: {acc.get('archived')} | Tipo: {acc.get('type') or acc.get('account_type')}")

print("\nCartões de Crédito:")
for cc in data.get('credit_cards', []):
    print(f"  ID: {cc.get('id')} | Nome: {cc.get('name')} | Limite: {cc.get('limit')} | Fechamento: {cc.get('closing_day')} | Vencimento: {cc.get('due_day')} | Arquivado: {cc.get('archived')} | Instituição: {cc.get('institution')}")

print("\nTags:")
print(data.get('tags', []))

# Regex parser para encontrar linhas com ng-repeat ou blocos de transações
def extract_ng_repeats(filepath):
    content = Path(filepath).read_text(encoding='utf-8', errors='ignore')
    # Buscar padrões ng-repeat="(.*?)"
    repeats = re.findall(r'ng-repeat="([^"]+)"', content)
    print(f"\nArquivo {Path(filepath).name}:")
    print(f"  Total ng-repeats encontrados: {len(repeats)}")
    unique_repeats = set(repeats)
    for r in sorted(unique_repeats):
        print(f"    - {r}")

extract_ng_repeats('Organizze/Organizze _ Visão geral.html')
extract_ng_repeats('Organizze/Organizze _ Lançamentos.html')
extract_ng_repeats('Organizze/Organizze _ Cartões de Crédito.html')
extract_ng_repeats('Organizze/Organizze _ Contas.html')
extract_ng_repeats('Organizze/Organizze _ Relatórios.html')
extract_ng_repeats('Organizze/Organizze _ Limite de gastos.html')
extract_ng_repeats('Organizze/Organizze _ Categorias.html')
