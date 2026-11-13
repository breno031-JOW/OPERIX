"""Dados de demonstração (``python main.py --demo``).

Cria uma oficina de exemplo com três usuários (um por perfil), clientes,
veículos, peças, serviços e algumas OS em status diferentes. Só roda em banco
vazio, para nunca misturar dados fictícios com dados reais.
"""

from operix.database import Database
from operix.errors import RegraNegocioError
from operix.models import StatusOrdem
from operix.services import AuthService, Servicos
from operix.utils.formatters import formatar_moeda

USUARIOS_DEMO = [
    # (nome, e-mail, perfil, senha)
    ("Administrador Demo", "admin@demo.com", "Administrador", "admin123"),
    ("Atendente Demo", "atendente@demo.com", "Atendente", "atend123"),
    ("Mecânico Demo", "mecanico@demo.com", "Mecânico", "mec123"),
]


def popular_demo(db: Database) -> None:
    auth = AuthService(db)
    if not auth.precisa_configuracao_inicial():
        raise RegraNegocioError("O banco já possui dados. A demonstração só pode ser criada em um banco vazio.")

    nome, email, _, senha = USUARIOS_DEMO[0]
    sessao = auth.configurar_primeiro_acesso("Oficina Demonstração", "11.222.333/0001-81", nome, email, senha, senha)
    s = Servicos(db, sessao)
    s.empresa.atualizar({"nome": "Oficina Demonstração", "cnpj": "11222333000181", "telefone": "31988887777",
                         "email": "contato@oficinademo.com", "endereco": "Rua das Oficinas, 100 - Centro"})
    ids_usuarios = {}
    for nome, email, perfil, senha in USUARIOS_DEMO[1:]:
        ids_usuarios[perfil] = s.usuarios.criar({"nome": nome, "email": email, "perfil": perfil,
                                                 "senha": senha, "confirmacao": senha})

    c1 = s.clientes.criar({"nome": "Carlos Silva", "documento": "529.982.247-25", "telefone": "31988887777",
                           "email": "carlos@email.com"})
    c2 = s.clientes.criar({"nome": "Transportes Rápido Ltda", "documento": "11.444.777/0001-61",
                           "telefone": "3133334444"})
    v1 = s.veiculos.criar(c1, {"placa": "ABC1234", "marca": "Toyota", "modelo": "Corolla", "ano": 2020,
                               "cor": "Prata", "km_atual": 58000})
    v2 = s.veiculos.criar(c2, {"placa": "BRA2E19", "marca": "Fiat", "modelo": "Fiorino", "ano": 2022,
                               "cor": "Branca", "km_atual": 81000})

    oleo = s.estoque.criar({"codigo": "OL-5W30", "descricao": "Óleo 5W30 sintético", "unidade": "L",
                            "custo": "28,00", "preco": "45,00", "estoque_minimo": "10", "estoque_inicial": "40"})
    filtro = s.estoque.criar({"codigo": "FO-001", "descricao": "Filtro de óleo", "unidade": "UN",
                              "custo": "18,00", "preco": "35,00", "estoque_minimo": "5", "estoque_inicial": "12"})
    pastilha = s.estoque.criar({"codigo": "PF-220", "descricao": "Pastilha de freio dianteira (jogo)",
                                "unidade": "JG", "custo": "95,00", "preco": "180,00", "estoque_minimo": "2",
                                "estoque_inicial": "3"})
    s.catalogo.salvar({"descricao": "Troca de óleo e filtro", "preco": "60,00"})
    s.catalogo.salvar({"descricao": "Revisão do sistema de freios", "preco": "150,00"})
    s.catalogo.salvar({"descricao": "Diagnóstico eletrônico (scanner)", "preco": "120,00"})

    # OS 1: entregue e paga
    o1 = s.ordens.criar({"cliente_id": c1, "veiculo_id": v1, "km_entrada": 60000,
                         "defeito_relatado": "Revisão dos 60 mil km", "mecanico_id": ids_usuarios["Mecânico"]})
    s.ordens.adicionar_peca(o1, oleo, "4,5")
    s.ordens.adicionar_peca(o1, filtro, 1)
    s.ordens.adicionar_servico(o1, "Troca de óleo e filtro", 1, "60,00")
    for status in (StatusOrdem.APROVADA, StatusOrdem.EM_EXECUCAO, StatusOrdem.CONCLUIDA):
        s.ordens.alterar_status(o1, status)
    s.ordens.registrar_pagamento(o1, formatar_moeda(s.ordens.obter(o1).saldo, simbolo=False), "PIX")
    s.ordens.alterar_status(o1, StatusOrdem.ENTREGUE)

    # OS 2: em execução
    o2 = s.ordens.criar({"cliente_id": c2, "veiculo_id": v2, "km_entrada": 81500,
                         "defeito_relatado": "Barulho ao frear", "mecanico_id": ids_usuarios["Mecânico"]})
    s.ordens.adicionar_peca(o2, pastilha, 1)
    s.ordens.adicionar_servico(o2, "Revisão do sistema de freios", 1, "150,00")
    s.ordens.alterar_status(o2, StatusOrdem.APROVADA)
    s.ordens.alterar_status(o2, StatusOrdem.EM_EXECUCAO)

    # OS 3: orçamento aguardando aprovação do cliente
    o3 = s.ordens.criar({"cliente_id": c1, "veiculo_id": v1, "km_entrada": 61200,
                         "defeito_relatado": "Luz de injeção acesa"})
    s.ordens.adicionar_servico(o3, "Diagnóstico eletrônico (scanner)", 1, "120,00")
