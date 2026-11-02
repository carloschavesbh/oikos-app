with open('planejamento_anual_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = []
for l in lines:
    if l.startswith('conn.commit()'):
        fixed.append('    conn.commit()\n')
    else:
        fixed.append(l)

with open('planejamento_anual_service.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print("SUCESSO: Indentação corrigida!")
