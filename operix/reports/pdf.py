"""Documentos PDF com ``fpdf2``.

As fontes padrão do PDF (Helvetica) aceitam apenas o alfabeto Latin-1, que
cobre os acentos do português. Caracteres fora dele (travessão, emojis...) são
substituídos por :func:`_t` para o PDF nunca falhar por causa de um texto
digitado pelo usuário.
"""

import logging
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from operix import config
from operix.errors import OperixError
from operix.models import Empresa, OrdemServico, StatusOrdem, TipoItem
from operix.utils import formatters as fmt
from operix.utils import validators as val

log = logging.getLogger(__name__)

_SUBSTITUICOES = {"—": "-", "–": "-", "•": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...",
                  "·": "-", "✔": "", "✖": "", "−": "-"}

TITULOS = {"orcamento": "ORÇAMENTO", "ordem": "ORDEM DE SERVIÇO", "recibo": "RECIBO"}
COR_PRIMARIA = (44, 62, 80)
COR_CLARA = (236, 240, 241)


class ErroDocumento(OperixError):
    titulo = "Erro ao gerar documento"


def _t(texto) -> str:
    """Converte qualquer texto para algo imprimível nas fontes padrão do PDF."""
    texto = "" if texto is None else str(texto)
    for original, troca in _SUBSTITUICOES.items():
        texto = texto.replace(original, troca)
    return texto.encode("latin-1", "replace").decode("latin-1")


