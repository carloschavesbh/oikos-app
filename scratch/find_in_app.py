import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

term = sys.argv[1] if len(sys.argv) > 1 else 'def '
with open('app.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if term.lower() in line.lower():
            print(f"{idx}: {line.strip()[:100]}")
