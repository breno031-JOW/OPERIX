"""Dashboard financeiro (somente administrador)."""

from datetime import date, datetime, timedelta

import ttkbootstrap as ttk
from ttkbootstrap.widgets import DateEntry

from operix.errors import ValidacaoError
from operix.models import StatusOrdem
from operix.services.dashboard import periodo_mes_atual
from operix.ui.shell import View
from operix.ui.views.ordens import abrir_ordem
from operix.ui.widgets import CardIndicador, Coluna, TabelaDados, notificar, titulo_secao
from operix.utils import formatters as fmt
from operix.utils import validators as val

FORMATO = "%d/%m/%Y"


class FinanceiroView(View):
    titulo = "Financeiro"
    subtitulo = "Recebimentos, faturamento e contas a receber"

    def __init__(self, master, shell):
        super().__init__(master, shell)
        self.botao_acao("📄 Relatório PDF", self.gerar_pdf, "secondary-outline")

        periodo = ttk.Frame(self)
        periodo.pack(fill="x", pady=(0, 14))
        inicio, fim = periodo_mes_atual()
        ttk.Label(periodo, text="De").pack(side="left")
        self.ent_inicio = DateEntry(periodo, dateformat=FORMATO, startdate=datetime.combine(inicio, datetime.min.time()),
                                    width=12)
        self.ent_inicio.pack(side="left", padx=6)
        ttk.Label(periodo, text="até").pack(side="left")
        self.ent_fim = DateEntry(periodo, dateformat=FORMATO, startdate=datetime.combine(fim, datetime.min.time()),
                                 width=12)
        self.ent_fim.pack(side="left", padx=6)
        ttk.Button(periodo, text="Aplicar", bootstyle="primary", command=self.atualizar).pack(side="left", padx=6)
        ttk.Button(periodo, text="Este mês", bootstyle="link", command=lambda: self._mes(0)).pack(side="left")
        ttk.Button(periodo, text="Mês anterior", bootstyle="link", command=lambda: self._mes(-1)).pack(side="left")

        self.cards = ttk.Frame(self)
        self.cards.pack(fill="x")

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True, pady=(16, 0))
        corpo.columnconfigure(0, weight=3)
        corpo.columnconfigure(1, weight=2)
        corpo.rowconfigure(1, weight=1)
        corpo.rowconfigure(3, weight=1)

        titulo_secao(corpo, "Contas a receber", "OS aprovadas/entregues com saldo · duplo clique abre a OS").grid(
            row=0, column=0, sticky="w")
        self.tabela_receber = TabelaDados(corpo, [
            Coluna("numero", "Nº OS", 70, "center", lambda n: f"{n:05d}", esticar=False),
            Coluna("cliente_nome", "Cliente", 200),
            Coluna("telefone", "Telefone", 130, formato=val.formatar_telefone, esticar=False),
            Coluna("placa", "Placa", 90, "center", val.formatar_placa, esticar=False),
            Coluna("status", "Status", 120, formato=lambda s: StatusOrdem(s).rotulo, esticar=False),
            Coluna("saldo", "Saldo", 110, "e", fmt.formatar_moeda, esticar=False),
        ], ao_abrir=lambda r: abrir_ordem(self, r["id"], self.atualizar), altura=8)
        self.tabela_receber.grid(row=1, column=0, rowspan=3, sticky="nsew", padx=(0, 16))

        titulo_secao(corpo, "Recebimentos por forma de pagamento").grid(row=0, column=1, sticky="w")
        self.tabela_formas = TabelaDados(corpo, [
            Coluna("forma", "Forma", 150), Coluna("qtd", "Qtd.", 60, "e", esticar=False),
            Coluna("total", "Total", 120, "e", fmt.formatar_moeda, esticar=False),
        ], com_busca=False, altura=5)
        self.tabela_formas.grid(row=1, column=1, sticky="nsew")
        titulo_secao(corpo, "Peças mais utilizadas no período").grid(row=2, column=1, sticky="w", pady=(10, 0))
        self.tabela_pecas = TabelaDados(corpo, [
            Coluna("descricao", "Peça", 200),
            Coluna("quantidade", "Qtd.", 60, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("total", "Total", 110, "e", fmt.formatar_moeda, esticar=False),
        ], com_busca=False, altura=5, chave_id="descricao")
        self.tabela_pecas.grid(row=3, column=1, sticky="nsew")
        self.atualizar()

    def _periodo(self) -> tuple[date, date]:
        try:
            inicio = datetime.strptime(self.ent_inicio.entry.get(), FORMATO).date()
            fim = datetime.strptime(self.ent_fim.entry.get(), FORMATO).date()
        except ValueError:
            raise ValidacaoError("Data inválida. Use o formato dd/mm/aaaa.") from None
        if inicio > fim:
            raise ValidacaoError("A data inicial deve ser anterior à data final.")
        return inicio, fim

    def _mes(self, deslocamento: int):
        inicio, fim = periodo_mes_atual()
        if deslocamento:
            fim = inicio - timedelta(days=1)
            inicio = fim.replace(day=1)
        for entrada, valor in ((self.ent_inicio, inicio), (self.ent_fim, fim)):
            entrada.entry.delete(0, "end")
            entrada.entry.insert(0, valor.strftime(FORMATO))
        self.atualizar()

    def atualizar(self):
        inicio, fim = self._periodo()
        dados = self.dados = self.servicos.dashboard.financeiro(inicio, fim)
        self.periodo = (inicio, fim)
        for filho in self.cards.winfo_children():
            filho.destroy()
        cartoes = [
            ("Recebido no período", dados["recebido"], "success", "pagamentos registrados"),
            ("Faturado (OS concluídas)", dados["faturado"], "primary", f"{dados['qtd_finalizadas']} OS"),
            ("Ticket médio", dados["ticket_medio"], "info", "por OS concluída"),
            ("A receber", dados["a_receber_total"], "danger" if dados["a_receber_total"] else "secondary",
             f"{len(dados['a_receber'])} OS com saldo"),
            ("Mão de obra", dados["receita_servicos"], "primary", "líquido de descontos"),
            ("Lucro bruto em peças", dados["lucro_bruto_pecas"], "success",
             f"venda {fmt.formatar_moeda(dados['receita_pecas'])}"),
        ]
        for indice, (titulo, valor, cor, detalhe) in enumerate(cartoes):
            coluna = indice % 3
            CardIndicador(self.cards, titulo, fmt.formatar_moeda(valor), cor, detalhe=detalhe).grid(
                row=indice // 3, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 10, 0), pady=(0, 10))
            self.cards.columnconfigure(coluna, weight=1, uniform="fin")
        self.tabela_receber.carregar(dados["a_receber"],
                                     tag=lambda r: "danger" if r["status"] == "ENTREGUE" else None)
        self.tabela_formas.carregar([{**f, "id": f["forma"]} for f in dados["por_forma"]])
        self.tabela_pecas.carregar(dados["top_pecas"])

    def gerar_pdf(self):
        from operix.reports.pdf import abrir_arquivo, gerar_relatorio_financeiro

        caminho = gerar_relatorio_financeiro(self.dados, self.periodo, self.servicos.empresa.obter())
        notificar(f"Relatório salvo em {caminho.parent}", "Relatório gerado", "info")
        abrir_arquivo(caminho)
