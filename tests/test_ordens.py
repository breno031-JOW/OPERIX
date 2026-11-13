"""Fluxo completo da OS: itens, totais, estoque, status, pagamentos e perfis."""

import pytest

from operix.errors import AcessoNegadoError, RegraNegocioError, ValidacaoError
from operix.models import StatusOrdem as S


def nova_os(svc, cenario, **extra):
    return svc.ordens.criar({"cliente_id": cenario["cliente"], "veiculo_id": cenario["veiculo"],
                             "km_entrada": 1500, "defeito_relatado": "Revisão", **extra})


def estoque(svc, peca_id):
    return svc.estoque.obter(peca_id).estoque


def test_criar_os_numeracao_e_km(admin, cenario):
    o1, o2 = nova_os(admin, cenario), nova_os(admin, cenario)
    assert admin.ordens.obter(o1).numero == 1
    assert admin.ordens.obter(o2).numero == 2
    assert admin.ordens.obter(o1).status == S.ORCAMENTO.value
    assert admin.veiculos.obter(cenario["veiculo"]).km_atual == 1500


def test_veiculo_de_outro_cliente(admin, cenario):
    outro = admin.clientes.criar({"nome": "Outro", "documento": "11444777000161"})
    with pytest.raises(ValidacaoError):
        admin.ordens.criar({"cliente_id": outro, "veiculo_id": cenario["veiculo"]})


