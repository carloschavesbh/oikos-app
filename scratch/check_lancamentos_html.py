from pathlib import Path
import re

content = Path('Organizze/Organizze _ Lançamentos.html').read_text(encoding='utf-8', errors='ignore')
matches = [m.start() for m in re.finditer(r'item in transactions\.data\.transactions', content)]
print(f"Occurrences of 'item in transactions.data.transactions': {len(matches)}")
for idx in matches[:5]:
    snippet = content[max(0, idx-100):min(len(content), idx+300)]
    print("-" * 50)
    print(snippet)
