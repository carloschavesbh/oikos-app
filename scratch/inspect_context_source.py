import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

with open("Organizze/Organizze _ Contas.html", "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

m = re.search(r'ContextSource\s*=\s*(\{.*?\});', html, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    print("=" * 80)
    print("DADOS COMPLETOS EXTRAÍDOS DE ContextSource")
    print("=" * 80)
    
    print("\n1. CONTAS BANCÁRIAS (accounts):", len(data.get("accounts", [])))
    for acc in data.get("accounts", []):
        print(f"   • ID: {acc.get('id')} | Nome: '{acc.get('name')}' | Instituição: {acc.get('institution_id')} | Arquivada: {acc.get('archived')} | Oculta: {acc.get('hide_balance')}")
        
    print("\n2. CARTÕES DE CRÉDITO (credit_cards):", len(data.get("credit_cards", [])))
    for cc in data.get("credit_cards", []):
        print(f"   • ID: {cc.get('id')} | Nome: '{cc.get('name')}' | Instituição: {cc.get('institution_id')} | Arquivado: {cc.get('archived')}")
        
    print("\n3. TAGS:", len(data.get("tags", [])))
    for t in data.get("tags", []):
        print(f"   • Tag: '{t.get('name')}' (ID: {t.get('id')})")
        
    print("\n4. CATEGORIAS (categories):", len(data.get("categories", [])))
    cats = data.get("categories", [])
    raizes = [c for c in cats if c.get("is_root") == "true" or c.get("is_root") is True or c.get("parent_id") is None]
    filhas = [c for c in cats if c not in raizes]
    print(f"   Total categorias: {len(cats)} ({len(raizes)} raízes / {len(filhas)} subcategorias)")
    for r in raizes[:15]:
        print(f"   📂 [{r.get('kind')}] {r.get('name')} (ID: {r.get('id')})")
        
    # Salva json limpo para consultas
    with open("scratch/organizze_context_source.json", "w", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
    print("\n✓ ContextSource completo salvo em 'scratch/organizze_context_source.json'")
else:
    print("ContextSource não encontrado.")