def test_totais_e_desconto(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_peca(o, cenario["oleo"], "4,5")        # 4,5 x 40,00 = 180,00
    admin.ordens.adicionar_servico(o, "Troca de óleo", 1, "60,00")  # 60,00
    admin.ordens.definir_desconto(o, "20,00")
    ordem = admin.ordens.obter(o)
    assert (ordem.total_pecas, ordem.total_servicos, ordem.total) == (18000, 6000, 22000)
    with pytest.raises(ValidacaoError):
        admin.ordens.definir_desconto(o, "1000")


def test_aprovar_baixa_estoque_e_cancelar_estorna(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_peca(o, cenario["oleo"], 4)
    assert estoque(admin, cenario["oleo"]) == 10  # orçamento não mexe no estoque
    admin.ordens.alterar_status(o, S.APROVADA)
    assert estoque(admin, cenario["oleo"]) == 6
    # Peça incluída depois da aprovação sai na hora; removida volta
    item = admin.ordens.adicionar_peca(o, cenario["oleo"], 1)
    assert estoque(admin, cenario["oleo"]) == 5
    admin.ordens.remover_item(o, item)
    assert estoque(admin, cenario["oleo"]) == 6
    admin.ordens.alterar_status(o, S.CANCELADA)
    assert estoque(admin, cenario["oleo"]) == 10
    tipos = [m.tipo for m in admin.estoque.movimentos(cenario["oleo"])]
    assert tipos.count("ESTORNO") == 2 and tipos.count("SAIDA") == 2


def test_aprovar_sem_estoque_nao_baixa_nada(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_peca(o, cenario["oleo"], 2)
    admin.ordens.adicionar_peca(o, cenario["filtro"], 3)  # só há 1 filtro
    with pytest.raises(RegraNegocioError, match="Estoque insuficiente"):
        admin.ordens.alterar_status(o, S.APROVADA)
    assert estoque(admin, cenario["oleo"]) == 10  # rollback: nada foi baixado
    assert admin.ordens.obter(o).status == S.ORCAMENTO.value


def test_aprovar_sem_itens(admin, cenario):
    o = nova_os(admin, cenario)
    with pytest.raises(RegraNegocioError):
        admin.ordens.alterar_status(o, S.APROVADA)


def test_transicao_invalida(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_servico(o, "Serviço", 1, "100")
    with pytest.raises(RegraNegocioError):
        admin.ordens.alterar_status(o, S.ENTREGUE)


def test_fluxo_completo_com_pagamento(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_servico(o, "Alinhamento", 1, "100,00")
    with pytest.raises(RegraNegocioError):  # orçamento ainda não aprovado
        admin.ordens.registrar_pagamento(o, "50", "PIX")
    for status in (S.APROVADA, S.EM_EXECUCAO, S.AGUARDANDO_PECA, S.EM_EXECUCAO, S.CONCLUIDA):
        admin.ordens.alterar_status(o, status)
    admin.ordens.registrar_pagamento(o, "40,00", "Dinheiro")
    with pytest.raises(ValidacaoError):  # maior que o saldo
        admin.ordens.registrar_pagamento(o, "70,00", "PIX")
    with pytest.raises(RegraNegocioError, match="saldo em aberto"):
        admin.ordens.alterar_status(o, S.ENTREGUE)
    admin.ordens.registrar_pagamento(o, "60,00", "PIX")
    admin.ordens.alterar_status(o, S.ENTREGUE)
    ordem = admin.ordens.obter(o)
    assert ordem.saldo == 0 and ordem.entregue_em
    assert [h.status_novo for h in ordem.historico][-1] == S.ENTREGUE.value
    with pytest.raises(RegraNegocioError):  # finalizada: itens bloqueados
        admin.ordens.adicionar_servico(o, "Extra", 1, "10")


def test_entregar_com_saldo_confirmado(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_servico(o, "Serviço", 1, "100")
    for status in (S.APROVADA, S.EM_EXECUCAO, S.CONCLUIDA):
        admin.ordens.alterar_status(o, status)
    admin.ordens.alterar_status(o, S.ENTREGUE, permitir_saldo_aberto=True)
    assert "saldo em aberto" in admin.ordens.obter(o).historico[-1].observacao


def test_cancelar_com_pagamento_bloqueado(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_servico(o, "Serviço", 1, "100")
    admin.ordens.alterar_status(o, S.APROVADA)
    pagamento = admin.ordens.registrar_pagamento(o, "30", "PIX")
    with pytest.raises(RegraNegocioError):
        admin.ordens.alterar_status(o, S.CANCELADA)
    admin.ordens.estornar_pagamento(o, pagamento)
    admin.ordens.alterar_status(o, S.CANCELADA)


def test_permissoes_mecanico(admin, mecanico, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_servico(o, "Serviço", 1, "100")
    assert mecanico.ordens.listar() == []  # orçamento não aparece para o mecânico
    with pytest.raises(AcessoNegadoError):
        mecanico.ordens.alterar_status(o, S.APROVADA)
    admin.ordens.alterar_status(o, S.APROVADA)
    assert [x["id"] for x in mecanico.ordens.listar()] == [o]  # aprovada sem responsável: fila
    mecanico.ordens.alterar_status(o, S.EM_EXECUCAO)  # assume a OS
    assert admin.ordens.obter(o).mecanico_id == mecanico.sessao.usuario.id
    mecanico.ordens.atualizar_dados(o, {"diagnostico": "Trocar correia"})
    assert admin.ordens.obter(o).diagnostico == "Trocar correia"
    with pytest.raises(AcessoNegadoError):
        mecanico.ordens.adicionar_servico(o, "Extra", 1, "10")
    with pytest.raises(AcessoNegadoError):
        mecanico.ordens.registrar_pagamento(o, "10", "PIX")
    with pytest.raises(AcessoNegadoError):
        mecanico.clientes.criar({"nome": "X", "documento": "52998224725"})
    with pytest.raises(AcessoNegadoError):
        mecanico.dashboard.financeiro(*__import__("operix.services.dashboard", fromlist=["x"]).periodo_mes_atual())


def test_mecanico_nao_ve_os_de_outro(admin, mecanico, cenario):
    admin.usuarios.criar({"nome": "Outro", "email": "outro@teste.com", "perfil": "Mecânico",
                          "senha": "senha123", "confirmacao": "senha123"})
    outro_id = [u.id for u in admin.usuarios.listar() if u.email == "outro@teste.com"][0]
    o = nova_os(admin, cenario, mecanico_id=outro_id)
    with pytest.raises(AcessoNegadoError):
        mecanico.ordens.obter(o)


def test_atendente_nao_estorna_nem_gerencia_usuarios(admin, atendente, cenario):
    o = nova_os(atendente, cenario)
    atendente.ordens.adicionar_servico(o, "Serviço", 1, "100")
    atendente.ordens.alterar_status(o, S.APROVADA)
    pagamento = atendente.ordens.registrar_pagamento(o, "10", "PIX")
    with pytest.raises(AcessoNegadoError):
        atendente.ordens.estornar_pagamento(o, pagamento)
    with pytest.raises(AcessoNegadoError):
        atendente.usuarios.listar()


def test_historico_por_placa(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_peca(o, cenario["filtro"], 1)
    historico = admin.veiculos.historico(cenario["veiculo"])
    assert len(historico) == 1 and "Filtro" in historico[0]["pecas"] and historico[0]["total"] == 3000


def test_dashboard(admin, cenario):
    o = nova_os(admin, cenario)
    admin.ordens.adicionar_peca(o, cenario["oleo"], 8)  # deixa o óleo abaixo do mínimo (2)
    admin.ordens.alterar_status(o, S.APROVADA)
    painel = admin.dashboard.operacional()
    assert painel["em_execucao"] == 1 and painel["estoque_baixo"] == 1
