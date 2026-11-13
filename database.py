"""
====================================================================
CAMADA DE CONEXÃO E PERSISTÊNCIA HÍBRIDA (database.py)
====================================================================
Suporta transparentemente SQLite local e PostgreSQL na nuvem (Neon Cloud).
- Carregamento automático via python-dotenv (.env)
- Wrapper compatível com sqlite3.Row (acesso por chave row['campo'] e índice row[0])
- Conversão de placeholders SQL (? -> %s)
- Emulação nativa de lastrowid para PostgreSQL
- Fallback seguro para SQLite local caso DATABASE_URL não esteja definida
====================================================================
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Carrega variáveis do arquivo .env se presente
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL_POOLED = os.getenv("DATABASE_URL_POOLED") or DATABASE_URL

# Determina o motor ativo
DB_ENGINE = "postgresql" if (DATABASE_URL and DATABASE_URL.startswith("postgres")) else "sqlite"


class CompatRow:
    """Emulador de sqlite3.Row para PostgreSQL.
    Permite acesso tanto por nome da coluna (row['id']) quanto por índice numérico (row[0]),
    além de suportar dict(row), row.keys(), row.get() e desempacotamento de tuplas.
    """
    __slots__ = ("_keys", "_values", "_map")

    def __init__(self, description: Any, values: Any):
        if description:
            self._keys = [d[0] for d in description]
        else:
            self._keys = []
        self._values = list(values)
        self._map = {k: v for k, v in zip(self._keys, self._values)}

    def __getitem__(self, key: Union[str, int]) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._map.get(key, default)

    def keys(self) -> List[str]:
        return self._keys

    def values(self) -> List[Any]:
        return self._values

    def items(self):
        return self._map.items()

    def __iter__(self):
        return iter(self._values)

    def __contains__(self, key: str) -> bool:
        return key in self._map

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"<CompatRow {self._map}>"


def converter_sql_sqlite_para_postgres(query: str, has_params: bool = False) -> str:
    """Converte sintaxe e placeholders do SQLite para PostgreSQL."""
    if not query:
        return query

    # 0. Converte funções específicas do SQLite para PostgreSQL antes de escapar %
    # strftime('%Y-%m', col) -> SUBSTR(col, 1, 7)
    query = re.sub(r"strftime\s*\(\s*['\"]%Y-%m['\"]\s*,\s*([^)]+)\)", r"SUBSTR(\1, 1, 7)", query, flags=re.IGNORECASE)
    query = re.sub(r"strftime\s*\(\s*['\"]%Y['\"]\s*,\s*([^)]+)\)", r"SUBSTR(\1, 1, 4)", query, flags=re.IGNORECASE)
    query = re.sub(r"strftime\s*\(\s*['\"]%m['\"]\s*,\s*([^)]+)\)", r"SUBSTR(\1, 6, 2)", query, flags=re.IGNORECASE)
    query = re.sub(r"strftime\s*\(\s*['\"]%d['\"]\s*,\s*([^)]+)\)", r"SUBSTR(\1, 9, 2)", query, flags=re.IGNORECASE)
    query = re.sub(r"\bIFNULL\s*\(", "COALESCE(", query, flags=re.IGNORECASE)

    # Se a query receber parâmetros no psycopg2, qualquer '%' literal existente no SQL
    # deve ser escapado como '%%' para evitar que o psycopg2 tente interpolá-lo
    if has_params:
        query = query.replace('%', '%%')

    # 1. Substitui ? por %s apenas fora de aspas simples literais
    buffer = []
    dentro_aspas = False
    i = 0
    n = len(query)
    while i < n:
        ch = query[i]
        if ch == "'":
            if dentro_aspas and i + 1 < n and query[i + 1] == "'":
                buffer.append("''")
                i += 2
                continue
            dentro_aspas = not dentro_aspas
            buffer.append(ch)
        elif ch == '?' and not dentro_aspas:
            buffer.append('%s')
        else:
            buffer.append(ch)
        i += 1
    res = "".join(buffer)

    # 2. INSERT OR IGNORE INTO -> INSERT INTO ... ON CONFLICT DO NOTHING
    if re.search(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', res, flags=re.IGNORECASE):
        res = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', res, flags=re.IGNORECASE)
        if 'ON CONFLICT' not in res.upper():
            res = res.rstrip().rstrip(';') + " ON CONFLICT DO NOTHING"

    # 3. AUTOINCREMENT -> SERIAL PRIMARY KEY
    res = re.sub(r'\b(?:INTEGER|INT|BIGINT)\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'BIGSERIAL PRIMARY KEY', res, flags=re.IGNORECASE)
    res = re.sub(r'\bAUTOINCREMENT\b', '', res, flags=re.IGNORECASE)

    # 4. ALTER TABLE ... ADD COLUMN ... -> ADD COLUMN IF NOT EXISTS
    if re.search(r'\bALTER\s+TABLE\s+(\S+)\s+ADD\s+COLUMN\b', res, flags=re.IGNORECASE):
        res = re.sub(r'\bALTER\s+TABLE\s+(\S+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS\b)', r'ALTER TABLE \1 ADD COLUMN IF NOT EXISTS ', res, flags=re.IGNORECASE)

    # 5. Funções de data/hora SQLite
    res = re.sub(r'\bDATETIME\s*\(\s*[\'"]NOW[\'"]\s*\)', 'CURRENT_TIMESTAMP', res, flags=re.IGNORECASE)
    res = re.sub(r'\bDATE\s*\(\s*[\'"]NOW[\'"]\s*\)', 'CURRENT_DATE', res, flags=re.IGNORECASE)

    # 6. Intercepta PRAGMA table_info("tabela")
    m_pragma = re.search(r'PRAGMA\s+table_info\s*\([\'"]?(\w+)[\'"]?\)', res, flags=re.IGNORECASE)
    if m_pragma:
        tbl = m_pragma.group(1).lower()
        res = (
            f"SELECT ordinal_position as cid, column_name as name, data_type as type, "
            f"CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END as notnull, "
            f"column_default as dflt_value, 0 as pk "
            f"FROM information_schema.columns "
            f"WHERE table_name = '{tbl}' ORDER BY ordinal_position"
        )

    return res


class PostgresCursorWrapper:
    """Cursor que encapsula psycopg2.extensions.cursor com suporte a sqlite3.Row, lastrowid e retry em queda de SSL."""
    def __init__(self, raw_cursor: Any, connection: Any, wrapper: Any = None):
        self._cursor = raw_cursor
        self._connection = connection
        self._wrapper = wrapper
        self.lastrowid: Optional[int] = None

    def _executar_com_retry(self, fn_exec):
        import psycopg2
        try:
            return fn_exec()
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as err:
            if self._wrapper is not None and self._wrapper._reconectar():
                self._connection = self._wrapper._conn
                self._cursor = self._connection.cursor()
                return fn_exec()
            raise err

    def execute(self, query: str, params: Any = None) -> "PostgresCursorWrapper":
        has_params = (params is not None and len(params) > 0) if isinstance(params, (tuple, list, dict)) else (params is not None)
        pg_sql = converter_sql_sqlite_para_postgres(query, has_params=has_params)
        self.lastrowid = None

        is_insert = bool(re.match(r'^\s*INSERT\s+INTO\b', pg_sql, flags=re.IGNORECASE))
        has_returning = 'RETURNING' in pg_sql.upper()

        if is_insert and not has_returning:
            # Tenta executar com RETURNING id para preencher lastrowid automaticamente
            sql_with_returning = pg_sql.rstrip().rstrip(';') + " RETURNING id"
            try:
                def _run_insert():
                    self._cursor.execute("SAVEPOINT lastrowid_sp;")
                    if params is not None:
                        self._cursor.execute(sql_with_returning, params)
                    else:
                        self._cursor.execute(sql_with_returning)
                    row = self._cursor.fetchone()
                    if row:
                        self.lastrowid = row[0]
                    self._cursor.execute("RELEASE SAVEPOINT lastrowid_sp;")
                self._executar_com_retry(_run_insert)
                return self
            except Exception:
                # Se falhar (ex: tabela sem coluna id), faz rollback até o savepoint e roda normal
                try:
                    self._cursor.execute("ROLLBACK TO SAVEPOINT lastrowid_sp;")
                    self._cursor.execute("RELEASE SAVEPOINT lastrowid_sp;")
                except Exception:
                    pass

        def _run_normal():
            if params is not None:
                self._cursor.execute(pg_sql, params)
            else:
                self._cursor.execute(pg_sql)

        self._executar_com_retry(_run_normal)
        return self

    def executemany(self, query: str, seq_of_params: Any) -> "PostgresCursorWrapper":
        pg_sql = converter_sql_sqlite_para_postgres(query, has_params=True)
        self._executar_com_retry(lambda: self._cursor.executemany(pg_sql, seq_of_params))
        return self

    def fetchone(self) -> Optional[CompatRow]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return CompatRow(self._cursor.description, row)

    def fetchall(self) -> List[CompatRow]:
        rows = self._cursor.fetchall()
        if not rows:
            return []
        desc = self._cursor.description
        return [CompatRow(desc, r) for r in rows]

    def fetchmany(self, size: int = 1) -> List[CompatRow]:
        rows = self._cursor.fetchmany(size)
        if not rows:
            return []
        desc = self._cursor.description
        return [CompatRow(desc, r) for r in rows]

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self) -> Any:
        return self._cursor.description

    def close(self):
        self._cursor.close()

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                break
            yield row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


import threading

_pg_pool = None
_pg_pool_lock = threading.Lock()
_PG_KEEPALIVE_KWARGS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}


def _obter_pool_postgresql(url: str):
    global _pg_pool
    if _pg_pool is None:
        with _pg_pool_lock:
            if _pg_pool is None:
                import psycopg2.pool
                _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    dsn=url,
                    **_PG_KEEPALIVE_KWARGS
                )
    return _pg_pool


class PostgresConnectionWrapper:
    """Wrapper de conexão psycopg2 compatível com a interface do sqlite3.Connection."""
    def __init__(self, raw_conn: Any, pool: Any = None, dsn_url: Optional[str] = None):
        self._conn = raw_conn
        self._pool = pool
        self._dsn_url = dsn_url
        self._closed = False
        self.row_factory = None  # Apenas para compatibilidade de atribuição
        try:
            self._conn.autocommit = True
        except Exception:
            pass

    def _reconectar(self) -> bool:
        """Descarta conexão morta e abre uma nova conexão limpa."""
        import psycopg2
        url = self._dsn_url or DATABASE_URL_POOLED or DATABASE_URL
        if not url:
            return False
        if self._pool is not None:
            try:
                self._pool.putconn(self._conn, close=True)
            except Exception:
                pass
        else:
            try:
                self._conn.close()
            except Exception:
                pass
        try:
            self._conn = psycopg2.connect(url, **_PG_KEEPALIVE_KWARGS)
            self._conn.autocommit = True
            self._pool = None  # Nova conexão direta fora do pool antigo
            return True
        except Exception:
            return False

    def cursor(self) -> PostgresCursorWrapper:
        return PostgresCursorWrapper(self._conn.cursor(), self._conn, wrapper=self)

    def execute(self, query: str, params: Any = None) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def executemany(self, query: str, seq_of_params: Any) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.executemany(query, seq_of_params)
        return cur

    def commit(self):
        try:
            if not self._conn.autocommit:
                self._conn.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            if not self._conn.autocommit:
                self._conn.rollback()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._pool is not None:
            try:
                if self._conn.closed:
                    self._pool.putconn(self._conn, close=True)
                else:
                    self._pool.putconn(self._conn)
            except Exception:
                try:
                    self._pool.putconn(self._conn, close=True)
                except Exception:
                    pass
        else:
            try:
                self._conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()


def conectar_db_hibrido(pooled: bool = True, db_path_sqlite: Optional[str] = None) -> Any:
    """Retorna uma conexão ativa (PostgreSQL com keepalive/ping, ou SQLite como fallback)."""
    if DB_ENGINE == "postgresql":
        import psycopg2
        url = DATABASE_URL_POOLED if pooled else DATABASE_URL
        if pooled:
            try:
                pool = _obter_pool_postgresql(url)
                raw = pool.getconn()
                try:
                    if raw.closed:
                        raise psycopg2.InterfaceError("Conexão do pool estava fechada")
                    with raw.cursor() as cur_ping:
                        cur_ping.execute("SELECT 1")
                    return PostgresConnectionWrapper(raw, pool=pool, dsn_url=url)
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    try:
                        pool.putconn(raw, close=True)
                    except Exception:
                        pass
                    raw_nova = psycopg2.connect(url, **_PG_KEEPALIVE_KWARGS)
                    return PostgresConnectionWrapper(raw_nova, pool=None, dsn_url=url)
            except Exception:
                pass
        raw = psycopg2.connect(url, **_PG_KEEPALIVE_KWARGS)
        return PostgresConnectionWrapper(raw, pool=None, dsn_url=url)
    else:
        import sqlite3
        path = db_path_sqlite or "financas_casa.db"
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
