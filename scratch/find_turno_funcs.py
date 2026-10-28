import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 'def modal_novo_turno' in line or 'def salvar_turno' in line or 'def excluir_turno' in line or 'INSERT INTO turnos' in line or 'UPDATE turnos' in line:
            print(f"{idx}: {line.strip()}")
