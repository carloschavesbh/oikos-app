with open('web_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '@app.get("/"' in line or "@app.get('/'" in line:
        print(f"Rota / na linha {idx+1}")
        for j in range(idx, min(idx + 50, len(lines))):
            if "return templates.TemplateResponse" in lines[j]:
                print(f"Retorno na linha {j+1}")
                print(''.join(lines[j-15:j+20]))
                break
        break

