with open('web_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "def coletar_dados_dashboard(" in line:
        print(f"coletar_dados_dashboard na linha {idx+1}")
        for j in range(idx, min(idx + 120, len(lines))):
            if "resumo_patrimonio" in lines[j]:
                print(''.join(lines[j-10:j+25]))
                break
        break
