"""Histórico completo de um veículo pela placa."""

import ttkbootstrap as ttk

from operix.models import StatusOrdem
from operix.ui.shell import View
from operix.ui.views.ordens import abrir_ordem, tag_status
from operix.ui.widgets import FONTE, MASCARAS, Coluna, TabelaDados, aplicar_mascara, titulo_secao
from operix.utils import formatters as fmt
from operix.utils import validators as val


class HistoricoPlacaView(View):
    titulo = "Histórico por placa"
    subtitulo = "Tudo o que já foi feito no veículo"

    def __init__(self, master, shell, placa: str | None = None):
        super().__init__(master, shell)
        busca = ttk.Frame(self)
        busca.pack(fill="x")
        ttk.Label(busca, text="Placa:", font=(FONTE, 11, "bold")).pack(side="left")
        self.ent_placa = ttk.Entry(busca, width=12, font=(FONTE, 14, "bold"), justify="center")
        aplicar_mascara(self.ent_placa, MASCARAS["placa"])
        self.ent_placa.pack(side="left", padx=8)
        self.ent_placa.bind("<Return>", lambda _e: self.buscar())
        ttk.Button(busca, text="Buscar", bootstyle="primary", command=self.buscar).pack(side="left")

        self.lbl_veiculo = ttk.Label(self, font=(FONTE, 12, "bold"))
        self.lbl_veiculo.pack(anchor="w", pady=(16, 0))
        self.lbl_resumo = ttk.Label(self, bootstyle="secondary")
        self.lbl_resumo.pack(anchor="w", pady=(0, 10))

        titulo_secao(self, "Ordens de serviço do veículo", "Duplo clique para abrir a OS").pack(anchor="w")
        self.tabela = TabelaDados(self, [
            Coluna("numero", "Nº OS", 70, "center", lambda n: f"{n:05d}", esticar=False),
            Coluna("criado_em", "Data", 100, "center", lambda d: fmt.formatar_data(d, com_hora=False), esticar=False),
            Coluna("status", "Status", 120, formato=lambda s: StatusOrdem(s).rotulo, esticar=False),
            Coluna("km_entrada", "Km", 90, "e", lambda k: f"{k:,}".replace(",", ".") if k else "—", esticar=False),
            Coluna("servicos", "Serviços", 240, formato=lambda x: x or ""),
            Coluna("pecas", "Peças trocadas", 260, formato=lambda x: x or ""),
            Coluna("total", "Total", 110, "e", fmt.formatar_moeda, esticar=False),
        ], ao_abrir=lambda r: abrir_ordem(self, r["id"], self.buscar), texto_busca="Filtrar no histórico")
        self.tabela.pack(fill="both", expand=True)

        if placa:
            self.ent_placa.insert(0, val.formatar_placa(placa))
            self.buscar()
        else:
            self.after(100, self.ent_placa.focus_set)

    def focar_busca(self):
        self.ent_placa.focus_set()
        self.ent_placa.select_range(0, "end")

    def atualizar(self):
        self.buscar()

    def buscar(self):
        texto = self.ent_placa.get()
        if not texto.strip():
            return
        placa = val.validar_placa(texto)
        veiculo = self.servicos.veiculos.buscar_por_placa(placa)
        if not veiculo:
            self.lbl_veiculo.configure(text=f"Nenhum veículo cadastrado com a placa {val.formatar_placa(placa)}.")
            self.lbl_resumo.configure(text="")
            self.tabela.carregar([])
            return
        cliente = self.servicos.clientes.obter(veiculo.cliente_id)
        historico = self.servicos.veiculos.historico(veiculo.id)
        self.lbl_veiculo.configure(text=f"🚗 {veiculo.descricao()}   ·   Proprietário: {cliente.nome}")
        validas = [h for h in historico if h["status"] in ("CONCLUIDA", "ENTREGUE")]
        ultima = fmt.formatar_data(validas[0]["criado_em"], com_hora=False) if validas else "—"
        km = f"{veiculo.km_atual or 0:,}".replace(",", ".")
        self.lbl_resumo.configure(
            text=f"{len(historico)} OS no total   ·   {len(validas)} concluída(s)   ·   "
                 f"Gasto total: {fmt.formatar_moeda(sum(h['total'] for h in validas))}   ·   "
                 f"Último serviço: {ultima}   ·   Km atual: {km}")
        self.tabela.carregar(historico, tag=tag_status)
