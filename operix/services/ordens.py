"""Orçamentos e Ordens de Serviço: o coração do fluxo da oficina.

Fluxo (ver :class:`operix.models.StatusOrdem`)::

    Orçamento ──aprovar──► Aprovada ──► Em execução ◄──► Aguardando peça
        │                                   │
        └─reprovar─► Reprovada              ▼
                                     Pronta p/ entrega ──► Entregue

Regras principais:

* Ao **aprovar**, todas as peças da OS são baixadas do estoque (com checagem de
  saldo). Depois de aprovada, peças incluídas/removidas movimentam o estoque na
  hora; ao **cancelar**, as peças voltam ao estoque (estorno).
* Totais = peças + mão de obra − desconto. Valores sempre em centavos.
* Entregar exige que a OS esteja quitada (ou confirmação explícita de saldo em aberto).
* Mecânicos só enxergam as próprias OS (e as aprovadas sem responsável, para
  poder assumi-las) e só alteram o status de execução e o diagnóstico.
"""

import logging
import sqlite3

from operix.errors import AcessoNegadoError, NaoEncontradoError, RegraNegocioError, ValidacaoError
from operix.models import (
    FORMAS_PAGAMENTO,
    ItemOrdem,
    OrdemServico,
    Pagamento,
    Permissao,
    RegistroHistorico,
    StatusOrdem,
    TipoItem,
)
from operix.services.base import ServicoBase
from operix.services.clientes import ClienteService, VeiculoService
from operix.services.estoque import EstoqueService
from operix.utils import formatters as fmt
from operix.utils import validators as val

log = logging.getLogger(__name__)

S = StatusOrdem

# Subconsulta reutilizada para calcular o subtotal de cada OS
SQL_SUBTOTAL = """COALESCE((SELECT SUM(CAST(ROUND(i.quantidade * i.valor_unitario_centavos) AS INTEGER))
                             FROM ordem_itens i WHERE i.ordem_id = o.id), 0)"""
SQL_PAGO = "COALESCE((SELECT SUM(p.valor_centavos) FROM pagamentos p WHERE p.ordem_id = o.id), 0)"


