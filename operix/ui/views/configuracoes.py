"""Dados da oficina (usados no cabeçalho dos PDFs)."""

import ttkbootstrap as ttk

from operix import config
from operix.ui.shell import View
from operix.ui.widgets import FONTE, MASCARAS, aplicar_mascara, notificar
from operix.utils import validators as val


class ConfiguracoesView(View):
    titulo = "Dados da oficina"
    subtitulo = "Aparecem nos orçamentos, ordens de serviço e recibos em PDF"

    def __init__(self, master, shell):
        super().__init__(master, shell)
        quadro = ttk.Labelframe(self, text=" Identificação ", padding=20, bootstyle="primary")
        quadro.pack(anchor="nw")
        empresa = self.servicos.empresa.obter()
        valores = {"nome": empresa.nome, "cnpj": val.formatar_documento(empresa.cnpj),
                   "telefone": val.formatar_telefone(empresa.telefone), "email": empresa.email or "",
                   "endereco": empresa.endereco or ""}
        self.campos = {}
        for linha, (chave, rotulo, mascara) in enumerate((
                ("nome", "Nome da oficina *", None), ("cnpj", "CNPJ", "cnpj"), ("telefone", "Telefone", "telefone"),
                ("email", "E-mail", None), ("endereco", "Endereço completo", None))):
            ttk.Label(quadro, text=rotulo, font=(FONTE, 9, "bold")).grid(row=linha * 2, column=0, sticky="w")
            entrada = ttk.Entry(quadro, width=60)
            entrada.insert(0, valores[chave])
            if mascara:
                aplicar_mascara(entrada, MASCARAS[mascara])
            entrada.grid(row=linha * 2 + 1, column=0, sticky="ew", pady=(2, 10))
            self.campos[chave] = entrada
        ttk.Button(quadro, text="Salvar", bootstyle="success", command=self.salvar).grid(row=20, column=0, sticky="e")

        info = ttk.Labelframe(self, text=" Arquivos do sistema ", padding=20, bootstyle="secondary")
        info.pack(anchor="nw", fill="x", pady=(16, 0))
        for rotulo, caminho in (("Banco de dados", self.servicos.db.caminho), ("PDFs gerados", config.PASTA_DOCUMENTOS),
                                ("Log de erros", config.CAMINHO_LOG)):
            ttk.Label(info, text=f"{rotulo}: {caminho}", bootstyle="secondary").pack(anchor="w")
        ttk.Label(info, text="Dica: faça cópia de segurança do arquivo do banco de dados regularmente.",
                  bootstyle="info").pack(anchor="w", pady=(8, 0))

    def salvar(self):
        empresa = self.servicos.empresa.atualizar({k: e.get() for k, e in self.campos.items()})
        notificar("Dados da oficina atualizados.")
        self.shell.winfo_toplevel().title(f"{config.APP_NOME} · {empresa.nome}")
