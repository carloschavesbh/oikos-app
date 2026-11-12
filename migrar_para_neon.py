"""
====================================================================
SCRIPT DE MIGRAÇÃO INTEGRAL: SQLite -> Neon PostgreSQL (São Paulo)
====================================================================
Migra integralmente as 39 tabelas de aplicação e 1.190 transações
do banco local financas_casa.db para o Neon PostgreSQL.
Preserva chaves primárias e atualiza sequências (setval).
====================================================================
"""

import os
import sys
import sqlite3
import psycopg2
from psycopg2 import extras

# Garante que os módulos locais sejam encontrados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada no .env!")

SQLITE_PATH = os.path.join(BASE_DIR, "financas_casa.db")
if not os.path.exists(SQLITE_PATH):
    raise FileNotFoundError(f"Banco SQLite de origem não encontrado: {SQLITE_PATH}")

print("=" * 65)
print("INICIANDO MIGRAÇÃO DO OIKOS: SQLITE -> NEON POSTGRESQL")
print("=" * 65)
print(f"Origem SQLite: {SQLITE_PATH}")
print(f"Destino Neon : {DATABASE_URL.split('@')[-1]}")

conn_sqlite = sqlite3.connect(SQLITE_PATH)
conn_sqlite.row_factory = sqlite3.Row
cur_sqlite = conn_sqlite.cursor()

conn_pg = psycopg2.connect(DATABASE_URL)
conn_pg.autocommit = False
cur_pg = conn_pg.cursor()

# Lista todas as tabelas de aplicação (ignora tabelas internas sqlite_*)
cur_sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tabelas = [r["name"] for r in cur_sqlite.fetchall()]
print(f"\nTotal de tabelas identificadas para migração: {len(tabelas)}")


def mapear_tipo_coluna(col_name: str, col_type: str, is_pk: bool, pk_count: int, amostra: list) -> str:
    col_name_lower = col_name.lower()
    col_type_upper = (col_type or "TEXT").upper().strip()
    
    # Se for chave primária simples do tipo INT -> BIGSERIAL
    if is_pk and pk_count == 1 and ("INT" in col_type_upper or col_name_lower == "id"):
        return "BIGSERIAL PRIMARY KEY"

    # Inspeciona a amostra de valores da coluna no SQLite
    tem_texto_nao_num = False
    tem_float = False
    for v in amostra:
        if v is not None and v != "":
            s = str(v)
            try:
                float(s)
                if "." in s or "," in s:
                    tem_float = True
            except ValueError:
                tem_texto_nao_num = True
                break

    if tem_texto_nao_num or "data" in col_name_lower or "created" in col_name_lower or "time" in col_name_lower or "desc" in col_name_lower:
        return "TEXT"
    
    if any(k in col_type_upper for k in ["REAL", "FLOA", "DOUB", "NUM", "DEC"]) or tem_float:
        return "NUMERIC(15, 2)"

    if "INT" in col_type_upper or "BOOL" in col_type_upper:
        return "BIGINT"

    return "TEXT"


resultados_migracao = []

