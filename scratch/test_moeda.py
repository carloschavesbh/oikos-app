import re

def parse_moeda_centavos(val_str) -> float:
    if val_str is None:
        return 0.0
    if isinstance(val_str, (int, float)):
        return round(float(val_str), 2)
    s = str(val_str).strip()
    if not s:
        return 0.0
    digits = re.sub(r"\D", "", s)
    if not digits:
        return 0.0
    return round(int(digits) / 100.0, 2)

def formatar_moeda_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

testes = [
    ("5", 0.05),
    ("500", 5.00),
    ("1170", 11.70),
    ("5505", 55.05),
    ("R$ 55,05", 55.05),
    ("R$ 1.428,82", 1428.82),
    ("0", 0.0),
    ("", 0.0),
    (10.5, 10.5),
    ("9048", 90.48),
    ("R$ 90,48", 90.48),
]

for entrada, esperado in testes:
    res = parse_moeda_centavos(entrada)
    assert res == esperado, f"Erro: {entrada} -> {res} != {esperado}"
    print(f"OK: {repr(entrada)} -> {res} -> {formatar_moeda_br(res)}")

print("\nTodos os testes passaram com sucesso!")
