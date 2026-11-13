"""Estrutura principal após o login: menu lateral + área de conteúdo.

Atalhos globais (quando não há janela modal aberta):
    Ctrl+1..8  telas do menu      F2 / Ctrl+N  novo registro
    F3 / Ctrl+F  buscar          F5  atualizar a tela
"""

from dataclasses import dataclass

import ttkbootstrap as ttk

from operix import config
from operix.models import Permissao
from operix.services import Servicos
from operix.ui.widgets import FONTE


@dataclass
class ItemMenu:
    chave: str
    texto: str
    permissao: Permissao | None


MENU = [
    ItemMenu("dashboard", "📊  Painel", Permissao.VER_DASHBOARD),
    ItemMenu("ordens", "🛠  Ordens de Serviço", None),
    ItemMenu("clientes", "👥  Clientes e Veículos", Permissao.GERENCIAR_CLIENTES),
    ItemMenu("historico", "🔎  Histórico por placa", None),
    ItemMenu("estoque", "📦  Estoque e Serviços", Permissao.VER_ESTOQUE),
    ItemMenu("financeiro", "💰  Financeiro", Permissao.VER_FINANCEIRO),
    ItemMenu("usuarios", "🔐  Usuários", Permissao.GERENCIAR_USUARIOS),
    ItemMenu("configuracoes", "⚙  Dados da oficina", Permissao.CONFIGURAR_EMPRESA),
]


def _classe_da_tela(chave: str):
    """Importação tardia das telas (evita carregar tudo no login)."""
    from operix.ui.views import clientes, configuracoes, dashboard, estoque, financeiro, historico, ordens, usuarios

    return {
        "dashboard": dashboard.DashboardView,
        "ordens": ordens.OrdensView,
        "clientes": clientes.ClientesView,
        "historico": historico.HistoricoPlacaView,
        "estoque": estoque.EstoqueView,
        "financeiro": financeiro.FinanceiroView,
        "usuarios": usuarios.UsuariosView,
        "configuracoes": configuracoes.ConfiguracoesView,
    }[chave]


