import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from abc import ABC, abstractmethod
from datetime import datetime

# ==========================================
# 1. BANCO DE DADOS E PERSISTÊNCIA (SQLite)
# ==========================================
class Database:
    """Gerenciador do Banco de Dados SQLite"""
    def __init__(self, db_name="operix.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS empresas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    tipo_negocio TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa_id INTEGER,
                    nome TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL,
                    perfil TEXT NOT NULL,
                    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa_id INTEGER,
                    nome TEXT NOT NULL,
                    documento TEXT NOT NULL,
                    telefone TEXT,
                    email TEXT,
                    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ativos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    tipo TEXT NOT NULL,
                    identificador TEXT NOT NULL,
                    detalhes TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orcamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa_id INTEGER,
                    cliente_id INTEGER,
                    ativo_id INTEGER,
                    status TEXT NOT NULL,
                    desconto REAL DEFAULT 0.0,
                    total REAL DEFAULT 0.0,
                    data_criacao TEXT,
                    FOREIGN KEY(empresa_id) REFERENCES empresas(id),
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id),
                    FOREIGN KEY(ativo_id) REFERENCES ativos(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ordens_servico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orcamento_id INTEGER UNIQUE,
                    tecnico TEXT,
                    status TEXT NOT NULL,
                    data_inicio TEXT,
                    FOREIGN KEY(orcamento_id) REFERENCES orcamentos(id)
                )
            """)

            # Carga Inicial de Teste
            cursor.execute("SELECT COUNT(*) FROM empresas")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO empresas (nome, tipo_negocio) VALUES ('Oficina Mecânica Pro', 'Oficina Mecânica')")
                empresa_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO usuarios (empresa_id, nome, email, senha, perfil)
                    VALUES (?, 'Administrador', 'admin@operix.com', '1234', 'Administrador')
                """, (empresa_id,))
                
                cursor.execute("""
                    INSERT INTO clientes (empresa_id, nome, documento, telefone, email)
                    VALUES (?, 'Carlos Silva', '123.456.789-00', '(31) 98888-7777', 'carlos@email.com')
                """, (empresa_id,))
                cliente_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO ativos (cliente_id, tipo, identificador, detalhes)
                    VALUES (?, 'Veiculo', 'ABC-1234', 'Toyota Corolla 2020 - Prata')
                """, (cliente_id,))
                
            conn.commit()


# ==========================================
# 2. MODELOS POO
# ==========================================
class Usuario:
    def __init__(self, id_usr, empresa_id, nome, email, perfil):
        self.id = id_usr
        self.empresa_id = empresa_id
        self.nome = nome
        self.email = email
        self.perfil = perfil

class Ativo(ABC):
    def __init__(self, id_ativo, cliente_id, identificador):
        self.id = id_ativo
        self.cliente_id = cliente_id
        self.identificador = identificador

    @abstractmethod
    def descricao(self):
        pass

class Veiculo(Ativo):
    def __init__(self, id_ativo, cliente_id, placa, detalhes=""):
        super().__init__(id_ativo, cliente_id, placa)
        self.detalhes = detalhes

    def descricao(self):
        return f"Veículo [Placa: {self.identificador}] {self.detalhes}"

class Equipamento(Ativo):
    def __init__(self, id_ativo, cliente_id, num_serie, detalhes=""):
        super().__init__(id_ativo, cliente_id, num_serie)
        self.detalhes = detalhes

    def descricao(self):
        return f"Equipamento [Série: {self.identificador}] {self.detalhes}"


# ==========================================
# 3. INTERFACE GRÁFICA TKINTER (OPERIX)
# ==========================================
class OperixApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Operix - Gestão Inteligente da sua Operação")
        self.geometry("1100x680")
        self.minsize(950, 600)

        self.db = Database()
        self.usuario_logado = None

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()

        self.main_container = tk.Frame(self, bg="#F3F4F6")
        self.main_container.pack(fill="both", expand=True)

        self.mostrar_tela_login()

    def configure_styles(self):
        self.style.configure(".", font=("Segoe UI", 10), background="#F3F4F6")
        self.style.configure("TFrame", background="#F3F4F6")
        self.style.configure("Sidebar.TFrame", background="#1E293B")
        
        self.style.configure("Nav.TButton", font=("Segoe UI", 10, "bold"), foreground="#F8FAFC",
                             background="#334155", borderwidth=0, padding=10, anchor="w")
        self.style.map("Nav.TButton", background=[("active", "#2563EB")])

        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), foreground="#FFFFFF",
                             background="#2563EB", padding=8, borderwidth=0)
        self.style.map("Primary.TButton", background=[("active", "#1D4ED8")])

        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), foreground="#FFFFFF",
                             background="#16A34A", padding=8, borderwidth=0)
        self.style.map("Success.TButton", background=[("active", "#15803D")])

        self.style.configure("Treeview", font=("Segoe UI", 10), rowheight=28, background="#FFFFFF")
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#E2E8F0", foreground="#1E293B")

    def limpar_tela(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def mostrar_tela_login(self):
        self.limpar_tela()

        card = tk.Frame(self.main_container, bg="#FFFFFF", padx=35, pady=35, highlightbackground="#E2E8F0", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="OPERIX", font=("Segoe UI", 26, "bold"), fg="#2563EB", bg="#FFFFFF").pack(anchor="w")
        tk.Label(card, text="Gestão Inteligente da sua Operação", font=("Segoe UI", 10), fg="#64748B", bg="#FFFFFF").pack(anchor="w", pady=(0, 20))

        tk.Label(card, text="E-mail", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#334155").pack(anchor="w")
        ent_email = ttk.Entry(card, width=32)
        ent_email.pack(fill="x", pady=(2, 12))
        ent_email.insert(0, "admin@operix.com")

        tk.Label(card, text="Senha", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#334155").pack(anchor="w")
        ent_senha = ttk.Entry(card, show="*", width=32)
        ent_senha.pack(fill="x", pady=(2, 20))
        ent_senha.insert(0, "1234")

        def efetuar_login():
            email = ent_email.get().strip()
            senha = ent_senha.get().strip()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, empresa_id, nome, email, perfil FROM usuarios WHERE email=? AND senha=?", (email, senha))
                row = cursor.fetchone()

                if row:
                    self.usuario_logado = Usuario(*row)
                    self.mostrar_dashboard()
                else:
                    messagebox.showerror("Erro de Autenticação", "E-mail ou senha incorretos.")

        ttk.Button(card, text="Entrar no Sistema", style="Primary.TButton", command=efetuar_login).pack(fill="x")

    def montar_layout_base(self, titulo_pagina):
        self.limpar_tela()

        sidebar = ttk.Frame(self.main_container, style="Sidebar.TFrame", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand_frame = tk.Frame(sidebar, bg="#1E293B", pady=20, padx=15)
        brand_frame.pack(fill="x")
        tk.Label(brand_frame, text="OPERIX", font=("Segoe UI", 18, "bold"), fg="#38BDF8", bg="#1E293B").pack(anchor="w")
        tk.Label(brand_frame, text=f"Usuário: {self.usuario_logado.nome}", font=("Segoe UI", 8), fg="#94A3B8", bg="#1E293B").pack(anchor="w")

        ttk.Button(sidebar, text="📊 Dashboard", style="Nav.TButton", command=self.mostrar_dashboard).pack(fill="x", pady=2)
        ttk.Button(sidebar, text="👥 Clientes & Ativos", style="Nav.TButton", command=self.mostrar_clientes).pack(fill="x", pady=2)
        ttk.Button(sidebar, text="📝 Orçamentos", style="Nav.TButton", command=self.mostrar_orcamentos).pack(fill="x", pady=2)
        ttk.Button(sidebar, text="🛠️ Ordens de Serviço", style="Nav.TButton", command=self.mostrar_os).pack(fill="x", pady=2)
        ttk.Button(sidebar, text="🚪 Sair", style="Nav.TButton", command=self.mostrar_tela_login).pack(fill="x", side="bottom", pady=15)

        content_area = tk.Frame(self.main_container, bg="#F3F4F6", padx=25, pady=20)
        content_area.pack(side="right", fill="both", expand=True)

        header = tk.Frame(content_area, bg="#F3F4F6")
        header.pack(fill="x", pady=(0, 20))
        tk.Label(header, text=titulo_pagina, font=("Segoe UI", 20, "bold"), fg="#0F172A", bg="#F3F4F6").pack(side="left")

        return content_area

    def mostrar_dashboard(self):
        area = self.montar_layout_base("Dashboard")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orcamentos WHERE status='Pendente' AND empresa_id=?", (self.usuario_logado.empresa_id,))
            orc_pendentes = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM ordens_servico os 
                JOIN orcamentos o ON os.orcamento_id = o.id 
                WHERE os.status='Em Andamento' AND o.empresa_id=?
            """, (self.usuario_logado.empresa_id,))
            os_andamento = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM clientes WHERE empresa_id=?", (self.usuario_logado.empresa_id,))
            total_clientes = cursor.fetchone()[0]

        cards_frame = tk.Frame(area, bg="#F3F4F6")
        cards_frame.pack(fill="x", pady=(0, 25))

        def criar_card(parent, titulo, valor, cor_borda):
            f = tk.Frame(parent, bg="#FFFFFF", padx=20, pady=15, highlightbackground=cor_borda, highlightthickness=2)
            f.pack(side="left", fill="both", expand=True, padx=5)
            tk.Label(f, text=titulo, font=("Segoe UI", 10, "bold"), fg="#64748B", bg="#FFFFFF").pack(anchor="w")
            tk.Label(f, text=str(valor), font=("Segoe UI", 22, "bold"), fg="#0F172A", bg="#FFFFFF").pack(anchor="w", pady=(5, 0))

        criar_card(cards_frame, "Orçamentos Pendentes", orc_pendentes, "#EAB308")
        criar_card(cards_frame, "OS em Execução", os_andamento, "#2563EB")
        criar_card(cards_frame, "Total de Clientes", total_clientes, "#16A34A")

        info_frame = tk.Frame(area, bg="#FFFFFF", padx=20, pady=20, highlightbackground="#E2E8F0", highlightthickness=1)
        info_frame.pack(fill="both", expand=True)

        tk.Label(info_frame, text="Fluxo da Operação Operix", font=("Segoe UI", 14, "bold"), fg="#0F172A", bg="#FFFFFF").pack(anchor="w", pady=(0, 10))
        fluxo_txt = (
            "1. Cadastre o Cliente e o seu Ativo (Veículo ou Equipamento).\n"
            "2. Crie um Orçamento detalhado para o serviço.\n"
            "3. Após aprovação do orçamento, gere automaticamente a Ordem de Serviço (OS).\n"
            "4. Acompanhe a execução e conclua o atendimento."
        )
        tk.Label(info_frame, text=fluxo_txt, font=("Segoe UI", 11), fg="#334155", bg="#FFFFFF", justify="left", anchor="w").pack(fill="x")

    def mostrar_clientes(self):
        area = self.montar_layout_base("Clientes e Ativos")

        form_frame = tk.Frame(area, bg="#FFFFFF", padx=15, pady=15, highlightbackground="#E2E8F0", highlightthickness=1)
        form_frame.pack(fill="x", pady=(0, 15))

        tk.Label(form_frame, text="Novo Cliente & Ativo", font=("Segoe UI", 12, "bold"), bg="#FFFFFF", fg="#0F172A").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(form_frame, text="Nome:", bg="#FFFFFF").grid(row=1, column=0, sticky="w")
        ent_nome = ttk.Entry(form_frame, width=25)
        ent_nome.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=5)

        tk.Label(form_frame, text="Documento (CPF/CNPJ):", bg="#FFFFFF").grid(row=1, column=2, sticky="w")
        ent_doc = ttk.Entry(form_frame, width=20)
        ent_doc.grid(row=1, column=3, sticky="w", pady=5)

        tk.Label(form_frame, text="Tipo de Ativo:", bg="#FFFFFF").grid(row=2, column=0, sticky="w")
        combo_tipo = ttk.Combobox(form_frame, values=["Veiculo", "Equipamento"], width=22, state="readonly")
        combo_tipo.grid(row=2, column=1, sticky="w", padx=(0, 15), pady=5)
        combo_tipo.set("Veiculo")

        tk.Label(form_frame, text="Identificador (Placa/Série):", bg="#FFFFFF").grid(row=2, column=2, sticky="w")
        ent_ativo = ttk.Entry(form_frame, width=20)
        ent_ativo.grid(row=2, column=3, sticky="w", pady=5)

        tk.Label(form_frame, text="Detalhes do Ativo:", bg="#FFFFFF").grid(row=3, column=0, sticky="w")
        ent_detalhes = ttk.Entry(form_frame, width=25)
        ent_detalhes.grid(row=3, column=1, sticky="w", padx=(0, 15), pady=5)

        def salvar_cliente():
            nome = ent_nome.get().strip()
            doc = ent_doc.get().strip()
            tipo = combo_tipo.get().strip()
            ativo_ident = ent_ativo.get().strip()
            detalhes = ent_detalhes.get().strip()

            if not nome or not doc or not ativo_ident:
                messagebox.showwarning("Campos Obrigatórios", "Preencha o Nome, Documento e o Ativo.")
                return

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO clientes (empresa_id, nome, documento) VALUES (?, ?, ?)
                """, (self.usuario_logado.empresa_id, nome, doc))
                cliente_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO ativos (cliente_id, tipo, identificador, detalhes) VALUES (?, ?, ?, ?)
                """, (cliente_id, tipo, ativo_ident, detalhes))

            messagebox.showinfo("Sucesso", "Cliente e Ativo cadastrados com sucesso!")
            self.mostrar_clientes()

        ttk.Button(form_frame, text="Salvar Cadastro", style="Primary.TButton", command=salvar_cliente).grid(row=3, column=3, sticky="e", pady=10)

        tree_frame = tk.Frame(area)
        tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "Nome", "Documento", "Tipo Ativo", "Identificador", "Detalhes Ativo")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110)

        tree.pack(fill="both", expand=True)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.nome, c.documento, a.tipo, a.identificador, a.detalhes 
                FROM clientes c 
                LEFT JOIN ativos a ON c.id = a.cliente_id 
                WHERE c.empresa_id=?
            """, (self.usuario_logado.empresa_id,))
            for row in cursor.fetchall():
                tree.insert("", "end", values=row)

    def mostrar_orcamentos(self):
        area = self.montar_layout_base("Orçamentos")

        form_frame = tk.Frame(area, bg="#FFFFFF", padx=15, pady=15, highlightbackground="#E2E8F0", highlightthickness=1)
        form_frame.pack(fill="x", pady=(0, 15))

        tk.Label(form_frame, text="Novo Orçamento", font=("Segoe UI", 12, "bold"), bg="#FFFFFF", fg="#0F172A").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        clientes_map = {}
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.nome, a.id, a.identificador 
                FROM clientes c 
                JOIN ativos a ON c.id = a.cliente_id 
                WHERE c.empresa_id=?
            """, (self.usuario_logado.empresa_id,))
            for cid, cnome, aid, aident in cursor.fetchall():
                clientes_map[f"{cnome} - ({aident})"] = (cid, aid)

        tk.Label(form_frame, text="Cliente / Ativo:", bg="#FFFFFF").grid(row=1, column=0, sticky="w")
        combo_cliente = ttk.Combobox(form_frame, values=list(clientes_map.keys()), width=35, state="readonly")
        combo_cliente.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=5)

        tk.Label(form_frame, text="Valor Total (R$):", bg="#FFFFFF").grid(row=1, column=2, sticky="w")
        ent_valor = ttk.Entry(form_frame, width=15)
        ent_valor.grid(row=1, column=3, sticky="w", pady=5)

        def criar_orcamento():
            selecao = combo_cliente.get()
            valor_str = ent_valor.get().strip().replace(".", "").replace(",", ".")

            if not selecao or not valor_str:
                messagebox.showwarning("Atenção", "Selecione o Cliente e o Valor Total.")
                return

            cid, aid = clientes_map[selecao]
            try:
                total = float(valor_str)
                if total <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Erro", "Valor total inválido. Informe um valor numérico positivo.")
                return

            data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M")
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orcamentos (empresa_id, cliente_id, ativo_id, status, total, data_criacao)
                    VALUES (?, ?, ?, 'Pendente', ?, ?)
                """, (self.usuario_logado.empresa_id, cid, aid, total, data_hoje))

            messagebox.showinfo("Sucesso", "Orçamento registrado!")
            self.mostrar_orcamentos()

        ttk.Button(form_frame, text="Gerar Orçamento", style="Primary.TButton", command=criar_orcamento).grid(row=2, column=3, sticky="e", pady=10)

        tree_frame = tk.Frame(area)
        tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "Cliente", "Ativo", "Status", "Total (R$)", "Data")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110)

        tree.pack(fill="both", expand=True)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.id, c.nome, a.identificador, o.status, o.total, o.data_criacao
                FROM orcamentos o
                JOIN clientes c ON o.cliente_id = c.id
                JOIN ativos a ON o.ativo_id = a.id
                WHERE o.empresa_id=?
            """, (self.usuario_logado.empresa_id,))
            for row in cursor.fetchall():
                tree.insert("", "end", values=row)

        action_frame = tk.Frame(area, bg="#F3F4F6", pady=10)
        action_frame.pack(fill="x")

        def aprovar_e_gerar_os():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Seleção", "Selecione um orçamento para aprovar.")
                return

            item = tree.item(selected[0])
            orc_id, status = item['values'][0], item['values'][3]

            if status != "Pendente":
                messagebox.showwarning("Status Inválido", f"Este orçamento já está '{status}'.")
                return

            data_inicio = datetime.now().strftime("%Y-%m-%d %H:%M")
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE orcamentos SET status='Aprovado' WHERE id=?", (orc_id,))
                cursor.execute("""
                    INSERT INTO ordens_servico (orcamento_id, tecnico, status, data_inicio)
                    VALUES (?, 'Técnico Responsável', 'Em Andamento', ?)
                """, (orc_id, data_inicio))

            messagebox.showinfo("Sucesso", "Orçamento APROVADO! Ordem de Serviço gerada com sucesso.")
            self.mostrar_orcamentos()

        ttk.Button(action_frame, text="✔ Aprovar e Gerar OS", style="Success.TButton", command=aprovar_e_gerar_os).pack(side="right")

    def mostrar_os(self):
        area = self.montar_layout_base("Ordens de Serviço")

        tree_frame = tk.Frame(area)
        tree_frame.pack(fill="both", expand=True)

        columns = ("OS ID", "Orçamento ID", "Cliente", "Ativo", "Técnico", "Status OS", "Início")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110)

        tree.pack(fill="both", expand=True)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT os.id, os.orcamento_id, c.nome, a.identificador, os.tecnico, os.status, os.data_inicio
                FROM ordens_servico os
                JOIN orcamentos o ON os.orcamento_id = o.id
                JOIN clientes c ON o.cliente_id = c.id
                JOIN ativos a ON o.ativo_id = a.id
                WHERE o.empresa_id=?
            """, (self.usuario_logado.empresa_id,))
            for row in cursor.fetchall():
                tree.insert("", "end", values=row)

        action_frame = tk.Frame(area, bg="#F3F4F6", pady=10)
        action_frame.pack(fill="x")

        def concluir_os():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Seleção", "Selecione uma OS para concluir.")
                return

            item = tree.item(selected[0])
            os_id, status = item['values'][0], item['values'][5]

            if status == "Concluída":
                messagebox.showwarning("Atenção", "Esta Ordem de Serviço já está concluída.")
                return

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE ordens_servico SET status='Concluída' WHERE id=?", (os_id,))

            messagebox.showinfo("Sucesso", f"Ordem de Serviço #{os_id} CONCLUÍDA!")
            self.mostrar_os()

        ttk.Button(action_frame, text="🏁 Concluir Execução da OS", style="Success.TButton", command=concluir_os).pack(side="right")


if __name__ == "__main__":
    app = OperixApp()
    app.mainloop()
