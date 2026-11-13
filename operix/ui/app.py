"""Janela principal e ponto de entrada da aplicação.

Aqui fica o **tratador central de erros**: qualquer exceção que escape de um
botão/atalho chega em :meth:`OperixApp._tratar_erro`. Erros de negócio
(:class:`OperixError`) viram um aviso amigável; erros inesperados são gravados
no ``operix.log`` com o traceback completo e o usuário vê uma mensagem
genérica. Em nenhum caso a aplicação é fechada.
"""

import argparse
import logging
import sys
import tkinter as tk
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

import ttkbootstrap as ttk

from operix import __version__, config
from operix.database import Database
from operix.errors import OperixError
from operix.services import AuthService, Servicos, Sessao

log = logging.getLogger("operix")


def configurar_log() -> None:
    raiz = logging.getLogger()
    if raiz.handlers:
        return
    raiz.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    try:
        arquivo = RotatingFileHandler(config.CAMINHO_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        arquivo.setFormatter(formato)
        raiz.addHandler(arquivo)
    except OSError:
        pass  # sem permissão de escrita: segue só com o console
    console = logging.StreamHandler()
    console.setFormatter(formato)
    console.setLevel(logging.WARNING)
    raiz.addHandler(console)


class OperixApp(ttk.Window):
    def __init__(self, db: Database):
        super().__init__(title=f"{config.APP_NOME} · {config.APP_SUBTITULO}", themename=config.TEMA_PADRAO,
                         size=(1280, 760), minsize=(1080, 640))
        self.db = db
        self.servicos: Servicos | None = None
        self._tela: tk.Widget | None = None
        self.report_callback_exception = self._tratar_erro
        self._configurar_estilos()
        try:
            self.state("zoomed")  # maximizada no Windows
        except tk.TclError:
            self.place_window_center()
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.iniciar()

    def _configurar_estilos(self) -> None:
        estilo = self.style
        estilo.configure(".", font=("Segoe UI", 10))
        ttk.Treeview(self, bootstyle="primary")  # cria o estilo do tema antes de ajustá-lo
        for prefixo in ("", "primary."):
            estilo.configure(f"{prefixo}Treeview", rowheight=30, font=("Segoe UI", 10))
            estilo.configure(f"{prefixo}Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(6, 6))
        estilo.configure("TButton", font=("Segoe UI", 10))
        # Botões do menu lateral (estilos próprios com as cores do tema)
        cores = estilo.colors
        ttk.Button(self, bootstyle="primary")  # garante que o estilo base exista
        for nome, fundo, peso in (("Lateral.TButton", cores.primary, "normal"),
                                  ("LateralAtivo.TButton", cores.info, "bold")):
            estilo.configure(nome, anchor="w", padding=(18, 10), font=("Segoe UI", 10, peso), background=fundo,
                             foreground=cores.selectfg, bordercolor=fundo, darkcolor=fundo, lightcolor=fundo,
                             relief="flat", focuscolor=fundo)
            estilo.map(nome, background=[("active", cores.info)], bordercolor=[("active", cores.info)],
                       lightcolor=[("active", cores.info)], darkcolor=[("active", cores.info)])

    # ------------------------------------------------------------ navegação
    def _trocar_tela(self, tela: tk.Widget) -> None:
        if self._tela is not None:
            self._tela.destroy()
        self._tela = tela
        tela.pack(fill="both", expand=True)

    def iniciar(self) -> None:
        from operix.ui.views.login import LoginView, PrimeiroAcessoView

        self.servicos = None
        if AuthService(self.db).precisa_configuracao_inicial():
            self._trocar_tela(PrimeiroAcessoView(self, self.db, ao_entrar=self.entrar))
        else:
            self._trocar_tela(LoginView(self, self.db, ao_entrar=self.entrar))

    def entrar(self, sessao: Sessao) -> None:
        from operix.ui.shell import Shell

        self.servicos = Servicos(self.db, sessao)
        self._trocar_tela(Shell(self, self.servicos, ao_sair=self.sair))

    def sair(self) -> None:
        if messagebox.askyesno("Sair", "Deseja encerrar a sessão?", parent=self):
            log.info("Logout: %s", self.servicos.sessao.usuario.email if self.servicos else "-")
            self.iniciar()

    def fechar(self) -> None:
        if self.servicos is None or messagebox.askyesno("Fechar", "Deseja fechar o Operix?", parent=self):
            self.destroy()

    # ------------------------------------------------------- tratamento de erro
    def _janela_ativa(self) -> tk.Misc:
        try:
            alvo = self.grab_current() or self.focus_get()
            return alvo.winfo_toplevel() if alvo else self
        except (tk.TclError, KeyError):
            return self

    def _tratar_erro(self, tipo, valor, rastreio) -> None:
        if isinstance(valor, OperixError):
            log.info("Aviso ao usuário: %s", valor.mensagem)
            messagebox.showwarning(valor.titulo, valor.mensagem, parent=self._janela_ativa())
            return
        log.error("Erro inesperado", exc_info=(tipo, valor, rastreio))
        messagebox.showerror(
            "Erro inesperado",
            "Ocorreu um erro inesperado, mas seus dados estão preservados.\n\n"
            f"Detalhe técnico: {tipo.__name__}: {valor}\n\n"
            f"O registro completo foi salvo em:\n{config.CAMINHO_LOG}",
            parent=self._janela_ativa(),
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="operix", description="Operix - gestão de oficina mecânica")
    parser.add_argument("--demo", action="store_true", help="cria dados de demonstração em um banco vazio")
    parser.add_argument("--banco", help="caminho do arquivo .db (padrão: operix.db na pasta do projeto)")
    parser.add_argument("--version", action="version", version=f"Operix {__version__}")
    args = parser.parse_args(argv)

    configurar_log()
    log.info("Iniciando Operix %s", __version__)
    try:
        db = Database(args.banco or config.CAMINHO_BANCO)
        if args.demo:
            from operix.services.demo import popular_demo

            try:
                popular_demo(db)
                print("Dados de demonstração criados. Logins: admin@demo.com / admin123, "
                      "atendente@demo.com / atend123, mecanico@demo.com / mec123")
            except OperixError as erro:
                print(f"Aviso: {erro.mensagem}")
    except OperixError as erro:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(erro.titulo, erro.mensagem)
        raiz.destroy()
        sys.exit(1)

    app = OperixApp(db)
    app.mainloop()


if __name__ == "__main__":
    main()
