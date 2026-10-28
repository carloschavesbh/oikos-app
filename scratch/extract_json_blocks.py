import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

print("=" * 80)
print("EXTRAÇÃO DOS BLOCOS JSON EMBUTIDOS NOS ARQUIVOS ORGANIZZE")
print("=" * 80)

files = [
    "Organizze _ Contas.html",
    "Organizze _ Cartões de Crédito.html",
    "Organizze _ Lançamentos.html",
    "Organizze _ Visão geral.html",
    "Organizze _ Categorias.html",
    "Organizze _ Limite de gastos.html",
    "Organizze _ Relatórios.html"
]

for fname in files:
    fpath = os.path.join("Organizze", fname)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    
    # Procura blocos JSON atribuídos a variáveis JS ou dentro de atributos
    print(f"\n--- Analisando {fname} ---")
    
    # Procura por "accounts": [ ... ] ou "credit_cards": [ ... ]
    matches = re.findall(r'(\{"id":\d+,"uuid":"[a-f0-9]+".*?\})', html)
    print(f"Objetos com id e uuid: {len(matches)}")
    
    # Procura atribuição de arrays/dicts grandes
    # Ex: gon.something = {...}; ou window.something = {...};
    assigns = re.findall(r'(?:gon|window|\$scope)\.([a-zA-Z0-9_]+)\s*=\s*(\{.*?\}|\[.*?\]);', html)
    print(f"Atribuições JS encontradas: {len(assigns)}")
    for a in assigns:
        print(f"   Variable: {a[0]} (tamanho: {len(a[1])} chars)")
        try:
            data = json.loads(a[1])
            if isinstance(data, dict):
                print(f"      Keys: {list(data.keys())[:10]}")
            elif isinstance(data, list):
                print(f"      List items: {len(data)}")
        except Exception:
            pass
            
    # Procura data-json ou data-initial
    data_attrs = re.findall(r'data-([a-zA-Z0-9_-]+)=["\'](\{.*?\}|\[.*?\])["\']', html)
    print(f"Atributos data-*: {len(data_attrs)}")
    for da in data_attrs:
        print(f"   data-{da[0]}: {len(da[1])} chars")

