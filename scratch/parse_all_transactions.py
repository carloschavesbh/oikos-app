from pathlib import Path
import re

content = Path('Organizze/Organizze _ Lançamentos.html').read_text(encoding='utf-8', errors='ignore')

# Extrair cada bloco <li ... id="transaction-(\d+)" ... > ... </li>
# Como os li podem ter tags aninhadas, vamos buscar de id="transaction-(\d+)" até o próximo id="transaction- ou end ngRepeat
pattern = r'<li[^>]*id="transaction-(\d+)"[^>]*>(.*?)(?=(?:<li[^>]*id="transaction-)|(?:</ul>)|(?:<!-- end ngRepeat: item in transactions\.data\.transactions))'
matches = re.findall(pattern, content, re.DOTALL)

print(f"Total transações encontradas em Lançamentos.html: {len(matches)}")
transactions = []
for tx_id, block in matches:
    clean_text = re.sub(r'<[^>]+>', ' | ', block)
    clean_text = ' '.join(clean_text.split())
    clean_text = re.sub(r'(\s*\|\s*)+', ' | ', clean_text)
    
    # Vamos tentar extrair campos específicos se possível
    transactions.append({
        'id': tx_id,
        'summary': clean_text
    })

print(f"\nPrimeiras 10 transações extraídas:")
for t in transactions[:15]:
    print(f"ID {t['id']}: {t['summary'][:160]}")

print(f"\nÚltimas 5 transações extraídas:")
for t in transactions[-5:]:
    print(f"ID {t['id']}: {t['summary'][:160]}")
