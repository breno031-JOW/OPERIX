"""Geração dos PDFs (orçamento, OS, recibo e relatório financeiro)."""

from operix import config
from operix.models import StatusOrdem as S
from operix.reports.pdf import _t, gerar_pdf_ordem, gerar_relatorio_financeiro
from operix.services.dashboard import periodo_mes_atual


def test_texto_fora_do_latin1_nao_quebra():
    assert _t("Troca — óleo • 5W30 🚗") == "Troca - óleo - 5W30 ?"


def test_pdfs_da_ordem(admin, cenario, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PASTA_DOCUMENTOS", tmp_path / "docs")
    o = admin.ordens.criar({"cliente_id": cenario["cliente"], "veiculo_id": cenario["veiculo"],
                            "defeito_relatado": "Barulho — no freio 🚗"})
    admin.ordens.adicionar_peca(o, cenario["oleo"], "4,5")
    admin.ordens.adicionar_servico(o, "Mão de obra com descrição bem longa " * 4, 1, "150")
    admin.ordens.alterar_status(o, S.APROVADA)
    admin.ordens.registrar_pagamento(o, "100", "PIX")
    ordem = admin.ordens.obter(o)
    empresa = admin.empresa.obter()
    for tipo in ("orcamento", "ordem", "recibo"):
        caminho = gerar_pdf_ordem(ordem, empresa, tipo)
        assert caminho.exists() and caminho.read_bytes()[:4] == b"%PDF"


def test_relatorio_financeiro(admin, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PASTA_DOCUMENTOS", tmp_path / "docs")
    periodo = periodo_mes_atual()
    caminho = gerar_relatorio_financeiro(admin.dashboard.financeiro(*periodo), periodo, admin.empresa.obter())
    assert caminho.read_bytes()[:4] == b"%PDF"
