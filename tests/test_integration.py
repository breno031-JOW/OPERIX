import os
import sqlite3
import unittest
from datetime import datetime

class TestOperixIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_name = "test_operix.db"
        if os.path.exists(cls.db_name):
            os.remove(cls.db_name)
        
        cls.conn = sqlite3.connect(cls.db_name)
        cls.conn.execute("PRAGMA foreign_keys = ON;")
        cls.init_schema()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        if os.path.exists(cls.db_name):
            os.remove(cls.db_name)

    @classmethod
    def init_schema(cls):
        sql_path = "Operix_Modelo_Fisico.sql"
        if os.path.exists(sql_path):
            with open(sql_path, "r", encoding="utf-8") as f:
                cls.conn.executescript(f.read())
        else:
            cls.conn.executescript("""
                CREATE TABLE empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, tipo_negocio TEXT NOT NULL);
                CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, nome TEXT NOT NULL, email TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, perfil TEXT NOT NULL, FOREIGN KEY(empresa_id) REFERENCES empresas(id));
                CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, nome TEXT NOT NULL, documento TEXT NOT NULL, telefone TEXT, email TEXT, FOREIGN KEY(empresa_id) REFERENCES empresas(id));
                CREATE TABLE ativos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT NOT NULL, identificador TEXT NOT NULL, detalhes TEXT, FOREIGN KEY(cliente_id) REFERENCES clientes(id));
                CREATE TABLE orcamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, cliente_id INTEGER, ativo_id INTEGER, status TEXT NOT NULL, desconto REAL DEFAULT 0.0, total REAL DEFAULT 0.0, data_criacao TEXT, FOREIGN KEY(empresa_id) REFERENCES empresas(id), FOREIGN KEY(cliente_id) REFERENCES clientes(id), FOREIGN KEY(ativo_id) REFERENCES ativos(id));
                CREATE TABLE ordens_servico (id INTEGER PRIMARY KEY AUTOINCREMENT, orcamento_id INTEGER UNIQUE, tecnico TEXT, status TEXT NOT NULL, data_inicio TEXT, FOREIGN KEY(orcamento_id) REFERENCES orcamentos(id));
            """)
            cls.conn.execute("INSERT INTO empresas (nome, tipo_negocio) VALUES ('Empresa Teste', 'Mecânica')")
            cls.conn.execute("INSERT INTO usuarios (empresa_id, nome, email, senha, perfil) VALUES (1, 'Admin', 'admin@operix.com', '1234', 'Administrador')")
            cls.conn.commit()

    def test_01_login_validations(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE email=? AND senha=?", ("admin@operix.com", "1234"))
        self.assertIsNotNone(cursor.fetchone())
        
        cursor.execute("SELECT id FROM usuarios WHERE email=? AND senha=?", ("admin@operix.com", "wrong_pass"))
        self.assertIsNone(cursor.fetchone())

    def test_02_cliente_ativo_creation(self):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO clientes (empresa_id, nome, documento) VALUES (1, 'Ana Lima', '999.888.777-66')")
        cliente_id = cursor.lastrowid

        cursor.execute("INSERT INTO ativos (cliente_id, tipo, identificador, detalhes) VALUES (?, 'Equipamento', 'EQ-9900', 'Torno CNC')", (cliente_id,))
        ativo_id = cursor.lastrowid

        cursor.execute("SELECT tipo, identificador FROM ativos WHERE id=?", (ativo_id,))
        row = cursor.fetchone()
        self.assertEqual(row, ("Equipamento", "EQ-9900"))

    def test_03_orcamento_os_flow(self):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO orcamentos (empresa_id, cliente_id, ativo_id, status, total, data_criacao) VALUES (1, 1, 1, 'Pendente', 1250.90, ?)", (datetime.now().strftime("%Y-%m-%d"),))
        orc_id = cursor.lastrowid

        cursor.execute("UPDATE orcamentos SET status='Aprovado' WHERE id=?", (orc_id,))
        cursor.execute("INSERT INTO ordens_servico (orcamento_id, tecnico, status, data_inicio) VALUES (?, 'Técnico 1', 'Em Andamento', ?)", (orc_id, datetime.now().strftime("%Y-%m-%d")))
        os_id = cursor.lastrowid

        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO ordens_servico (orcamento_id, tecnico, status, data_inicio) VALUES (?, 'Técnico 2', 'Em Andamento', ?)", (orc_id, datetime.now().strftime("%Y-%m-%d")))

        cursor.execute("UPDATE ordens_servico SET status='Concluída' WHERE id=?", (os_id,))
        cursor.execute("SELECT status FROM ordens_servico WHERE id=?", (os_id,))
        self.assertEqual(cursor.fetchone()[0], "Concluída")

if __name__ == "__main__":
    unittest.main()