class Shell(ttk.Frame):
    def __init__(self, master, servicos: Servicos, ao_sair):
        super().__init__(master)
        self.servicos = servicos
        self.ao_sair = ao_sair
        self.tela_atual = None
        self.chave_atual = None
        sessao = servicos.sessao
        self.itens = [i for i in MENU if i.permissao is None or sessao.pode(i.permissao)]
        self.botoes: dict[str, ttk.Button] = {}

        # ------------------------------------------------------- menu lateral
        lateral = ttk.Frame(self, bootstyle="primary", width=250)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        ttk.Label(lateral, text=config.APP_NOME.upper(), font=(FONTE, 22, "bold"),
                  bootstyle="inverse-primary").pack(anchor="w", padx=18, pady=(22, 0))
        ttk.Label(lateral, text=sessao.empresa.nome, font=(FONTE, 9), bootstyle="inverse-primary",
                  wraplength=210).pack(anchor="w", padx=18, pady=(0, 18))

        for indice, item in enumerate(self.itens, start=1):
            botao = ttk.Button(lateral, text=item.texto, style="Lateral.TButton",
                               command=lambda c=item.chave: self.navegar(c))
            botao.pack(fill="x")
            self.botoes[item.chave] = botao
            if indice <= 9:
                self.bind_all(f"<Control-Key-{indice}>", lambda _e, c=item.chave: self._atalho(lambda: self.navegar(c)))

        rodape = ttk.Frame(lateral, bootstyle="primary")
        rodape.pack(side="bottom", fill="x", pady=12)
        ttk.Label(rodape, text=sessao.usuario.nome, font=(FONTE, 10, "bold"),
                  bootstyle="inverse-primary").pack(anchor="w", padx=18)
        ttk.Label(rodape, text=sessao.usuario.perfil_enum.rotulo, font=(FONTE, 9),
                  bootstyle="inverse-primary").pack(anchor="w", padx=18, pady=(0, 8))
        ttk.Button(rodape, text="🔑  Alterar minha senha", style="Lateral.TButton",
                   command=self._alterar_senha).pack(fill="x")
        ttk.Button(rodape, text="🚪  Sair", style="Lateral.TButton", command=self.ao_sair).pack(fill="x")

        # --------------------------------------------------------- conteúdo
        self.area = ttk.Frame(self, padding=(24, 18))
        self.area.pack(side="left", fill="both", expand=True)

        for sequencia, metodo in (("<F2>", "novo"), ("<Control-n>", "novo"), ("<F3>", "focar_busca"),
                                  ("<Control-f>", "focar_busca"), ("<F5>", "atualizar")):
            self.bind_all(sequencia, lambda _e, m=metodo: self._atalho(lambda: self._chamar_tela(m)))

        inicial = "dashboard" if sessao.pode(Permissao.VER_DASHBOARD) else "ordens"
        self.navegar(inicial)

    def destroy(self):
        # Remove atalhos globais para não vazarem para a tela de login
        for indice in range(1, 10):
            self.unbind_all(f"<Control-Key-{indice}>")
        for sequencia in ("<F2>", "<Control-n>", "<F3>", "<Control-f>", "<F5>"):
            self.unbind_all(sequencia)
        super().destroy()

    def _atalho(self, acao):
        if self.winfo_toplevel().grab_current() is None:  # ignora com janela modal aberta
            acao()
        return "break"

    def _chamar_tela(self, metodo: str):
        funcao = getattr(self.tela_atual, metodo, None)
        if callable(funcao):
            funcao()

    def navegar(self, chave: str, **parametros) -> None:
        """Abre uma tela do menu. ``parametros`` são repassados à tela (ex.: filtro)."""
        if chave not in self.botoes:
            return
        if self.tela_atual is not None:
            self.tela_atual.destroy()
        for c, botao in self.botoes.items():
            botao.configure(style="LateralAtivo.TButton" if c == chave else "Lateral.TButton")
        classe = _classe_da_tela(chave)
        self.chave_atual = chave
        self.tela_atual = classe(self.area, self, **parametros)
        self.tela_atual.pack(fill="both", expand=True)

    def _alterar_senha(self):
        from operix.ui.widgets import Campo, FormularioDialog

        FormularioDialog(
            self, "Alterar minha senha",
            [Campo("atual", "Senha atual", "senha", True), Campo("nova", "Nova senha", "senha", True,
                                                                 dica=f"Mínimo de {config.SENHA_MINIMA} caracteres"),
             Campo("confirmacao", "Confirme a nova senha", "senha", True)],
            lambda d: self.servicos.usuarios.alterar_propria_senha(d["atual"], d["nova"], d["confirmacao"]),
            texto_botao="Alterar senha", mensagem_sucesso="Senha alterada com sucesso.",
        )


class View(ttk.Frame):
    """Base das telas: cabeçalho padrão + acesso aos serviços e à navegação."""

    titulo = ""
    subtitulo = ""

    def __init__(self, master, shell: Shell):
        super().__init__(master)
        self.shell = shell
        self.servicos: Servicos = shell.servicos
        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill="x", pady=(0, 14))
        ttk.Label(cabecalho, text=self.titulo, font=(FONTE, 20, "bold")).pack(side="left", anchor="w")
        if self.subtitulo:
            ttk.Label(cabecalho, text=self.subtitulo, bootstyle="secondary").pack(side="left", padx=14, pady=(8, 0))
        self.acoes = ttk.Frame(cabecalho)  # botões de ação no canto direito do cabeçalho
        self.acoes.pack(side="right")

    @property
    def sessao(self):
        return self.servicos.sessao

    def pode(self, permissao: Permissao) -> bool:
        return self.sessao.pode(permissao)

    def botao_acao(self, texto: str, comando, estilo: str = "primary", dica: str | None = None) -> ttk.Button:
        botao = ttk.Button(self.acoes, text=texto, bootstyle=estilo, command=comando)
        botao.pack(side="left", padx=(8, 0))
        if dica:
            from ttkbootstrap.tooltip import ToolTip

            ToolTip(botao, text=dica)
        return botao

    def atualizar(self) -> None:  # sobrescrito pelas telas
        pass


def exigir_selecao(registro, mensagem: str = "Selecione um registro na tabela.") -> dict:
    """Usado pelos botões que dependem de uma linha selecionada."""
    from operix.errors import ValidacaoError

    if not registro:
        raise ValidacaoError(mensagem)
    return registro


