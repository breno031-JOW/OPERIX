"""Estoque de peças (cadastro, entradas, ajustes, movimentações) e catálogo de serviços."""

import ttkbootstrap as ttk

from operix.models import Permissao
from operix.ui.shell import View, exigir_selecao
from operix.ui.widgets import (
    FONTE,
    Campo,
    Coluna,
    DialogoModal,
    FormularioDialog,
    TabelaDados,
    confirmar,
    notificar,
)
from operix.utils import formatters as fmt


def _peca_para_form(peca: dict) -> dict:
    return {**peca, "custo": fmt.formatar_moeda(peca["custo_centavos"], simbolo=False),
            "preco": fmt.formatar_moeda(peca["preco_centavos"], simbolo=False),
            "estoque_minimo": fmt.formatar_quantidade(peca["estoque_minimo"])}


class EstoqueView(View):
    titulo = "Estoque e Serviços"
    subtitulo = "Peças com baixa automática nas OS aprovadas"

    def __init__(self, master, shell, apenas_baixo: bool = False):
        super().__init__(master, shell)
        self.catalogo = self.pode(Permissao.GERENCIAR_CATALOGO)
        self.abas = ttk.Notebook(self, bootstyle="primary")
        self.abas.pack(fill="both", expand=True)

        # ------------------------------------------------------------ peças
        aba_pecas = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba_pecas, text="  Peças  ")
        self.var_baixo = ttk.BooleanVar(value=apenas_baixo)
        self.tabela = TabelaDados(aba_pecas, [
            Coluna("codigo", "Código", 100, esticar=False),
            Coluna("descricao", "Descrição", 280),
            Coluna("unidade", "Un.", 50, "center", esticar=False),
            Coluna("estoque", "Saldo", 80, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("estoque_minimo", "Mínimo", 80, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("custo_centavos", "Custo", 100, "e", fmt.formatar_moeda, esticar=False),
            Coluna("preco_centavos", "Venda", 100, "e", fmt.formatar_moeda, esticar=False),
            Coluna("margem", "Margem", 80, "e", lambda m: f"{m:.0f}%" if m is not None else "—", esticar=False),
        ], ao_abrir=self.editar if self.catalogo else None, texto_busca="Código ou descrição (F3)")
        self.tabela.pack(fill="both", expand=True)
        barra = self.tabela.barra
        ttk.Checkbutton(barra, text="Só estoque baixo", variable=self.var_baixo, bootstyle="round-toggle",
                        command=self.atualizar).pack(side="left", padx=(10, 0))
        botoes = []
        if self.catalogo:
            botoes += [("＋ Nova peça (F2)", "success", self.novo), ("Editar", "primary-outline", self.editar)]
        if self.pode(Permissao.MOVIMENTAR_ESTOQUE):
            botoes.append(("⬇ Entrada", "primary", self.entrada))
        if self.catalogo:
            botoes += [("Ajuste de inventário", "warning-outline", self.ajustar),
                       ("Inativar", "secondary-outline", self.inativar)]
        botoes.append(("Movimentações", "info-outline", self.movimentos))
        for texto, estilo, comando in reversed(botoes):
            ttk.Button(barra, text=texto, bootstyle=estilo, command=lambda c=comando: c()).pack(side="right",
                                                                                               padx=(6, 0))

        # ---------------------------------------------------------- serviços
        aba_serv = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba_serv, text="  Catálogo de mão de obra  ")
        self.tabela_serv = TabelaDados(aba_serv, [
            Coluna("descricao", "Serviço", 400),
            Coluna("preco_centavos", "Preço sugerido", 140, "e", fmt.formatar_moeda, esticar=False),
        ], ao_abrir=self.editar_servico if self.catalogo else None)
        self.tabela_serv.pack(fill="both", expand=True)
        if self.catalogo:
            for texto, estilo, comando in (("Inativar", "secondary-outline", self.inativar_servico),
                                           ("Editar", "primary-outline", self.editar_servico),
                                           ("＋ Novo serviço", "success", self.novo_servico)):
                ttk.Button(self.tabela_serv.barra, text=texto, bootstyle=estilo,
                           command=lambda c=comando: c()).pack(side="right", padx=(6, 0))
        self.atualizar()

    def atualizar(self):
        pecas = []
        for p in self.servicos.estoque.listar(apenas_baixo=self.var_baixo.get()):
            pecas.append({**vars(p), "margem": p.margem_percentual, "baixo": p.estoque_baixo})
        self.tabela.carregar(pecas, tag=lambda p: "danger" if p["baixo"] or p["estoque"] <= 0 else None)
        self.tabela_serv.carregar([vars(s) for s in self.servicos.catalogo.listar()])

    def focar_busca(self):
        (self.tabela if self.abas.index("current") == 0 else self.tabela_serv).focar_busca()

    # ------------------------------------------------------------- peças
    def _campos_peca(self, nova: bool) -> list[Campo]:
        campos = [
            Campo("codigo", "Código", obrigatorio=True, largura=16),
            Campo("unidade", "Unidade", "combo", opcoes=["UN", "L", "KG", "JG", "PAR", "M", "CX"], largura=8),
            Campo("descricao", "Descrição", obrigatorio=True, largura=44, linha_inteira=True),
            Campo("custo", "Custo (R$)", "moeda", largura=14),
            Campo("preco", "Preço de venda (R$)", "moeda", True, largura=14),
            Campo("estoque_minimo", "Estoque mínimo", largura=10, dica="Alerta quando o saldo ficar igual ou abaixo"),
        ]
        if nova:
            campos.append(Campo("estoque_inicial", "Estoque inicial", largura=10))
        return campos

    def novo(self):
        if not self.catalogo:
            return
        self.abas.select(0)
        FormularioDialog(self, "Nova peça", self._campos_peca(True),
                         lambda d: (self.servicos.estoque.criar(d), self.atualizar()),
                         valores={"unidade": "UN"}, colunas=2, mensagem_sucesso="Peça cadastrada.")

    def editar(self, registro=None):
        peca = registro or exigir_selecao(self.tabela.selecionado(), "Selecione uma peça.")
        FormularioDialog(self, "Editar peça", self._campos_peca(False),
                         lambda d: (self.servicos.estoque.atualizar(peca["id"], d), self.atualizar()),
                         valores=_peca_para_form(peca), colunas=2,
                         subtitulo="Para alterar o saldo use 'Entrada' ou 'Ajuste de inventário'.")

    def entrada(self):
        peca = exigir_selecao(self.tabela.selecionado(), "Selecione a peça que chegou.")
        FormularioDialog(
            self, "Entrada de mercadoria",
            [Campo("quantidade", "Quantidade recebida", obrigatorio=True, largura=12),
             Campo("custo", "Custo unitário (R$) — opcional", "moeda", largura=14),
             Campo("observacao", "Fornecedor / nota fiscal", largura=36, linha_inteira=True)],
            lambda d: (self.servicos.estoque.entrada(peca["id"], d["quantidade"], d["custo"], d["observacao"]),
                       self.atualizar()),
            colunas=2, subtitulo=f"{peca['codigo']} - {peca['descricao']} · saldo atual "
                                 f"{fmt.formatar_quantidade(peca['estoque'])} {peca['unidade']}",
            texto_botao="Dar entrada", mensagem_sucesso="Entrada registrada.")

    def ajustar(self):
        peca = exigir_selecao(self.tabela.selecionado(), "Selecione uma peça.")
        FormularioDialog(
            self, "Ajuste de inventário",
            [Campo("saldo", "Quantidade contada", obrigatorio=True, largura=12),
             Campo("motivo", "Motivo", obrigatorio=True, largura=36)],
            lambda d: (self.servicos.estoque.ajustar(peca["id"], d["saldo"], d["motivo"]), self.atualizar()),
            colunas=2, subtitulo=f"{peca['descricao']} · saldo no sistema: "
                                 f"{fmt.formatar_quantidade(peca['estoque'])} {peca['unidade']}",
            texto_botao="Ajustar", mensagem_sucesso="Estoque ajustado.")

    def inativar(self):
        peca = exigir_selecao(self.tabela.selecionado(), "Selecione uma peça.")
        if confirmar(self, f"Inativar a peça '{peca['descricao']}'? Ela deixa de aparecer nas buscas."):
            self.servicos.estoque.definir_ativo(peca["id"], False)
            self.atualizar()
            notificar("Peça inativada.")

    def movimentos(self):
        peca = exigir_selecao(self.tabela.selecionado(), "Selecione uma peça.")
        MovimentosDialog(self, peca, self.servicos.estoque.movimentos(peca["id"]))

    # ----------------------------------------------------------- serviços
    def _form_servico(self, servico=None):
        valores = {"descricao": servico["descricao"],
                   "preco": fmt.formatar_moeda(servico["preco_centavos"], simbolo=False)} if servico else None
        FormularioDialog(
            self, "Editar serviço" if servico else "Novo serviço",
            [Campo("descricao", "Descrição", obrigatorio=True, largura=40),
             Campo("preco", "Preço sugerido (R$)", "moeda", largura=14)],
            lambda d: (self.servicos.catalogo.salvar(d, servico["id"] if servico else None), self.atualizar()),
            valores=valores, mensagem_sucesso="Serviço salvo.")

    def novo_servico(self):
        self._form_servico()

    def editar_servico(self, registro=None):
        self._form_servico(registro or exigir_selecao(self.tabela_serv.selecionado(), "Selecione um serviço."))

    def inativar_servico(self):
        servico = exigir_selecao(self.tabela_serv.selecionado(), "Selecione um serviço.")
        if confirmar(self, f"Inativar o serviço '{servico['descricao']}'?"):
            self.servicos.catalogo.definir_ativo(servico["id"], False)
            self.atualizar()


class MovimentosDialog(DialogoModal):
    def __init__(self, master, peca: dict, movimentos):
        super().__init__(master, "Movimentações de estoque", size=(900, 520))
        quadro = ttk.Frame(self, padding=16)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text=f"{peca['codigo']} - {peca['descricao']}", font=(FONTE, 13, "bold")).pack(anchor="w")
        ttk.Label(quadro, text=f"Saldo atual: {fmt.formatar_quantidade(peca['estoque'])} {peca['unidade']}",
                  bootstyle="secondary").pack(anchor="w", pady=(0, 8))
        tabela = TabelaDados(quadro, [
            Coluna("data", "Data", 140, "center", fmt.formatar_data, esticar=False),
            Coluna("tipo", "Tipo", 90, esticar=False),
            Coluna("quantidade", "Qtd.", 80, "e",
                   lambda q: ("+" if q > 0 else "-") + fmt.formatar_quantidade(abs(q)), esticar=False),
            Coluna("saldo_apos", "Saldo após", 90, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("ordem_numero", "OS", 70, "center", lambda n: f"{n:05d}" if n else "", esticar=False),
            Coluna("usuario_nome", "Usuário", 140, formato=lambda n: n or ""),
            Coluna("observacao", "Observação", 220, formato=lambda o: o or ""),
        ], altura=14)
        tabela.pack(fill="both", expand=True)
        tabela.carregar([vars(m) for m in movimentos],
                        tag=lambda m: "success" if m["quantidade"] > 0 else "danger")
        ttk.Button(quadro, text="Fechar", bootstyle="secondary", command=self.destroy).pack(anchor="e", pady=(10, 0))
        self.exibir()