class OrdemService(ServicoBase):
    # ================================================================ leitura
    def listar(self, status: list[StatusOrdem] | None = None, busca: str = "") -> list[dict]:
        """Lista resumida para a tabela principal (com totais e saldo)."""
        sql = f"""
            SELECT o.id, o.numero, o.status, o.criado_em, o.km_entrada, o.mecanico_id,
                   c.nome AS cliente_nome, c.telefone AS cliente_telefone,
                   v.placa, TRIM(COALESCE(v.marca, '') || ' ' || COALESCE(v.modelo, '')) AS veiculo,
                   u.nome AS mecanico_nome,
                   {SQL_SUBTOTAL} AS subtotal, o.desconto_centavos, {SQL_PAGO} AS pago
              FROM ordens o
              JOIN clientes c ON c.id = o.cliente_id
              JOIN veiculos v ON v.id = o.veiculo_id
              LEFT JOIN usuarios u ON u.id = o.mecanico_id
             WHERE o.empresa_id = ?
        """
        parametros: list = [self.empresa_id]
        if not self.sessao.pode(Permissao.VER_TODAS_ORDENS):
            sql += " AND (o.mecanico_id = ? OR (o.mecanico_id IS NULL AND o.status = 'APROVADA'))"
            parametros.append(self.usuario.id)
        if status:
            sql += f" AND o.status IN ({','.join('?' * len(status))})"
            parametros += [s.value for s in status]
        if busca.strip():
            termo = f"%{busca.strip()}%"
            placa = val.normalizar_placa(busca) or "\x00"
            sql += " AND (c.nome LIKE ? OR v.placa LIKE ? OR CAST(o.numero AS TEXT) = ?)"
            parametros += [termo, f"%{placa}%", busca.strip().lstrip("0#")]
        sql += " ORDER BY o.numero DESC"
        resultado = []
        for linha in self.db.consultar(sql, tuple(parametros)):
            item = dict(linha)
            item["total"] = max(item["subtotal"] - item["desconto_centavos"], 0)
            item["saldo"] = max(item["total"] - item["pago"], 0)
            resultado.append(item)
        return resultado

    def obter(self, ordem_id: int) -> OrdemServico:
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
        self._exigir_acesso_leitura(ordem)
        return ordem

    def _carregar(self, conn: sqlite3.Connection, ordem_id: int) -> OrdemServico:
        """Carrega a OS completa (itens, pagamentos e histórico) usando a conexão dada."""
        linha = conn.execute(
            """SELECT o.*, c.nome AS cliente_nome, c.documento AS cliente_documento, c.telefone AS cliente_telefone,
                      v.placa AS veiculo_placa,
                      TRIM(COALESCE(v.marca, '') || ' ' || COALESCE(v.modelo, '') || ' ' ||
                           COALESCE(CAST(v.ano AS TEXT), '')) AS veiculo_descricao,
                      u.nome AS mecanico_nome
                 FROM ordens o
                 JOIN clientes c ON c.id = o.cliente_id
                 JOIN veiculos v ON v.id = o.veiculo_id
                 LEFT JOIN usuarios u ON u.id = o.mecanico_id
                WHERE o.id = ? AND o.empresa_id = ?""",
            (ordem_id, self.empresa_id),
        ).fetchone()
        if not linha:
            raise NaoEncontradoError("Ordem de serviço não encontrada.")
        ordem = OrdemServico.da_linha(linha)
        ordem.itens = [ItemOrdem.da_linha(r) for r in conn.execute(
            "SELECT * FROM ordem_itens WHERE ordem_id = ? ORDER BY tipo, id", (ordem_id,))]
        ordem.pagamentos = [Pagamento.da_linha(r) for r in conn.execute(
            """SELECT p.*, u.nome AS usuario_nome FROM pagamentos p LEFT JOIN usuarios u ON u.id = p.usuario_id
                WHERE p.ordem_id = ? ORDER BY p.data, p.id""", (ordem_id,))]
        ordem.historico = [RegistroHistorico.da_linha(r) for r in conn.execute(
            """SELECT h.*, u.nome AS usuario_nome FROM ordem_historico h LEFT JOIN usuarios u ON u.id = h.usuario_id
                WHERE h.ordem_id = ? ORDER BY h.data, h.id""", (ordem_id,))]
        return ordem

    # ============================================================ permissões
    def _e_responsavel(self, ordem: OrdemServico) -> bool:
        return ordem.mecanico_id == self.usuario.id

    def _exigir_acesso_leitura(self, ordem: OrdemServico) -> None:
        if self.sessao.pode(Permissao.VER_TODAS_ORDENS) or self._e_responsavel(ordem):
            return
        if ordem.mecanico_id is None and ordem.status == S.APROVADA.value:
            return
        raise AcessoNegadoError("Esta ordem de serviço está atribuída a outro mecânico.")

    def _exigir_edicao_itens(self, ordem: OrdemServico) -> None:
        self.exigir(Permissao.EDITAR_ITENS_ORDEM)
        if not ordem.status_enum.permite_editar_itens:
            raise RegraNegocioError(
                f"Não é possível alterar itens de uma OS com status '{ordem.status_enum.rotulo}'."
            )

    # ================================================================ criação
    def criar(self, dados: dict) -> int:
        """Abre uma nova OS (inicialmente como orçamento)."""
        self.exigir(Permissao.CRIAR_ORDEM)
        cliente = ClienteService(self.db, self.sessao).obter(int(dados.get("cliente_id") or 0))
        veiculo = VeiculoService(self.db, self.sessao).obter(int(dados.get("veiculo_id") or 0))
        if veiculo.cliente_id != cliente.id:
            raise ValidacaoError("O veículo selecionado não pertence a este cliente.", "veiculo")
        if not cliente.ativo or not veiculo.ativo:
            raise RegraNegocioError("Cliente ou veículo inativo. Reative o cadastro antes de abrir a OS.")
        km = val.validar_inteiro(dados.get("km_entrada"), "Km de entrada", maximo=5_000_000)
        mecanico_id = self._validar_mecanico(dados.get("mecanico_id"))
        defeito = val.validar_texto_longo(dados.get("defeito_relatado"))
        observacoes = val.validar_texto_longo(dados.get("observacoes"))
        agora = fmt.agora()

        with self.db.conexao() as conn:
            numero = conn.execute("SELECT COALESCE(MAX(numero), 0) + 1 FROM ordens WHERE empresa_id = ?",
                                  (self.empresa_id,)).fetchone()[0]
            ordem_id = conn.execute(
                """INSERT INTO ordens (empresa_id, numero, cliente_id, veiculo_id, mecanico_id, status, km_entrada,
                                       defeito_relatado, observacoes, criado_por, criado_em)
                   VALUES (?, ?, ?, ?, ?, 'ORCAMENTO', ?, ?, ?, ?, ?)""",
                (self.empresa_id, numero, cliente.id, veiculo.id, mecanico_id, km, defeito, observacoes,
                 self.usuario.id, agora),
            ).lastrowid
            if km and km > (veiculo.km_atual or 0):
                conn.execute("UPDATE veiculos SET km_atual = ? WHERE id = ?", (km, veiculo.id))
            self._registrar_historico(conn, ordem_id, None, S.ORCAMENTO, "OS aberta")
        log.info("OS #%s criada (id=%s)", numero, ordem_id)
        return ordem_id

    def _validar_mecanico(self, mecanico_id) -> int | None:
        if mecanico_id in (None, "", 0):
            return None
        existe = self.db.escalar("SELECT COUNT(*) FROM usuarios WHERE id = ? AND empresa_id = ? AND ativo = 1",
                                 (int(mecanico_id), self.empresa_id))
        if not existe:
            raise ValidacaoError("Mecânico responsável inválido.", "mecanico")
        return int(mecanico_id)

    def atualizar_dados(self, ordem_id: int, dados: dict) -> None:
        """Atualiza km, defeito, diagnóstico, observações e responsável.

        Mecânicos só podem alterar o diagnóstico das próprias OS.
        """
        ordem = self.obter(ordem_id)
        if ordem.status_enum.finalizada:
            raise RegraNegocioError("Esta OS já foi finalizada e não pode ser alterada.")
        diagnostico = val.validar_texto_longo(dados.get("diagnostico"))

        if not self.sessao.pode(Permissao.EDITAR_ITENS_ORDEM):
            self.exigir(Permissao.ALTERAR_STATUS_EXECUCAO)
            if not self._e_responsavel(ordem):
                raise AcessoNegadoError("Você só pode alterar o diagnóstico das suas ordens de serviço.")
            with self.db.conexao() as conn:
                conn.execute("UPDATE ordens SET diagnostico = ? WHERE id = ?", (diagnostico, ordem_id))
            return

        km = val.validar_inteiro(dados.get("km_entrada"), "Km de entrada", maximo=5_000_000)
        mecanico_id = self._validar_mecanico(dados.get("mecanico_id"))
        with self.db.conexao() as conn:
            conn.execute(
                """UPDATE ordens SET km_entrada = ?, defeito_relatado = ?, diagnostico = ?, observacoes = ?,
                          mecanico_id = ? WHERE id = ? AND empresa_id = ?""",
                (km, val.validar_texto_longo(dados.get("defeito_relatado")), diagnostico,
                 val.validar_texto_longo(dados.get("observacoes")), mecanico_id, ordem_id, self.empresa_id),
            )
            if km:
                conn.execute("UPDATE veiculos SET km_atual = MAX(km_atual, ?) WHERE id = ?", (km, ordem.veiculo_id))

    # ================================================================== itens
    def adicionar_peca(self, ordem_id: int, peca_id: int, quantidade, valor_unitario=None) -> int:
        """Inclui uma peça do estoque. Sem valor informado, usa o preço de venda cadastrado."""
        estoque = EstoqueService(self.db, self.sessao)
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            self._exigir_edicao_itens(ordem)
            peca = estoque.obter(int(peca_id))
            if not peca.ativo:
                raise RegraNegocioError("Esta peça está inativa no cadastro.")
            qtd = fmt.texto_para_quantidade(quantidade)
            valor = (peca.preco_centavos if valor_unitario in (None, "")
                     else fmt.moeda_para_centavos(valor_unitario, "Valor unitário"))
            item_id = conn.execute(
                """INSERT INTO ordem_itens (ordem_id, tipo, peca_id, descricao, quantidade, valor_unitario_centavos)
                   VALUES (?, 'PECA', ?, ?, ?, ?)""",
                (ordem_id, peca.id, f"{peca.codigo} - {peca.descricao}", qtd, valor),
            ).lastrowid
            if ordem.estoque_baixado:
                # OS já aprovada: a peça sai do estoque imediatamente
                estoque._movimentar(conn, peca.id, "SAIDA", qtd, ordem_id, f"OS #{ordem.numero_formatado}")
            return item_id

    def adicionar_servico(self, ordem_id: int, descricao: str, quantidade, valor_unitario,
                          servico_id: int | None = None) -> int:
        """Inclui mão de obra (livre ou a partir do catálogo de serviços)."""
        descricao = val.validar_texto(descricao, "Descrição do serviço", maximo=200)
        qtd = fmt.texto_para_quantidade(quantidade or "1")
        valor = fmt.moeda_para_centavos(valor_unitario, "Valor da mão de obra", permitir_zero=False)
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            self._exigir_edicao_itens(ordem)
            return conn.execute(
                """INSERT INTO ordem_itens (ordem_id, tipo, servico_id, descricao, quantidade, valor_unitario_centavos)
                   VALUES (?, 'SERVICO', ?, ?, ?, ?)""",
                (ordem_id, servico_id or None, descricao, qtd, valor),
            ).lastrowid

    def remover_item(self, ordem_id: int, item_id: int) -> None:
        estoque = EstoqueService(self.db, self.sessao)
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            self._exigir_edicao_itens(ordem)
            item = next((i for i in ordem.itens if i.id == int(item_id)), None)
            if not item:
                raise NaoEncontradoError("Item não encontrado nesta OS.")
            novo_total = max(ordem.subtotal - item.total_centavos - ordem.desconto_centavos, 0)
            if novo_total < ordem.total_pago:
                raise RegraNegocioError("Remover este item deixaria o total menor que o valor já pago.")
            conn.execute("DELETE FROM ordem_itens WHERE id = ?", (item.id,))
            if ordem.estoque_baixado and item.tipo == TipoItem.PECA.value and item.peca_id:
                estoque._movimentar(conn, item.peca_id, "ESTORNO", item.quantidade, ordem_id,
                                    f"Item removido da OS #{ordem.numero_formatado}")
            # Desconto não pode ficar maior que o novo subtotal
            novo_subtotal = ordem.subtotal - item.total_centavos
            if ordem.desconto_centavos > novo_subtotal:
                conn.execute("UPDATE ordens SET desconto_centavos = ? WHERE id = ?", (max(novo_subtotal, 0), ordem_id))

    def definir_desconto(self, ordem_id: int, valor) -> None:
        desconto = fmt.moeda_para_centavos(valor or "0", "Desconto")
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            self._exigir_edicao_itens(ordem)
            if desconto > ordem.subtotal:
                raise ValidacaoError(
                    f"O desconto não pode ser maior que o subtotal ({fmt.formatar_moeda(ordem.subtotal)}).", "desconto"
                )
            if ordem.subtotal - desconto < ordem.total_pago:
                raise RegraNegocioError("Com este desconto o total ficaria menor que o valor já pago.")
            conn.execute("UPDATE ordens SET desconto_centavos = ? WHERE id = ?", (desconto, ordem_id))

    # ================================================================= status
    def alterar_status(self, ordem_id: int, novo: StatusOrdem | str, observacao: str | None = None,
                       permitir_saldo_aberto: bool = False) -> None:
        novo = StatusOrdem(novo)
        estoque = EstoqueService(self.db, self.sessao)
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            self._exigir_acesso_leitura(ordem)
            atual = ordem.status_enum
            if not atual.pode_ir_para(novo):
                raise RegraNegocioError(f"Não é possível mudar de '{atual.rotulo}' para '{novo.rotulo}'.")
            self._exigir_permissao_transicao(ordem, atual, novo)

            agora = fmt.agora()
            campos: dict = {"status": novo.value}

            if novo is S.APROVADA:
                if not ordem.itens:
                    raise RegraNegocioError("Inclua ao menos uma peça ou serviço antes de aprovar o orçamento.")
                self._baixar_estoque(conn, estoque, ordem)
                campos.update(estoque_baixado=1, aprovado_em=agora)
            elif novo is S.EM_EXECUCAO and ordem.mecanico_id is None and self.usuario.e_mecanico:
                campos["mecanico_id"] = self.usuario.id  # mecânico "assume" a OS
            elif novo is S.CONCLUIDA:
                if not ordem.itens:
                    raise RegraNegocioError("A OS não possui itens. Inclua os serviços realizados antes de concluir.")
                campos["concluido_em"] = agora
            elif novo is S.ENTREGUE:
                if ordem.saldo > 0 and not permitir_saldo_aberto:
                    raise RegraNegocioError(
                        f"A OS possui saldo em aberto de {fmt.formatar_moeda(ordem.saldo)}.\n"
                        "Registre o pagamento antes de entregar o veículo."
                    )
                campos["entregue_em"] = agora
            elif novo is S.CANCELADA:
                if ordem.pagamentos:
                    raise RegraNegocioError("Esta OS possui pagamentos registrados. Estorne-os antes de cancelar.")
                if ordem.estoque_baixado:
                    self._estornar_estoque(conn, estoque, ordem)
                campos.update(estoque_baixado=0, cancelado_em=agora)

            atribuicoes = ", ".join(f"{k} = ?" for k in campos)
            conn.execute(f"UPDATE ordens SET {atribuicoes} WHERE id = ?", (*campos.values(), ordem_id))
            if novo is S.ENTREGUE and ordem.saldo > 0:
                observacao = (observacao + " | " if observacao else "") + \
                    f"Entregue com saldo em aberto de {fmt.formatar_moeda(ordem.saldo)}"
            self._registrar_historico(conn, ordem_id, atual, novo, observacao)
        log.info("OS id=%s: %s -> %s", ordem_id, atual.value, novo.value)

    def _exigir_permissao_transicao(self, ordem: OrdemServico, atual: StatusOrdem, novo: StatusOrdem) -> None:
        if novo in (S.APROVADA, S.REPROVADA) or (atual is S.REPROVADA and novo is S.ORCAMENTO):
            self.exigir(Permissao.APROVAR_ORDEM)
        elif novo in (S.ENTREGUE, S.CANCELADA):
            self.exigir(Permissao.ENTREGAR_CANCELAR_ORDEM)
        else:  # EM_EXECUCAO, AGUARDANDO_PECA, CONCLUIDA
            self.exigir(Permissao.ALTERAR_STATUS_EXECUCAO)
            if not self.sessao.pode(Permissao.VER_TODAS_ORDENS) and ordem.mecanico_id not in (None, self.usuario.id):
                raise AcessoNegadoError("Esta ordem de serviço está atribuída a outro mecânico.")

    def _baixar_estoque(self, conn, estoque: EstoqueService, ordem: OrdemServico) -> None:
        """Baixa todas as peças; se faltar alguma, nada é baixado (transação)."""
        faltando = []
        necessidade: dict[int, float] = {}
        for item in ordem.itens:
            if item.tipo == TipoItem.PECA.value and item.peca_id:
                necessidade[item.peca_id] = necessidade.get(item.peca_id, 0) + item.quantidade
        for peca_id, qtd in necessidade.items():
            peca = conn.execute("SELECT descricao, estoque, unidade FROM pecas WHERE id = ?", (peca_id,)).fetchone()
            if peca["estoque"] < qtd:
                faltando.append(f"• {peca['descricao']}: disponível {fmt.formatar_quantidade(peca['estoque'])}, "
                                f"necessário {fmt.formatar_quantidade(qtd)} {peca['unidade']}")
        if faltando:
            raise RegraNegocioError("Estoque insuficiente para aprovar a OS:\n" + "\n".join(faltando) +
                                    "\n\nDê entrada nas peças ou ajuste as quantidades.")
        for peca_id, qtd in necessidade.items():
            estoque._movimentar(conn, peca_id, "SAIDA", qtd, ordem.id, f"Aprovação da OS #{ordem.numero_formatado}")

    def _estornar_estoque(self, conn, estoque: EstoqueService, ordem: OrdemServico) -> None:
        for item in ordem.itens:
            if item.tipo == TipoItem.PECA.value and item.peca_id:
                estoque._movimentar(conn, item.peca_id, "ESTORNO", item.quantidade, ordem.id,
                                    f"Cancelamento da OS #{ordem.numero_formatado}")

    def _registrar_historico(self, conn, ordem_id: int, anterior: StatusOrdem | None, novo: StatusOrdem,
                             observacao: str | None) -> None:
        conn.execute(
            """INSERT INTO ordem_historico (ordem_id, status_anterior, status_novo, usuario_id, observacao, data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ordem_id, anterior.value if anterior else None, novo.value, self.usuario.id,
             val.validar_texto_longo(observacao, 500), fmt.agora()),
        )

    # ============================================================ pagamentos
    def registrar_pagamento(self, ordem_id: int, valor, forma: str, observacao: str | None = None) -> int:
        self.exigir(Permissao.REGISTRAR_PAGAMENTO)
        centavos = fmt.moeda_para_centavos(valor, "Valor do pagamento", permitir_zero=False)
        if forma not in FORMAS_PAGAMENTO:
            raise ValidacaoError("Selecione a forma de pagamento.", "forma")
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            if not ordem.status_enum.permite_pagamento:
                raise RegraNegocioError(
                    f"Não é possível registrar pagamento em uma OS com status '{ordem.status_enum.rotulo}'.\n"
                    "Aprove o orçamento primeiro."
                )
            if centavos > ordem.saldo:
                raise ValidacaoError(
                    f"O valor informado é maior que o saldo em aberto ({fmt.formatar_moeda(ordem.saldo)}).", "valor"
                )
            return conn.execute(
                """INSERT INTO pagamentos (empresa_id, ordem_id, valor_centavos, forma, data, usuario_id, observacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (self.empresa_id, ordem_id, centavos, forma, fmt.agora(), self.usuario.id,
                 val.validar_texto(observacao, "Observação", obrigatorio=False)),
            ).lastrowid

    def estornar_pagamento(self, ordem_id: int, pagamento_id: int) -> None:
        self.exigir(Permissao.ESTORNAR_PAGAMENTO)
        with self.db.conexao() as conn:
            ordem = self._carregar(conn, ordem_id)
            if ordem.status == S.ENTREGUE.value:
                raise RegraNegocioError("Não é possível estornar pagamentos de uma OS já entregue.")
            apagados = conn.execute("DELETE FROM pagamentos WHERE id = ? AND ordem_id = ?",
                                    (pagamento_id, ordem_id)).rowcount
            if not apagados:
                raise NaoEncontradoError("Pagamento não encontrado.")
            self._registrar_historico(conn, ordem_id, ordem.status_enum, ordem.status_enum,
                                      "Pagamento estornado")
