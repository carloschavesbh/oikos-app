import re
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

with open('Organizze/Organizze _ Categorias.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Vamos extrair usando regex estruturado
# Cada categoria começa com <div class="category-cell"
category_blocks = re.findall(r'<div class="category-cell"[^>]*>(.*?)</ul></div>(.*?)(?=<div class="category-cell"|<!-- end ngRepeat: item in categoriesList|$)', html, re.DOTALL)

tree = []

# Vamos iterar por padrões de categorias principais
cat_pattern = re.compile(r'<div class="category-cell"[^>]*>.*?class="category-name[^"]*"[^>]*>(?:<zze-category-icon.*?</zze-category-icon>)?\s*(.*?)\s*</a>(.*?)</div>', re.DOTALL)
matches = list(re.finditer(r'<div class="category-cell"[^>]*>', html))

for i, m in enumerate(matches):
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(html)
    chunk = html[start:end]
    
    # Extrai nome da categoria
    cat_match = re.search(r'class="category-name[^"]*"[^>]*>(?:<zze-category-icon.*?</zze-category-icon>)?\s*(.*?)\s*</a>', chunk, re.DOTALL)
    if cat_match:
        cat_name = re.sub(r'<[^>]+>', '', cat_match.group(1)).strip()
        # Limpar emojis ou ícones residuais se necessário, mas manter
        cat_name = re.sub(r'\s+', ' ', cat_name).strip()
    else:
        continue
        
    # Extrai subcategorias
    subcats = []
    sub_matches = re.findall(r'<span class="ng-binding">\s*(.*?)\s*</span>', chunk)
    for sm in sub_matches:
        s_clean = re.sub(r'<[^>]+>', '', sm).strip()
        s_clean = re.sub(r'\s+', ' ', s_clean).strip()
        if s_clean and s_clean not in subcats and s_clean != cat_name:
            subcats.append(s_clean)
            
    tree.append({
        "categoria": cat_name,
        "subcategorias": subcats
    })

print(f"Total de categorias principais extraídas: {len(tree)}")
for item in tree:
    print(f"\n📂 GRUPO/CATEGORIA: {item['categoria']} ({len(item['subcategorias'])} subcategorias)")
    for sc in item['subcategorias']:
        print(f"   └── {sc}")

with open('scratch/organizze_tree.json', 'w', encoding='utf-8') as out_f:
    json.dump(tree, out_f, ensure_ascii=False, indent=2)
print("\nSalvo em scratch/organizze_tree.json")
