import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 1900 <= idx <= 2300 and ('editar' in line.lower() or 'turno' in line.lower()):
            print(f"{idx}: {line.strip()}")
