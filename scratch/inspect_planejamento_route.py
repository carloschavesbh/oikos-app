import re

with open('web_app.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('/planejamento')
while idx != -1:
    line_start = text.rfind('\n', 0, idx)
    line_end = text.find('\n', idx)
    print("Encontrado:", text[line_start:line_end].strip())
    # print context if it is a route
    if '@app.' in text[line_start-50:line_end]:
        print("--- Contexto ---")
        print(text[line_start-50:line_start+800])
        print("----------------")
    idx = text.find('/planejamento', idx + 1)

