"""Acesso ao banco de dados SQLite e cálculos financeiros."""
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


def conectar(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
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
        """
    )

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


def listar_transacoes(conn):
    cur = conn.execute(
        """
        SELECT t.id, t.data, t.descricao, t.valor_centavos, t.tipo,
               c.nome AS categoria, a.nome AS conta
        FROM transacoes t
        JOIN categorias c ON c.id = t.categoria_id
        JOIN contas a ON a.id = t.conta_id
        ORDER BY t.data DESC, t.id DESC
        """
    )
    return cur.fetchall()


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


def calcular_soma_por_categoria(conn, tipo=None):
    query = """
        SELECT c.nome AS categoria, COALESCE(SUM(t.valor_centavos), 0) AS total
        FROM transacoes t
        JOIN categorias c ON c.id = t.categoria_id
    """
    params = ()
    if tipo:
        query += " WHERE t.tipo = ?"
        params = (tipo,)
    query += " GROUP BY c.nome ORDER BY total DESC"
    cur = conn.execute(query, params)
    return {row["categoria"]: row["total"] for row in cur.fetchall()}