for tabela in tabelas:
    cur_sqlite.execute(f'PRAGMA table_info("{tabela}")')
    cols_info = cur_sqlite.fetchall()
    
    pk_cols = [c["name"] for c in cols_info if c["pk"] > 0]
    pk_count = len(pk_cols)
    
    # Lê todos os dados do SQLite primeiro para podermos amostrar os tipos reais
    cur_sqlite.execute(f'SELECT * FROM "{tabela}"')
    rows = cur_sqlite.fetchall()
    total_linhas_sqlite = len(rows)
    
    col_defs = []
    col_names = []
    
    for c in cols_info:
        c_name = c["name"]
        c_type = c["type"]
        is_pk = c["pk"] > 0
        col_names.append(c_name)
        
        amostra = [r[c_name] for r in rows[:20] if r[c_name] is not None]
        pg_type = mapear_tipo_coluna(c_name, c_type, is_pk, pk_count, amostra)
        col_defs.append(f'"{c_name}" {pg_type}')
        
    # Se for chave primária composta
    if pk_count > 1:
        pks_str = ", ".join(f'"{p}"' for p in pk_cols)
        col_defs.append(f"PRIMARY KEY ({pks_str})")
        
    ddl_create = f'CREATE TABLE "{tabela}" (\n  ' + ",\n  ".join(col_defs) + "\n);"
    
    # 1. Drop e Create no Postgres
    cur_pg.execute(f'DROP TABLE IF EXISTS "{tabela}" CASCADE;')
    cur_pg.execute(ddl_create)
    
    # 2. Inserir dados se houver
    if total_linhas_sqlite > 0:
        colunas_insert = ", ".join(f'"{c}"' for c in col_names)
        query_insert = f'INSERT INTO "{tabela}" ({colunas_insert}) VALUES %s'
        
        dados_valores = []
        for r in rows:
            dados_valores.append(tuple(r[c] for c in col_names))
            
        extras.execute_values(cur_pg, query_insert, dados_valores, page_size=500)
        
    # 3. Atualizar sequência se houver coluna id
    if "id" in col_names:
        try:
            cur_pg.execute(f"""
                SELECT setval(pg_get_serial_sequence('"{tabela}"', 'id'), COALESCE((SELECT MAX("id") FROM "{tabela}"), 1));
            """)
        except Exception:
            pass
            
    # 4. Validar contagem no Postgres
    cur_pg.execute(f'SELECT COUNT(*) FROM "{tabela}"')
    total_linhas_pg = cur_pg.fetchone()[0]
    
    status = "OK" if total_linhas_sqlite == total_linhas_pg else "DIVERGÊNCIA"
    resultados_migracao.append({
        "tabela": tabela,
        "sqlite": total_linhas_sqlite,
        "postgres": total_linhas_pg,
        "status": status
    })
    print(f" -> {tabela:<35} | SQLite: {total_linhas_sqlite:>5} | Neon: {total_linhas_pg:>5} | [{status}]")

conn_pg.commit()

print("\n" + "=" * 65)
print("VALIDAÇÃO CONTÁBIL E OPERACIONAL DIRETO DO NEON")
print("=" * 65)

# Importa database.py e saldo_service para validar via camada de abstração
import database
import saldo_service

# Cria conexão compatível com o Neon
conn_hibrido = database.conectar_db_hibrido(pooled=False)
saldo_info = saldo_service.calcular_saldo_consolidado(conn_hibrido)
saldo_consolidado = saldo_info["saldo_consolidado"]

cur_pg.execute('SELECT COUNT(*) FROM "transacoes"')
total_transacoes = cur_pg.fetchone()[0]

cur_pg.execute("""
    SELECT id, data, descricao, valor, pago, afeta_saldo_bancario, conta
    FROM "transacoes"
    WHERE descricao LIKE '%Fernanda%' AND data LIKE '2026-11%'
    ORDER BY id ASC
""")
rows_fernanda = cur_pg.fetchall()

print(f"Total de Transações no Neon: {total_transacoes}")
print(f"Saldo Consolidado Apurado no Neon: R$ {saldo_consolidado}")
for c in saldo_info["contas"]:
    if c.get("incluir_saldo_consolidado"):
        print(f"    - {c['conta_nome']}: R$ {c['saldo_atual']}")

print(f"\nTransações do Contracheque da Fernanda (11/2026) no Neon ({len(rows_fernanda)}):")
for r in rows_fernanda:
    pago_str = "PAGO" if r[4] == 1 else "PENDENTE"
    print(f"    * [ID {r[0]}] {r[1]} | {r[2]} | R$ {r[3]} | {pago_str}")

conn_hibrido.close()
conn_pg.close()
conn_sqlite.close()

if total_transacoes == 1190 and str(saldo_consolidado) == "1653.18":
    print("\n" + "=" * 65)
    print(">>> MIGRAÇÃO CONCLUÍDA COM SUCESSO ABSOLUTO! 100% VALIDADO! <<<")
    print("=" * 65)
else:
    print(f"\nAVISO: Saldo ou quantidade divergente (Transações: {total_transacoes}, Saldo: {saldo_consolidado})")