class _DocumentoBase(FPDF):
    def __init__(self, empresa: Empresa, titulo: str, subtitulo: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.empresa = empresa
        self.titulo_doc = titulo
        self.subtitulo_doc = subtitulo
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(14, 14, 14)
        self.alias_nb_pages()
        self.add_page()

    def header(self):
        e = self.empresa
        self.set_fill_color(*COR_PRIMARIA)
        self.rect(0, 0, 210, 4, "F")
        self.set_y(9)
        self.set_font("helvetica", "B", 15)
        self.set_text_color(*COR_PRIMARIA)
        self.cell(120, 7, _t(e.nome), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("helvetica", "B", 13)
        self.cell(0, 7, _t(self.titulo_doc), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(90, 90, 90)
        linha1 = " | ".join(x for x in (f"CNPJ {val.formatar_documento(e.cnpj)}" if e.cnpj else "",
                                        val.formatar_telefone(e.telefone), e.email or "") if x)
        self.cell(120, 4.5, _t(linha1), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 4.5, _t(self.subtitulo_doc), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if e.endereco:
            self.cell(0, 4.5, _t(e.endereco), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
        self.set_draw_color(*COR_PRIMARIA)
        self.line(14, self.get_y(), 196, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", "I", 7.5)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, _t(f"Gerado pelo {config.APP_NOME} em {datetime.now():%d/%m/%Y %H:%M}"),
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")

    # ----------------------------------------------------------- utilidades
    def secao(self, texto: str):
        self.ln(2)
        self.set_fill_color(*COR_CLARA)
        self.set_font("helvetica", "B", 9.5)
        self.cell(0, 6, _t("  " + texto.upper()), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)
        self.set_font("helvetica", "", 9.5)

    def campo(self, rotulo: str, valor, largura: float = 0, quebra: bool = True):
        self.set_font("helvetica", "B", 9)
        self.cell(self.get_string_width(_t(rotulo)) + 2, 5.5, _t(rotulo), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("helvetica", "", 9)
        restante = largura - self.get_string_width(_t(rotulo)) - 2 if largura else 0
        self.cell(restante, 5.5, _t(valor), new_x=XPos.LMARGIN if quebra else XPos.RIGHT,
                  new_y=YPos.NEXT if quebra else YPos.TOP)

    def tabela(self, cabecalho: list[tuple[str, float, str]], linhas: list[list[str]]):
        """``cabecalho`` = [(titulo, largura_mm, alinhamento)]."""
        self.set_font("helvetica", "B", 8.5)
        self.set_fill_color(*COR_PRIMARIA)
        self.set_text_color(255, 255, 255)
        for titulo, largura, alinhamento in cabecalho:
            self.cell(largura, 6.5, _t(titulo), border=0, align=alinhamento, fill=True,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("helvetica", "", 8.5)
        for indice, linha in enumerate(linhas):
            if self.will_page_break(6):
                self.add_page()
            self.set_fill_color(*(COR_CLARA if indice % 2 else (255, 255, 255)))
            for (_titulo, largura, alinhamento), valor in zip(cabecalho, linha, strict=False):
                texto = _t(valor)
                while texto and self.get_string_width(texto) > largura - 2:
                    texto = texto[:-1]  # corta textos longos para caber na célula
                self.cell(largura, 6, texto, align=alinhamento, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.ln()

    def texto_longo(self, texto: str):
        self.set_font("helvetica", "", 9)
        self.multi_cell(0, 5, _t(texto or "-"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def assinaturas(self, esquerda: str, direita: str):
        if self.will_page_break(30):
            self.add_page()
        self.ln(18)
        y = self.get_y()
        self.line(20, y, 95, y)
        self.line(115, y, 190, y)
        self.set_font("helvetica", "", 8.5)
        self.set_xy(20, y + 1)
        self.cell(75, 5, _t(esquerda), align="C")
        self.set_xy(115, y + 1)
        self.cell(75, 5, _t(direita), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _caminho_saida(nome: str) -> Path:
    pasta = Path(config.PASTA_DOCUMENTOS)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as erro:
        raise ErroDocumento(f"Não foi possível criar a pasta de documentos:\n{pasta}") from erro
    return pasta / nome


def _salvar(pdf: FPDF, caminho: Path) -> Path:
    try:
        pdf.output(str(caminho))
    except PermissionError as erro:
        raise ErroDocumento(
            f"O arquivo está aberto em outro programa. Feche o PDF e tente novamente.\n{caminho}") from erro
    except OSError as erro:
        raise ErroDocumento(f"Não foi possível salvar o PDF:\n{caminho}") from erro
    log.info("PDF gerado: %s", caminho)
    return caminho


def gerar_pdf_ordem(ordem: OrdemServico, empresa: Empresa, tipo: str = "orcamento") -> Path:
    """Gera orçamento, ordem de serviço ou recibo de uma OS e retorna o caminho do arquivo."""
    if tipo not in TITULOS:
        raise ValueError(tipo)
    status = ordem.status_enum
    pdf = _DocumentoBase(empresa, f"{TITULOS[tipo]} Nº {ordem.numero_formatado}",
                         f"Emissão: {date.today():%d/%m/%Y}   Situação: {status.rotulo}")

    # Cliente e veículo
    pdf.secao("Cliente e veículo")
    pdf.campo("Cliente: ", ordem.cliente_nome, 110, quebra=False)
    pdf.campo("CPF/CNPJ: ", val.formatar_documento(ordem.cliente_documento))
    pdf.campo("Telefone: ", val.formatar_telefone(ordem.cliente_telefone) or "-", 110, quebra=False)
    pdf.campo("Abertura: ", fmt.formatar_data(ordem.criado_em))
    pdf.campo("Veículo: ", f"{val.formatar_placa(ordem.veiculo_placa)} - {ordem.veiculo_descricao or ''}", 110,
              quebra=False)
    pdf.campo("Km: ", f"{ordem.km_entrada:,}".replace(",", ".") if ordem.km_entrada else "-")
    if tipo != "recibo" and ordem.mecanico_nome:
        pdf.campo("Mecânico responsável: ", ordem.mecanico_nome)

    if tipo != "recibo":
        pdf.secao("Defeito relatado")
        pdf.texto_longo(ordem.defeito_relatado)
        if tipo == "ordem" or ordem.diagnostico:
            pdf.secao("Diagnóstico / serviço executado")
            pdf.texto_longo(ordem.diagnostico)

    # Itens
    pdf.secao("Peças e mão de obra")
    linhas = [[TipoItem(i.tipo).rotulo, i.descricao, fmt.formatar_quantidade(i.quantidade),
               fmt.formatar_moeda(i.valor_unitario_centavos), fmt.formatar_moeda(i.total_centavos)]
              for i in ordem.itens]
    pdf.tabela([("Tipo", 24, "L"), ("Descrição", 92, "L"), ("Qtd.", 16, "R"), ("Unitário", 25, "R"),
                ("Total", 25, "R")], linhas or [["-", "Nenhum item lançado", "", "", ""]])

    # Totais
    pdf.ln(2)
    totais = [("Peças", ordem.total_pecas), ("Mão de obra", ordem.total_servicos)]
    if ordem.desconto_centavos:
        totais.append(("Desconto", -ordem.desconto_centavos))
    totais.append(("TOTAL", ordem.total))
    if tipo == "recibo" or ordem.total_pago:
        totais += [("Pago", ordem.total_pago), ("Saldo", ordem.saldo)]
    for rotulo, valor in totais:
        destaque = rotulo in ("TOTAL", "Saldo")
        pdf.set_font("helvetica", "B" if destaque else "", 10.5 if destaque else 9.5)
        pdf.cell(150, 6, _t(rotulo), align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(32, 6, _t(fmt.formatar_moeda(valor)), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if tipo == "recibo":
        pdf.secao("Pagamentos recebidos")
        pdf.tabela([("Data", 40, "L"), ("Forma", 60, "L"), ("Observação", 52, "L"), ("Valor", 30, "R")],
                   [[fmt.formatar_data(p.data), p.forma, p.observacao or "", fmt.formatar_moeda(p.valor_centavos)]
                    for p in ordem.pagamentos])
        pdf.ln(4)
        pdf.texto_longo(
            f"Recebemos de {ordem.cliente_nome} a quantia de {fmt.formatar_moeda(ordem.total_pago)} referente aos "
            f"serviços da OS nº {ordem.numero_formatado} no veículo {val.formatar_placa(ordem.veiculo_placa)}."
            + (f" Saldo restante: {fmt.formatar_moeda(ordem.saldo)}." if ordem.saldo else " Quitado."))
        pdf.assinaturas(empresa.nome, "Cliente")
    elif tipo == "orcamento":
        pdf.ln(3)
        pdf.set_font("helvetica", "I", 8.5)
        pdf.multi_cell(0, 4.5, _t("Orçamento válido por 7 dias. Peças sujeitas à disponibilidade em estoque. "
                                  "Serviços adicionais só serão executados com autorização do cliente."),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.assinaturas("Responsável pela oficina", "Autorização do cliente")
    else:
        pdf.ln(3)
        pdf.set_font("helvetica", "I", 8.5)
        pdf.multi_cell(0, 4.5, _t("Garantia de 90 dias para serviços executados, conforme o Código de Defesa do "
                                  "Consumidor. Peças conforme garantia do fabricante."),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.assinaturas("Responsável técnico", "Cliente (retirada do veículo)")

    if status is StatusOrdem.CANCELADA:
        pdf.set_font("helvetica", "B", 50)
        pdf.set_text_color(220, 80, 80)
        with pdf.rotation(30, 105, 150):
            pdf.text(45, 160, "CANCELADA")

    nome = f"{tipo}_{ordem.numero_formatado}_{val.normalizar_placa(ordem.veiculo_placa)}.pdf"
    return _salvar(pdf, _caminho_saida(nome))


def gerar_relatorio_financeiro(dados: dict, periodo: tuple[date, date], empresa: Empresa) -> Path:
    inicio, fim = periodo
    pdf = _DocumentoBase(empresa, "RELATÓRIO FINANCEIRO", f"Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")
    pdf.secao("Resumo")
    for rotulo, valor in (("Recebido no período", dados["recebido"]),
                          ("Faturado (OS concluídas)", dados["faturado"]),
                          ("Quantidade de OS concluídas", None),
                          ("Ticket médio", dados["ticket_medio"]),
                          ("Receita de peças", dados["receita_pecas"]),
                          ("Receita de mão de obra (líquida)", dados["receita_servicos"]),
                          ("Lucro bruto em peças", dados["lucro_bruto_pecas"]),
                          ("Total a receber (todas as OS)", dados["a_receber_total"])):
        texto = str(dados["qtd_finalizadas"]) if valor is None else fmt.formatar_moeda(valor)
        pdf.campo(f"{rotulo}: ", texto)

    pdf.secao("Recebimentos por forma de pagamento")
    pdf.tabela([("Forma", 100, "L"), ("Qtd.", 30, "R"), ("Total", 52, "R")],
               [[f["forma"], str(f["qtd"]), fmt.formatar_moeda(f["total"])] for f in dados["por_forma"]]
               or [["Nenhum recebimento no período", "", ""]])
    pdf.secao("Contas a receber")
    pdf.tabela([("OS", 18, "C"), ("Cliente", 70, "L"), ("Telefone", 32, "L"), ("Situação", 32, "L"),
                ("Saldo", 30, "R")],
               [[f"{r['numero']:05d}", r["cliente_nome"], val.formatar_telefone(r["telefone"]),
                 StatusOrdem(r["status"]).rotulo, fmt.formatar_moeda(r["saldo"])] for r in dados["a_receber"]]
               or [["", "Nenhuma pendência", "", "", ""]])
    pdf.secao("Peças mais utilizadas")
    pdf.tabela([("Peça", 120, "L"), ("Qtd.", 25, "R"), ("Total", 37, "R")],
               [[p["descricao"], fmt.formatar_quantidade(p["quantidade"]), fmt.formatar_moeda(p["total"])]
                for p in dados["top_pecas"]] or [["Nenhuma peça no período", "", ""]])
    return _salvar(pdf, _caminho_saida(f"financeiro_{inicio:%Y%m%d}_{fim:%Y%m%d}.pdf"))


def abrir_arquivo(caminho: Path) -> None:
    """Abre o PDF no visualizador padrão do sistema (sem travar se não houver)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(caminho)])
        else:
            subprocess.Popen(["xdg-open", str(caminho)])
    except OSError:
        log.warning("Não foi possível abrir o PDF automaticamente: %s", caminho)
