import re
import sys
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

with open('Organizze/Organizze _ Categorias.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# Let's search for category names and subcategory names in the HTML
# In Organizze, categories typically have data attributes or specific classes
# Let's find all text inside category list elements
lines = html.splitlines()
print(f"Total lines: {len(lines)}")

# Let's search for patterns like class="category..." or similar
for i, line in enumerate(lines):
    if any(k in line.lower() for k in ['category', 'subcategor', 'categoria', 'habitacao', 'habitação', 'alimentação', 'chaves transportes']):
        # print line preview
        clean = re.sub(r'<[^>]+>', ' ', line).strip()
        if clean and len(clean) < 150:
            print(f"L{i+1}: {clean}")
