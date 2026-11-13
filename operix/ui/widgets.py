"""Componentes reutilizáveis da interface.

- :class:`TabelaDados`: tabela com busca instantânea, ordenação por coluna,
  barra de rolagem, cores por status e atalhos de teclado;
- :class:`FormularioDialog`: janela modal de cadastro montada a partir de uma
  lista de :class:`Campo` (com máscaras, Enter = salvar, Esc = cancelar);
- :class:`ComboBusca`: combobox que filtra as opções enquanto se digita;
- funções de feedback: :func:`notificar`, :func:`confirmar`, :func:`perguntar_texto`.
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import messagebox, simpledialog

import ttkbootstrap as ttk
from ttkbootstrap.toast import ToastNotification

from operix.errors import ValidacaoError
from operix.utils import formatters as fmt
from operix.utils import validators as val

FONTE = "Segoe UI"
_TECLAS_NAVEGACAO = {"Left", "Right", "Up", "Down", "Home", "End", "Tab", "Shift_L", "Shift_R",
                     "Control_L", "Control_R", "BackSpace", "Delete", "ISO_Left_Tab"}


# ================================================================== feedback
def notificar(mensagem: str, titulo: str = "Operix", tipo: str = "success", duracao: int = 2500) -> None:
    """Aviso discreto que some sozinho (canto inferior direito da tela)."""
    try:
        ToastNotification(title=titulo, message=mensagem, duration=duracao, bootstyle=tipo,
                          position=(30, 60, "se")).show_toast()
    except tk.TclError:
        pass  # janela fechando: ignora o aviso


def confirmar(parent, mensagem: str, titulo: str = "Confirmar") -> bool:
    return messagebox.askyesno(titulo, mensagem, parent=parent)


def perguntar_texto(parent, titulo: str, mensagem: str, inicial: str = "") -> str | None:
    return simpledialog.askstring(titulo, mensagem, parent=parent, initialvalue=inicial)


# =================================================================== máscaras
def aplicar_mascara(entry: tk.Entry, funcao: Callable[[str], str]) -> None:
    """Reformata o conteúdo do campo a cada tecla (CPF/CNPJ, telefone, placa...)."""

    def ao_digitar(evento):
        if evento.keysym in _TECLAS_NAVEGACAO:
            return
        atual = entry.get()
        novo = funcao(atual)
        if novo != atual:
            entry.delete(0, "end")
            entry.insert(0, novo)
            entry.icursor("end")

    entry.bind("<KeyRelease>", ao_digitar, add="+")


def aplicar_formato_moeda(entry: tk.Entry) -> None:
    """Ao sair do campo, exibe o valor como 1.250,90."""

    def ao_sair(_evento):
        texto = entry.get().strip()
        if not texto:
            return
        try:
            novo = fmt.formatar_moeda(fmt.moeda_para_centavos(texto), simbolo=False)
        except ValidacaoError:
            return
        entry.delete(0, "end")
        entry.insert(0, novo)

    entry.bind("<FocusOut>", ao_sair, add="+")


MASCARAS = {
    "documento": val.mascara_documento_parcial,
    "telefone": val.mascara_telefone_parcial,
    "placa": val.mascara_placa_parcial,
    "cnpj": val.mascara_documento_parcial,
}


# ================================================================ ComboBusca
class ComboBusca(ttk.Combobox):
    """Combobox editável que filtra as opções conforme o usuário digita.

    ``opcoes`` é uma lista de tuplas ``(valor, rotulo)``.
    """

    def __init__(self, master, opcoes: list[tuple] | None = None, ao_escolher: Callable | None = None, **kw):
        super().__init__(master, **kw)
        self._ao_escolher = ao_escolher
        self.definir_opcoes(opcoes or [])
        self.bind("<KeyRelease>", self._filtrar, add="+")
        self.bind("<<ComboboxSelected>>", self._selecionado, add="+")

    def definir_opcoes(self, opcoes: list[tuple]) -> None:
        self._opcoes = list(opcoes)
        self._por_rotulo = {rotulo: valor for valor, rotulo in self._opcoes}
        self.configure(values=[r for _, r in self._opcoes])

    def _filtrar(self, evento):
        if evento.keysym in _TECLAS_NAVEGACAO | {"Return", "Escape"}:
            return
        termos = fmt.normalizar_busca(self.get()).split()
        filtradas = [r for _, r in self._opcoes if all(t in fmt.normalizar_busca(r) for t in termos)]
        self.configure(values=filtradas)

    def _selecionado(self, _evento=None):
        if self._ao_escolher:
            self._ao_escolher(self.valor())

    def valor(self):
        return self._por_rotulo.get(self.get())

    def selecionar_valor(self, valor) -> None:
        for v, rotulo in self._opcoes:
            if v == valor:
                self.set(rotulo)
                self._selecionado()
                return
        self.set("")


# ================================================================ TabelaDados
@dataclass
class Coluna:
    chave: str
    titulo: str
    largura: int = 120
    ancora: str = "w"
    formato: Callable | None = None  # valor -> texto exibido
    esticar: bool = True  # mantido por compatibilidade; todas as colunas se ajustam à largura


class TabelaDados(ttk.Frame):
    """Tabela com busca instantânea e ordenação clicando no cabeçalho."""

    def __init__(self, master, colunas: list[Coluna], ao_abrir: Callable | None = None,
                 ao_selecionar: Callable | None = None, com_busca: bool = True, altura: int = 12,
                 texto_busca: str = "Buscar (F3)", chave_id: str = "id"):
        super().__init__(master)
        self.colunas = colunas
        self.ao_abrir = ao_abrir
        self.ao_selecionar = ao_selecionar
        self.chave_id = chave_id
        self._registros: list[dict] = []
        self._visiveis: dict[str, dict] = {}
        self._ordem: tuple[str, bool] | None = None
        self._tag_func: Callable | None = None

        # Barra superior: busca à esquerda; as telas podem incluir botões em ``self.barra``
        self.barra = ttk.Frame(self)
        self.barra.pack(fill="x", pady=(0, 6))
        self.var_busca = tk.StringVar()
        if com_busca:
            ttk.Label(self.barra, text="🔍").pack(side="left", padx=(0, 4))
            self.entry_busca = ttk.Entry(self.barra, textvariable=self.var_busca, width=34)
            self.entry_busca.pack(side="left")
            self._placeholder(texto_busca)
            self.var_busca.trace_add("write", lambda *_: self._aplicar())
        self.lbl_contagem = ttk.Label(self.barra, text="", bootstyle="secondary")
        self.lbl_contagem.pack(side="left", padx=10)

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(corpo, columns=[c.chave for c in colunas], show="headings", height=altura,
                                 selectmode="browse", bootstyle="primary")
        for c in colunas:
            self.tree.heading(c.chave, text=c.titulo, anchor=c.ancora, command=lambda k=c.chave: self._ordenar(k))
            self.tree.column(c.chave, width=c.largura, anchor=c.ancora, stretch=False, minwidth=40)
        barra_v = ttk.Scrollbar(corpo, orient="vertical", command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscrollcommand=barra_v.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra_v.pack(side="right", fill="y")

        self.tree.bind("<Configure>", self._ajustar_colunas, add="+")
        self.tree.bind("<Double-1>", self._abrir)
        self.tree.bind("<Return>", self._abrir)
        self.tree.bind("<<TreeviewSelect>>", self._selecionar)
        self._configurar_tags()

    # ------------------------------------------------------------ aparência
    def _ajustar_colunas(self, evento) -> None:
        """Distribui a largura disponível entre as colunas, proporcional à largura sugerida."""
        disponivel = evento.width - 4
        sugerido = sum(c.largura for c in self.colunas)
        if disponivel <= 50 or not sugerido:
            return
        fator = disponivel / sugerido
        for c in self.colunas:
            self.tree.column(c.chave, width=max(40, int(c.largura * fator)))

    def _configurar_tags(self) -> None:
        cores = ttk.Style().colors
        for nome in ("primary", "secondary", "success", "info", "warning", "danger", "dark"):
            self.tree.tag_configure(nome, foreground=cores.get(nome))
        self.tree.tag_configure("negrito", font=(FONTE, 10, "bold"))
        self.tree.tag_configure("inativo", foreground=cores.get("secondary"))

    def _placeholder(self, texto: str) -> None:
        """Texto de ajuda exibido em cinza enquanto a busca está vazia."""
        self._texto_placeholder = texto
        self._em_placeholder = False

        def mostrar(_=None):
            if not self.var_busca.get():
                self._em_placeholder = True
                self.entry_busca.configure(foreground="gray")
                self.entry_busca.insert(0, texto)

        def esconder(_=None):
            if self._em_placeholder:
                self._em_placeholder = False
                self.entry_busca.delete(0, "end")
                self.entry_busca.configure(foreground="")

        self.entry_busca.bind("<FocusIn>", esconder, add="+")
        self.entry_busca.bind("<FocusOut>", mostrar, add="+")
        self.entry_busca.bind("<Escape>", lambda _: (self.var_busca.set(""), self.tree.focus_set()))
        self.entry_busca.bind("<Down>", lambda _: self.focar_tabela())
        mostrar()

    def _texto_busca(self) -> str:
        return "" if getattr(self, "_em_placeholder", False) else self.var_busca.get()

    # ---------------------------------------------------------------- dados
    def carregar(self, registros: list[dict], tag: Callable[[dict], str | tuple | None] | None = None) -> None:
        """Substitui os dados da tabela, mantendo busca, ordenação e seleção."""
        selecionado = self.selecionado()
        self._registros = list(registros)
        self._tag_func = tag
        self._aplicar()
        if selecionado:
            self.selecionar_id(selecionado.get(self.chave_id))

    def _formatar(self, coluna: Coluna, registro: dict) -> str:
        valor = registro.get(coluna.chave)
        if coluna.formato:
            try:
                return coluna.formato(valor)
            except (TypeError, ValueError):
                return str(valor)
        return "" if valor is None else str(valor)

    def _aplicar(self) -> None:
        termos = fmt.normalizar_busca(self._texto_busca()).split()
        registros = self._registros
        if self._ordem:
            chave, reverso = self._ordem
            registros = sorted(registros, key=lambda r: _chave_ordenacao(r.get(chave)), reverse=reverso)
        self.tree.delete(*self.tree.get_children())
        self._visiveis = {}
        for indice, registro in enumerate(registros):
            textos = [self._formatar(c, registro) for c in self.colunas]
            if termos:
                alvo = fmt.normalizar_busca(" ".join(textos))
                if not all(t in alvo for t in termos):
                    continue
            iid = str(registro.get(self.chave_id, indice))
            tags = self._tag_func(registro) if self._tag_func else None
            if isinstance(tags, str):
                tags = (tags,)
            self.tree.insert("", "end", iid=iid, values=textos, tags=tags or ())
            self._visiveis[iid] = registro
        total, visiveis = len(self._registros), len(self._visiveis)
        self.lbl_contagem.configure(text=f"{visiveis} de {total} registro(s)" if termos else f"{total} registro(s)")

    def _ordenar(self, chave: str) -> None:
        reverso = bool(self._ordem and self._ordem[0] == chave and not self._ordem[1])
        self._ordem = (chave, reverso)
        for c in self.colunas:
            seta = (" ▼" if reverso else " ▲") if c.chave == chave else ""
            self.tree.heading(c.chave, text=c.titulo + seta)
        self._aplicar()

    # ------------------------------------------------------------- seleção
    def selecionado(self) -> dict | None:
        selecao = self.tree.selection()
        return self._visiveis.get(selecao[0]) if selecao else None

    def selecionar_id(self, valor) -> None:
        iid = str(valor)
        if iid in self._visiveis:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    def focar_busca(self) -> None:
        if hasattr(self, "entry_busca"):
            self.entry_busca.focus_set()
            self.entry_busca.select_range(0, "end")

    def focar_tabela(self) -> None:
        filhos = self.tree.get_children()
        if filhos:
            if not self.tree.selection():
                self.tree.selection_set(filhos[0])
                self.tree.focus(filhos[0])
            self.tree.focus_set()

    def _abrir(self, _evento=None):
        registro = self.selecionado()
        if registro and self.ao_abrir:
            self.ao_abrir(registro)
        return "break"

    def _selecionar(self, _evento=None):
        if self.ao_selecionar:
            self.ao_selecionar(self.selecionado())


def _chave_ordenacao(valor):
    """Ordena com segurança valores mistos (None vai para o fim)."""
    if valor is None:
        return (2, "")
    if isinstance(valor, (int, float)):
        return (0, valor)
    return (1, fmt.normalizar_busca(str(valor)))


# ============================================================== DialogoModal
class DialogoModal(ttk.Toplevel):
    """Janela modal que devolve o "foco exclusivo" (grab) à janela anterior ao fechar.

    Sem isso, abrir um diálogo a partir de outro diálogo liberaria a janela
    principal para cliques quando o segundo fosse fechado.
    """

    def __init__(self, master, titulo: str, **kw):
        super().__init__(title=titulo, transient=master.winfo_toplevel(), **kw)
        self.withdraw()
        self._grab_anterior = master.winfo_toplevel().grab_current()
        self.bind("<Escape>", lambda _e: self.destroy())

    def exibir(self, centralizar: bool = True) -> None:
        if centralizar:
            self.place_window_center()
        self.deiconify()
        self.lift()
        self.grab_set()

    def destroy(self):
        anterior = self._grab_anterior
        super().destroy()
        try:
            if anterior is not None and anterior.winfo_exists():
                anterior.grab_set()
                anterior.focus_force()
        except tk.TclError:
            pass


# ========================================================= FormularioDialog
@dataclass
class Campo:
    """Definição de um campo de formulário."""

    chave: str
    rotulo: str
    tipo: str = "texto"  # texto | senha | combo | combo_busca | multilinha | moeda | numero
    obrigatorio: bool = False
    opcoes: list = field(default_factory=list)  # combo: [(valor, rotulo)] ou [rotulo]
    mascara: str | None = None  # chave de MASCARAS
    largura: int = 32
    dica: str = ""
    linha_inteira: bool = False  # ocupa as duas colunas no layout de 2 colunas


class FormularioDialog(DialogoModal):
    """Janela modal de cadastro/edição.

    ``ao_salvar(dados: dict)`` recebe os valores digitados. Se levantar uma
    exceção de negócio, a mensagem é exibida e a janela continua aberta (com o
    foco no campo com problema, quando identificado).
    """

    def __init__(self, master, titulo: str, campos: list[Campo], ao_salvar: Callable[[dict], None],
                 valores: dict | None = None, colunas: int = 1, texto_botao: str = "Salvar",
                 subtitulo: str | None = None, mensagem_sucesso: str | None = "Registro salvo com sucesso."):
        super().__init__(master, titulo, resizable=(False, False))
        self.campos = campos
        self.ao_salvar = ao_salvar
        self.mensagem_sucesso = mensagem_sucesso
        self.widgets: dict[str, tk.Widget] = {}
        valores = valores or {}

        moldura = ttk.Frame(self, padding=20)
        moldura.pack(fill="both", expand=True)
        ttk.Label(moldura, text=titulo, font=(FONTE, 15, "bold")).grid(row=0, column=0, columnspan=colunas,
                                                                       sticky="w")
        if subtitulo:
            ttk.Label(moldura, text=subtitulo, bootstyle="secondary").grid(row=1, column=0, columnspan=colunas,
                                                                          sticky="w")
        ttk.Separator(moldura).grid(row=2, column=0, columnspan=colunas, sticky="ew", pady=10)

        linha, coluna = 3, 0
        for campo in campos:
            if campo.linha_inteira and coluna:
                linha, coluna = linha + 2, 0
            span = colunas if campo.linha_inteira else 1
            rotulo = campo.rotulo + (" *" if campo.obrigatorio else "")
            ttk.Label(moldura, text=rotulo, font=(FONTE, 9, "bold")).grid(
                row=linha, column=coluna, columnspan=span, sticky="w", padx=(0, 16))
            widget = self._criar_widget(moldura, campo, valores.get(campo.chave))
            widget.grid(row=linha + 1, column=coluna, columnspan=span, sticky="ew", padx=(0, 16), pady=(2, 10))
            self.widgets[campo.chave] = widget
            coluna += span
            if coluna >= colunas:
                linha, coluna = linha + 2, 0

        ttk.Label(moldura, text="* campos obrigatórios   ·   Enter: salvar   ·   Esc: cancelar",
                  bootstyle="secondary", font=(FONTE, 8)).grid(row=linha + 2, column=0, columnspan=colunas,
                                                               sticky="w", pady=(4, 0))
        botoes = ttk.Frame(moldura)
        botoes.grid(row=linha + 3, column=0, columnspan=colunas, sticky="e", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", bootstyle="secondary-outline", command=self.destroy).pack(side="right")
        ttk.Button(botoes, text=texto_botao, bootstyle="success", command=self._salvar).pack(side="right", padx=8)

        self.bind("<Return>", self._enter)
        self.exibir()
        primeiro = next(iter(self.widgets.values()), None)
        if primeiro is not None:
            primeiro.focus_set()

    def _criar_widget(self, master, campo: Campo, valor):
        if campo.tipo == "multilinha":
            widget = tk.Text(master, width=campo.largura, height=4, wrap="word", font=(FONTE, 10),
                             relief="solid", borderwidth=1)
            if valor:
                widget.insert("1.0", str(valor))
            return widget
        if campo.tipo in ("combo", "combo_busca"):
            opcoes = [o if isinstance(o, tuple) else (o, o) for o in campo.opcoes]
            if campo.tipo == "combo_busca":
                widget = ComboBusca(master, opcoes, width=campo.largura)
            else:
                widget = ComboBusca(master, opcoes, width=campo.largura, state="readonly")
            if valor is not None:
                widget.selecionar_valor(valor)
            return widget
        widget = ttk.Entry(master, width=campo.largura, show="•" if campo.tipo == "senha" else "")
        if valor not in (None, ""):
            widget.insert(0, str(valor))
        if campo.mascara:
            aplicar_mascara(widget, MASCARAS[campo.mascara])
        if campo.tipo == "moeda":
            aplicar_formato_moeda(widget)
            widget.configure(justify="right")
        if campo.dica:
            from ttkbootstrap.tooltip import ToolTip
            ToolTip(widget, text=campo.dica)
        return widget

    def valores(self) -> dict:
        dados = {}
        for campo in self.campos:
            widget = self.widgets[campo.chave]
            if isinstance(widget, tk.Text):
                dados[campo.chave] = widget.get("1.0", "end-1c")
            elif isinstance(widget, ComboBusca):
                dados[campo.chave] = widget.valor()
            else:
                dados[campo.chave] = widget.get()
        return dados

    def _enter(self, evento):
        if isinstance(evento.widget, tk.Text):
            return None  # Enter quebra linha nos campos de texto longo
        self._salvar()
        return "break"

    def _salvar(self):
        dados = self.valores()
        for campo in self.campos:  # obrigatoriedade básica antes de chamar o serviço
            if campo.obrigatorio and (dados.get(campo.chave) in (None, "") or not str(dados[campo.chave]).strip()):
                self.widgets[campo.chave].focus_set()
                raise ValidacaoError(f"Preencha o campo '{campo.rotulo}'.", campo.chave)
        try:
            self.ao_salvar(dados)
        except ValidacaoError as erro:
            if erro.campo in self.widgets:
                self.widgets[erro.campo].focus_set()
            raise
        self.destroy()
        if self.mensagem_sucesso:
            notificar(self.mensagem_sucesso)


# ================================================================ Indicador
class CardIndicador(ttk.Frame):
    """Cartão do dashboard: número grande + legenda, opcionalmente clicável."""

    def __init__(self, master, titulo: str, valor: str, cor: str = "primary", ao_clicar: Callable | None = None,
                 detalhe: str = ""):
        super().__init__(master, bootstyle=cor, padding=2)
        interno = ttk.Frame(self, padding=(16, 12))
        interno.pack(fill="both", expand=True)
        self.lbl_titulo = ttk.Label(interno, text=titulo.upper(), font=(FONTE, 8, "bold"), bootstyle="secondary")
        self.lbl_titulo.pack(anchor="w")
        self.lbl_valor = ttk.Label(interno, text=valor, font=(FONTE, 22, "bold"), bootstyle=cor)
        self.lbl_valor.pack(anchor="w", pady=(2, 0))
        self.lbl_detalhe = ttk.Label(interno, text=detalhe, font=(FONTE, 8), bootstyle="secondary")
        self.lbl_detalhe.pack(anchor="w")
        if ao_clicar:
            for w in (self, interno, self.lbl_titulo, self.lbl_valor, self.lbl_detalhe):
                w.bind("<Button-1>", lambda _e: ao_clicar())
                w.configure(cursor="hand2")


def titulo_secao(master, texto: str, subtitulo: str = "") -> ttk.Frame:
    quadro = ttk.Frame(master)
    ttk.Label(quadro, text=texto, font=(FONTE, 12, "bold")).pack(anchor="w")
    if subtitulo:
        ttk.Label(quadro, text=subtitulo, bootstyle="secondary", font=(FONTE, 9)).pack(anchor="w")
    return quadro
