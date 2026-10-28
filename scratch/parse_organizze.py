import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Organizze/Organizze _ Categorias.html', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

print("Tamanho do arquivo HTML:", len(content))

# Procurar padrões de categorias no Organizze
# No Organizze, categorias e subcategorias geralmente estão em listas ou tabelas com classes específicas
# Vamos procurar blocos com "category" ou "subcategory" ou data-name
grupos_alvo = [
    'Habitação', 'Alimentação', 'Saúde', 'Educação', 'Dívidas', 'Lazer', 
    'Eventual', 'Chaves Transportes', 'Transporte Pessoal', 'Pedro', 
    'Carlos', 'Fernanda', 'Dízimos', 'Investimentos'
]

print("\n--- BUSCA DOS GRUPOS DO USUÁRIO NO ORGANIZZE HTML ---")
for g in grupos_alvo:
    # Achar todas as ocorrências
    for m in re.finditer(re.escape(g), content, re.IGNORECASE):
        start = max(0, m.start() - 150)
        end = min(len(content), m.end() + 250)
        snippet = content[start:end]
        snippet_clean = re.sub(r'<[^>]+>', ' ', snippet)
        snippet_clean = re.sub(r'\s+', ' ', snippet_clean).strip()
        print(f"[{g}] -> {snippet_clean[:180]}")
        break

# Vamos também verificar o arquivo de lançamentos do Organizze
print("\n--- ANALISANDO ORGANIZZE LANCAMENTOS ---")
try:
    with open('Organizze/Organizze _ Lançamentos.html', 'r', encoding='utf-8', errors='ignore') as f2:
        content_lanc = f2.read()
    print("Tamanho Lançamentos HTML:", len(content_lanc))
    # Buscar pares de Categoria / Subcategoria em Lançamentos
    # No Organizze, as vezes aparece como "Habitação > Água" ou similar
    cat_pairs = set(re.findall(r'([A-Za-zÀ-ÖØ-öø-ÿ\s—–-]+)\s*[>›»/]\s*([A-Za-zÀ-ÖØ-öø-ÿ\s—–-]+)', content_lanc))
    print(f"Pares categoria > subcategoria encontrados: {len(cat_pairs)}")
    for cp in sorted(list(cat_pairs))[:40]:
        print(f"  {cp[0].strip()} > {cp[1].strip()}")
except Exception as e:
    print("Erro ao ler lançamentos:", e)
