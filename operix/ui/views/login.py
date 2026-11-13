"""Tela de login e assistente de primeiro acesso."""

import ttkbootstrap as ttk

from operix import __version__, config
from operix.services import AuthService
from operix.ui.widgets import FONTE, MASCARAS, aplicar_mascara


class _TelaCentral(ttk.Frame):
    """Fundo neutro com um cartão centralizado."""

    def __init__(self, master, largura: int = 380):
        super().__init__(master, bootstyle="light")
        externo = ttk.Frame(self, bootstyle="secondary", padding=1)
        externo.place(relx=0.5, rely=0.5, anchor="center")
        self.cartao = ttk.Frame(externo, padding=36)
        self.cartao.pack()
        ttk.Label(self.cartao, text=config.APP_NOME.upper(), font=(FONTE, 28, "bold"),
                  bootstyle="primary").pack(anchor="w")
        ttk.Label(self.cartao, text=config.APP_SUBTITULO, bootstyle="secondary",
                  wraplength=largura).pack(anchor="w", pady=(0, 22))
        ttk.Label(self, text=f"versão {__version__}", bootstyle="secondary", font=(FONTE, 8),
                  background=self.winfo_toplevel().style.colors.light).place(relx=0.99, rely=0.99, anchor="se")

    def campo(self, rotulo: str, largura: int = 36, senha: bool = False, mascara: str | None = None) -> ttk.Entry:
        ttk.Label(self.cartao, text=rotulo, font=(FONTE, 9, "bold")).pack(anchor="w")
        entry = ttk.Entry(self.cartao, width=largura, show="•" if senha else "", font=(FONTE, 11))
        entry.pack(fill="x", pady=(2, 12))
        if mascara:
            aplicar_mascara(entry, MASCARAS[mascara])
        return entry


class LoginView(_TelaCentral):
    def __init__(self, master, db, ao_entrar):
        super().__init__(master)
        self.auth = AuthService(db)
        self.ao_entrar = ao_entrar
        self.ent_email = self.campo("E-mail")
        self.ent_senha = self.campo("Senha", senha=True)
        self.lbl_erro = ttk.Label(self.cartao, text="", bootstyle="danger", wraplength=320)
        self.lbl_erro.pack(anchor="w")
        self.btn = ttk.Button(self.cartao, text="Entrar", bootstyle="primary", command=self.entrar)
        self.btn.pack(fill="x", pady=(8, 0), ipady=4)
        ttk.Label(self.cartao, text="Esqueceu a senha? Peça ao administrador da oficina para redefini-la.",
                  bootstyle="secondary", font=(FONTE, 8), wraplength=320).pack(anchor="w", pady=(14, 0))

        self.ent_email.bind("<Return>", lambda _e: self.ent_senha.focus_set())
        self.ent_senha.bind("<Return>", lambda _e: self.entrar())
        self.after(100, self.ent_email.focus_set)

    def entrar(self):
        from operix.errors import AutenticacaoError

        self.lbl_erro.configure(text="")
        try:
            sessao = self.auth.autenticar(self.ent_email.get(), self.ent_senha.get())
        except AutenticacaoError as erro:
            # Erro de login aparece no próprio cartão (sem janela pop-up)
            self.lbl_erro.configure(text=erro.mensagem)
            self.ent_senha.delete(0, "end")
            self.ent_senha.focus_set()
            return
        self.ao_entrar(sessao)


class PrimeiroAcessoView(_TelaCentral):
    """Primeira execução: cadastra a oficina e o administrador."""

    def __init__(self, master, db, ao_entrar):
        super().__init__(master, largura=420)
        self.auth = AuthService(db)
        self.ao_entrar = ao_entrar
        ttk.Label(self.cartao, text="Bem-vindo! Vamos configurar sua oficina.", font=(FONTE, 12, "bold")).pack(
            anchor="w", pady=(0, 14))
        self.ent_oficina = self.campo("Nome da oficina *", 44)
        self.ent_cnpj = self.campo("CNPJ (opcional)", 44, mascara="cnpj")
        ttk.Separator(self.cartao).pack(fill="x", pady=(2, 12))
        self.ent_nome = self.campo("Seu nome (administrador) *", 44)
        self.ent_email = self.campo("Seu e-mail (login) *", 44)
        self.ent_senha = self.campo(f"Senha * (mínimo {config.SENHA_MINIMA} caracteres)", 44, senha=True)
        self.ent_conf = self.campo("Confirme a senha *", 44, senha=True)
        ttk.Button(self.cartao, text="Concluir configuração", bootstyle="success",
                   command=self.concluir).pack(fill="x", pady=(8, 0), ipady=4)
        self.ent_conf.bind("<Return>", lambda _e: self.concluir())
        self.after(100, self.ent_oficina.focus_set)

    def concluir(self):
        sessao = self.auth.configurar_primeiro_acesso(
            self.ent_oficina.get(), self.ent_cnpj.get(), self.ent_nome.get(), self.ent_email.get(),
            self.ent_senha.get(), self.ent_conf.get(),
        )
        self.ao_entrar(sessao)
