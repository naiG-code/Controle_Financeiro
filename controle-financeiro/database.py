"""Acesso ao banco de dados SQLite (local) ou Turso/libSQL (remoto) e cálculos financeiros."""
import calendar
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "financas.db"

CATEGORIAS_INICIAIS = [
    ("Alimentação", "despesa"),
    ("Transporte", "despesa"),
    ("Moradia", "despesa"),
    ("Saúde", "despesa"),
    ("Lazer", "despesa"),
    ("Educação", "despesa"),
    ("Outros", "despesa"),
    ("Salário", "receita"),
    ("Freelance", "receita"),
    ("Investimentos", "receita"),
    ("Outros", "receita"),
]


class _TursoCursor:
    def __init__(self, result_set):
        self._rows = list(result_set.rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _TursoConnection:
    """Conexão remota (Turso/libSQL) com uma API parecida com a do sqlite3."""

    def __init__(self, url, auth_token):
        import libsql_client

        url_http = url.replace("libsql://", "https://")
        self._client = libsql_client.create_client_sync(url=url_http, auth_token=auth_token)

    def execute(self, sql, params=()):
        resultado = self._client.execute(sql, list(params))
        return _TursoCursor(resultado)

    def executescript(self, script):
        for comando in script.split(";"):
            comando = comando.strip()
            if comando:
                self._client.execute(comando)

    def commit(self):
        pass  # cada comando já é gravado imediatamente via HTTP


def conectar(db_path=DB_PATH, turso_url=None, turso_token=None):
    if turso_url and turso_token:
        conn = _TursoConnection(turso_url, turso_token)
    else:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_banco(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categorias (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT NOT NULL,
            tipo  TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
            UNIQUE (nome, tipo)
        );

        CREATE TABLE IF NOT EXISTS contas (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS transacoes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            data           DATE NOT NULL,
            descricao      TEXT NOT NULL,
            valor_centavos INTEGER NOT NULL,
            tipo           TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
            categoria_id   INTEGER NOT NULL REFERENCES categorias(id),
            conta_id       INTEGER NOT NULL REFERENCES contas(id) DEFAULT 1,
            criado_em      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS configuracoes (
            chave  TEXT PRIMARY KEY,
            valor  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gastos_fixos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao       TEXT NOT NULL,
            valor_centavos  INTEGER NOT NULL,
            categoria_id    INTEGER NOT NULL REFERENCES categorias(id),
            dia_vencimento  INTEGER NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 31),
            ativo           INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    colunas_transacoes = {row["name"] for row in conn.execute("PRAGMA table_info(transacoes)")}
    if "gasto_fixo_id" not in colunas_transacoes:
        conn.execute(
            "ALTER TABLE transacoes ADD COLUMN gasto_fixo_id "
            "INTEGER REFERENCES gastos_fixos(id) ON DELETE SET NULL"
        )

    colunas_gastos_fixos = {row["name"] for row in conn.execute("PRAGMA table_info(gastos_fixos)")}
    if "total_parcelas" not in colunas_gastos_fixos:
        conn.execute("ALTER TABLE gastos_fixos ADD COLUMN total_parcelas INTEGER")

    conn.execute("INSERT OR IGNORE INTO contas (id, nome) VALUES (1, 'Geral')")

    for nome, tipo in CATEGORIAS_INICIAIS:
        conn.execute(
            "INSERT OR IGNORE INTO categorias (nome, tipo) VALUES (?, ?)", (nome, tipo)
        )

    conn.execute(
        "INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('saldo_inicial_centavos', '0')"
    )
    conn.commit()


def reais_para_centavos(valor_reais):
    return round(valor_reais * 100)


def centavos_para_reais(valor_centavos):
    return valor_centavos / 100


def formatar_moeda(valor_centavos):
    reais = centavos_para_reais(valor_centavos)
    texto = f"{reais:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def listar_categorias(conn, tipo=None):
    if tipo:
        cur = conn.execute(
            "SELECT * FROM categorias WHERE tipo = ? ORDER BY nome", (tipo,)
        )
    else:
        cur = conn.execute("SELECT * FROM categorias ORDER BY tipo, nome")
    return cur.fetchall()


def adicionar_categoria(conn, nome, tipo):
    conn.execute(
        "INSERT OR IGNORE INTO categorias (nome, tipo) VALUES (?, ?)",
        (nome.strip(), tipo),
    )
    conn.commit()


def adicionar_transacao(conn, data, descricao, valor_centavos, tipo, categoria_id, conta_id=1):
    conn.execute(
        """
        INSERT INTO transacoes (data, descricao, valor_centavos, tipo, categoria_id, conta_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (data, descricao, valor_centavos, tipo, categoria_id, conta_id),
    )
    conn.commit()


def listar_transacoes(conn, categoria_id=None, mes=None):
    query = """
        SELECT t.id, t.data, t.descricao, t.valor_centavos, t.tipo,
               c.nome AS categoria, a.nome AS conta
        FROM transacoes t
        JOIN categorias c ON c.id = t.categoria_id
        JOIN contas a ON a.id = t.conta_id
    """
    condicoes = []
    params = []
    if categoria_id is not None:
        condicoes.append("t.categoria_id = ?")
        params.append(categoria_id)
    if mes:
        condicoes.append("substr(t.data, 1, 7) = ?")
        params.append(mes)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY t.data DESC, t.id DESC"

    cur = conn.execute(query, params)
    return cur.fetchall()


def listar_meses_disponiveis(conn):
    cur = conn.execute(
        "SELECT DISTINCT substr(data, 1, 7) AS mes FROM transacoes ORDER BY mes DESC"
    )
    return [row["mes"] for row in cur.fetchall()]


def get_saldo_inicial_centavos(conn):
    cur = conn.execute(
        "SELECT valor FROM configuracoes WHERE chave = 'saldo_inicial_centavos'"
    )
    row = cur.fetchone()
    return int(row["valor"]) if row else 0


def set_saldo_inicial_centavos(conn, valor_centavos):
    conn.execute(
        """
        INSERT INTO configuracoes (chave, valor) VALUES ('saldo_inicial_centavos', ?)
        ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
        """,
        (str(valor_centavos),),
    )
    conn.commit()


def calcular_saldo_atual(conn):
    saldo = get_saldo_inicial_centavos(conn)
    cur = conn.execute(
        "SELECT tipo, COALESCE(SUM(valor_centavos), 0) AS total FROM transacoes GROUP BY tipo"
    )
    for row in cur.fetchall():
        if row["tipo"] == "receita":
            saldo += row["total"]
        else:
            saldo -= row["total"]
    return saldo


def obter_transacao(conn, transacao_id):
    cur = conn.execute(
        "SELECT * FROM transacoes WHERE id = ?", (transacao_id,)
    )
    return cur.fetchone()


def atualizar_transacao(conn, transacao_id, data, descricao, valor_centavos, tipo, categoria_id):
    conn.execute(
        """
        UPDATE transacoes
        SET data = ?, descricao = ?, valor_centavos = ?, tipo = ?, categoria_id = ?
        WHERE id = ?
        """,
        (data, descricao, valor_centavos, tipo, categoria_id, transacao_id),
    )
    conn.commit()


def excluir_transacao(conn, transacao_id):
    conn.execute("DELETE FROM transacoes WHERE id = ?", (transacao_id,))
    conn.commit()


def calcular_soma_por_categoria(conn, tipo=None, mes=None):
    query = """
        SELECT c.nome AS categoria, COALESCE(SUM(t.valor_centavos), 0) AS total
        FROM transacoes t
        JOIN categorias c ON c.id = t.categoria_id
    """
    condicoes = []
    params = []
    if tipo:
        condicoes.append("t.tipo = ?")
        params.append(tipo)
    if mes:
        condicoes.append("substr(t.data, 1, 7) = ?")
        params.append(mes)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " GROUP BY c.nome ORDER BY total DESC"
    cur = conn.execute(query, params)
    return {row["categoria"]: row["total"] for row in cur.fetchall()}


def calcular_totais(conn, mes=None):
    query = "SELECT tipo, COALESCE(SUM(valor_centavos), 0) AS total FROM transacoes"
    params = []
    if mes:
        query += " WHERE substr(data, 1, 7) = ?"
        params.append(mes)
    query += " GROUP BY tipo"

    totais_por_tipo = {"receita": 0, "despesa": 0}
    for row in conn.execute(query, params):
        totais_por_tipo[row["tipo"]] = row["total"]

    return {
        "receitas": totais_por_tipo["receita"],
        "despesas": totais_por_tipo["despesa"],
        "saldo": totais_por_tipo["receita"] - totais_por_tipo["despesa"],
    }


def listar_gastos_fixos(conn, apenas_ativos=True):
    query = """
        SELECT g.id, g.descricao, g.valor_centavos, g.dia_vencimento, g.ativo,
               g.categoria_id, g.total_parcelas, c.nome AS categoria,
               (SELECT COUNT(*) FROM transacoes t WHERE t.gasto_fixo_id = g.id) AS parcelas_lancadas
        FROM gastos_fixos g
        JOIN categorias c ON c.id = g.categoria_id
    """
    if apenas_ativos:
        query += " WHERE g.ativo = 1"
    query += " ORDER BY g.dia_vencimento, g.descricao"
    cur = conn.execute(query)
    return cur.fetchall()


def obter_gasto_fixo(conn, gasto_fixo_id):
    cur = conn.execute("SELECT * FROM gastos_fixos WHERE id = ?", (gasto_fixo_id,))
    return cur.fetchone()


def adicionar_gasto_fixo(conn, descricao, valor_centavos, categoria_id, dia_vencimento, total_parcelas=None):
    conn.execute(
        """
        INSERT INTO gastos_fixos (descricao, valor_centavos, categoria_id, dia_vencimento, total_parcelas)
        VALUES (?, ?, ?, ?, ?)
        """,
        (descricao, valor_centavos, categoria_id, dia_vencimento, total_parcelas),
    )
    conn.commit()


def _atualizar_ativo_por_parcelas(conn, gasto_fixo_id, total_parcelas):
    if total_parcelas is None:
        conn.execute("UPDATE gastos_fixos SET ativo = 1 WHERE id = ?", (gasto_fixo_id,))
        return
    parcelas_lancadas = conn.execute(
        "SELECT COUNT(*) AS total FROM transacoes WHERE gasto_fixo_id = ?", (gasto_fixo_id,)
    ).fetchone()["total"]
    ativo = 0 if parcelas_lancadas >= total_parcelas else 1
    conn.execute("UPDATE gastos_fixos SET ativo = ? WHERE id = ?", (ativo, gasto_fixo_id))


def atualizar_gasto_fixo(
    conn, gasto_fixo_id, descricao, valor_centavos, categoria_id, dia_vencimento, total_parcelas=None
):
    conn.execute(
        """
        UPDATE gastos_fixos
        SET descricao = ?, valor_centavos = ?, categoria_id = ?, dia_vencimento = ?, total_parcelas = ?
        WHERE id = ?
        """,
        (descricao, valor_centavos, categoria_id, dia_vencimento, total_parcelas, gasto_fixo_id),
    )
    _atualizar_ativo_por_parcelas(conn, gasto_fixo_id, total_parcelas)
    conn.commit()


def excluir_gasto_fixo(conn, gasto_fixo_id):
    conn.execute("DELETE FROM gastos_fixos WHERE id = ?", (gasto_fixo_id,))
    conn.commit()


def gastos_fixos_pendentes(conn, mes):
    cur = conn.execute(
        """
        SELECT g.id, g.descricao, g.valor_centavos, g.dia_vencimento, g.categoria_id, g.total_parcelas
        FROM gastos_fixos g
        WHERE g.ativo = 1
          AND NOT EXISTS (
              SELECT 1 FROM transacoes t
              WHERE t.gasto_fixo_id = g.id AND substr(t.data, 1, 7) = ?
          )
        ORDER BY g.dia_vencimento, g.descricao
        """,
        (mes,),
    )
    return cur.fetchall()


def lancar_gastos_fixos_do_mes(conn, mes):
    pendentes = gastos_fixos_pendentes(conn, mes)
    ano, mes_num = (int(parte) for parte in mes.split("-"))
    ultimo_dia_do_mes = calendar.monthrange(ano, mes_num)[1]

    for g in pendentes:
        dia = min(g["dia_vencimento"], ultimo_dia_do_mes)
        conn.execute(
            """
            INSERT INTO transacoes (data, descricao, valor_centavos, tipo, categoria_id, gasto_fixo_id)
            VALUES (?, ?, ?, 'despesa', ?, ?)
            """,
            (f"{mes}-{dia:02d}", g["descricao"], g["valor_centavos"], g["categoria_id"], g["id"]),
        )
        _atualizar_ativo_por_parcelas(conn, g["id"], g["total_parcelas"])
    conn.commit()
    return len(pendentes)
