"""Cadastro de usuários e perfis de acesso (somente administrador)."""

import ttkbootstrap as ttk

from operix import config
from operix.models import Perfil
from operix.ui.shell import View, exigir_selecao
from operix.ui.widgets import FONTE, Campo, Coluna, FormularioDialog, TabelaDados, confirmar, notificar

DESCRICAO_PERFIS = (
    "Administrador: acesso total (usuários, financeiro, preços, estornos).   "
    "Atendente: clientes, OS, aprovação, pagamentos e entrada de estoque.   "
    "Mecânico: vê as próprias OS, atualiza status de execução e diagnóstico."
)


class UsuariosView(View):
    titulo = "Usuários"
    subtitulo = "Quem acessa o sistema e o que cada um pode fazer"

    def __init__(self, master, shell):
        super().__init__(master, shell)
        self.botao_acao("＋ Novo usuário (F2)", self.novo, "success")
        ttk.Label(self, text=DESCRICAO_PERFIS, bootstyle="secondary", wraplength=1000, font=(FONTE, 9)).pack(
            anchor="w", pady=(0, 10))
        self.tabela = TabelaDados(self, [
            Coluna("nome", "Nome", 220), Coluna("email", "E-mail (login)", 240),
            Coluna("perfil", "Perfil", 140, formato=lambda p: Perfil(p).rotulo),
            Coluna("ativo", "Situação", 100, formato=lambda a: "Ativo" if a else "Inativo"),
        ], ao_abrir=self.editar)
        self.tabela.pack(fill="both", expand=True)
        for texto, estilo, comando in (("Ativar/Desativar", "secondary-outline", self.alternar),
                                       ("Editar / redefinir senha", "primary-outline", self.editar)):
            ttk.Button(self.tabela.barra, text=texto, bootstyle=estilo, command=lambda c=comando: c()).pack(
                side="right", padx=(6, 0))
        self.atualizar()

    def atualizar(self):
        self.tabela.carregar([vars(u) for u in self.servicos.usuarios.listar()],
                             tag=lambda u: None if u["ativo"] else "inativo")

    def focar_busca(self):
        self.tabela.focar_busca()

    def _campos(self, novo: bool):
        dica = f"Mínimo de {config.SENHA_MINIMA} caracteres" + ("" if novo else " · deixe em branco para manter")
        return [
            Campo("nome", "Nome", obrigatorio=True, largura=36),
            Campo("email", "E-mail (login)", obrigatorio=True, largura=36),
            Campo("perfil", "Perfil de acesso", "combo", True, [p.rotulo for p in Perfil], largura=20),
            Campo("senha", "Senha" if novo else "Nova senha", "senha", novo, largura=20, dica=dica),
            Campo("confirmacao", "Confirme a senha", "senha", novo, largura=20),
        ]

    def novo(self):
        FormularioDialog(self, "Novo usuário", self._campos(True),
                         lambda d: (self.servicos.usuarios.criar(d), self.atualizar()),
                         valores={"perfil": Perfil.ATENDENTE.rotulo}, colunas=2, mensagem_sucesso="Usuário criado.")

    def editar(self, registro=None):
        usuario = registro or exigir_selecao(self.tabela.selecionado(), "Selecione um usuário.")
        FormularioDialog(self, "Editar usuário", self._campos(False),
                         lambda d: (self.servicos.usuarios.atualizar(usuario["id"], d), self.atualizar()),
                         valores={**usuario, "perfil": Perfil(usuario["perfil"]).rotulo}, colunas=2)

    def alternar(self):
        usuario = exigir_selecao(self.tabela.selecionado(), "Selecione um usuário.")
        ativar = not usuario["ativo"]
        if confirmar(self, f"{'Ativar' if ativar else 'Desativar'} o usuário {usuario['nome']}?"):
            self.servicos.usuarios.definir_ativo(usuario["id"], ativar)
            self.atualizar()
            notificar("Usuário atualizado.")
