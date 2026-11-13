"""Estoque de peças e catálogo de serviços (mão de obra)."""

import sqlite3

from operix.errors import NaoEncontradoError, RegraNegocioError, ValidacaoError
from operix.models import MovimentoEstoque, Peca, Permissao, ServicoCatalogo
from operix.services.base import ServicoBase, traduzir_integridade
from operix.utils import formatters as fmt
from operix.utils import validators as val


class EstoqueService(ServicoBase):
    _ERROS = {"pecas.empresa_id, pecas.codigo": "Já existe uma peça com este código."}

    # ------------------------------------------------------------- consultas
    def listar(self, busca: str = "", apenas_baixo: bool = False, incluir_inativas: bool = False) -> list[Peca]:
        self.exigir(Permissao.VER_ESTOQUE)
        sql = "SELECT * FROM pecas WHERE empresa_id = ?"
        parametros: list = [self.empresa_id]
        if not incluir_inativas:
            sql += " AND ativo = 1"
        if busca.strip():
            sql += " AND (codigo LIKE ? OR descricao LIKE ?)"
            parametros += [f"%{busca.strip()}%"] * 2
        if apenas_baixo:
            sql += " AND estoque_minimo > 0 AND estoque <= estoque_minimo"
        sql += " ORDER BY descricao COLLATE NOCASE"
        return [Peca.da_linha(r) for r in self.db.consultar(sql, tuple(parametros))]

    def obter(self, peca_id: int) -> Peca:
        linha = self.db.consultar_um("SELECT * FROM pecas WHERE id = ? AND empresa_id = ?", (peca_id, self.empresa_id))
        if not linha:
            raise NaoEncontradoError("Peça não encontrada.")
        return Peca.da_linha(linha)

    def movimentos(self, peca_id: int, limite: int = 200) -> list[MovimentoEstoque]:
        self.exigir(Permissao.VER_ESTOQUE)
        self.obter(peca_id)
        linhas = self.db.consultar(
            """SELECT m.*, u.nome AS usuario_nome, o.numero AS ordem_numero
                 FROM movimentos_estoque m
                 LEFT JOIN usuarios u ON u.id = m.usuario_id
                 LEFT JOIN ordens o ON o.id = m.ordem_id
                WHERE m.peca_id = ? AND m.empresa_id = ?
                ORDER BY m.data DESC, m.id DESC LIMIT ?""",
            (peca_id, self.empresa_id, limite),
        )
        return [MovimentoEstoque.da_linha(r) for r in linhas]

    # -------------------------------------------------------------- cadastro
    def _validar(self, dados: dict) -> tuple:
        custo = fmt.moeda_para_centavos(dados.get("custo") or "0", "Custo")
        preco = fmt.moeda_para_centavos(dados.get("preco") or "0", "Preço de venda", permitir_zero=False)
        minimo = fmt.texto_para_quantidade(dados.get("estoque_minimo"), "Estoque mínimo", permitir_zero=True)
        return (
            (val.validar_texto(dados.get("codigo"), "Código", maximo=30) or "").upper(),
            val.validar_texto(dados.get("descricao"), "Descrição", maximo=120),
            (val.validar_texto(dados.get("unidade"), "Unidade", obrigatorio=False, maximo=5) or "UN").upper(),
            custo,
            preco,
            minimo,
        )

    def criar(self, dados: dict) -> int:
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        valores = self._validar(dados)
        estoque_inicial = fmt.texto_para_quantidade(dados.get("estoque_inicial"), "Estoque inicial", permitir_zero=True)
        try:
            with self.db.conexao() as conn:
                peca_id = conn.execute(
                    """INSERT INTO pecas (empresa_id, codigo, descricao, unidade, custo_centavos, preco_centavos,
                                          estoque_minimo) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.empresa_id, *valores),
                ).lastrowid
                if estoque_inicial:
                    self._movimentar(conn, peca_id, "ENTRADA", estoque_inicial, observacao="Estoque inicial")
                return peca_id
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def atualizar(self, peca_id: int, dados: dict) -> None:
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        self.obter(peca_id)
        valores = self._validar(dados)
        try:
            with self.db.conexao() as conn:
                conn.execute(
                    """UPDATE pecas SET codigo = ?, descricao = ?, unidade = ?, custo_centavos = ?,
                              preco_centavos = ?, estoque_minimo = ? WHERE id = ? AND empresa_id = ?""",
                    (*valores, peca_id, self.empresa_id),
                )
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def definir_ativo(self, peca_id: int, ativo: bool) -> None:
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        self.obter(peca_id)
        with self.db.conexao() as conn:
            conn.execute("UPDATE pecas SET ativo = ? WHERE id = ? AND empresa_id = ?",
                         (1 if ativo else 0, peca_id, self.empresa_id))

    # ----------------------------------------------------------- movimentos
    def entrada(self, peca_id: int, quantidade, custo_unitario=None, observacao: str | None = None) -> None:
        """Entrada de mercadoria (compra). Atualiza o custo se informado."""
        self.exigir(Permissao.MOVIMENTAR_ESTOQUE)
        self.obter(peca_id)
        qtd = fmt.texto_para_quantidade(quantidade)
        with self.db.conexao() as conn:
            if custo_unitario not in (None, ""):
                custo = fmt.moeda_para_centavos(custo_unitario, "Custo unitário")
                conn.execute("UPDATE pecas SET custo_centavos = ? WHERE id = ?", (custo, peca_id))
            self._movimentar(conn, peca_id, "ENTRADA", qtd, observacao=observacao or "Entrada de mercadoria")

    def ajustar(self, peca_id: int, saldo_contado, motivo: str) -> None:
        """Ajuste de inventário: define o saldo para a quantidade contada."""
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        peca = self.obter(peca_id)
        motivo = val.validar_texto(motivo, "Motivo do ajuste")
        if str(saldo_contado if saldo_contado is not None else "").strip() == "":
            raise ValidacaoError("Informe o saldo contado.", "saldo")
        novo = fmt.texto_para_quantidade(saldo_contado, "Saldo contado", permitir_zero=True)
        diferenca = round(novo - peca.estoque, 3)
        if diferenca == 0:
            raise ValidacaoError("O saldo contado é igual ao saldo atual. Nada a ajustar.")
        with self.db.conexao() as conn:
            self._movimentar(conn, peca_id, "AJUSTE", diferenca, observacao=motivo)

    def _movimentar(self, conn: sqlite3.Connection, peca_id: int, tipo: str, quantidade: float,
                    ordem_id: int | None = None, observacao: str | None = None) -> float:
        """Aplica um movimento dentro de uma transação já aberta.

        ``quantidade`` positiva soma ao estoque; negativa subtrai. Para
        ``SAIDA`` informe a quantidade positiva (o sinal é aplicado aqui).
        Retorna o novo saldo. Usado também pelo serviço de ordens.
        """
        delta = -abs(quantidade) if tipo == "SAIDA" else quantidade
        linha = conn.execute("SELECT descricao, estoque, unidade FROM pecas WHERE id = ? AND empresa_id = ?",
                             (peca_id, self.empresa_id)).fetchone()
        if not linha:
            raise NaoEncontradoError("Peça não encontrada.")
        novo_saldo = round(linha["estoque"] + delta, 3)
        if novo_saldo < 0:
            raise RegraNegocioError(
                f"Estoque insuficiente para '{linha['descricao']}'.\n"
                f"Disponível: {fmt.formatar_quantidade(linha['estoque'])} {linha['unidade']} · "
                f"Necessário: {fmt.formatar_quantidade(abs(delta))} {linha['unidade']}"
            )
        conn.execute("UPDATE pecas SET estoque = ? WHERE id = ?", (novo_saldo, peca_id))
        conn.execute(
            """INSERT INTO movimentos_estoque (empresa_id, peca_id, tipo, quantidade, saldo_apos, ordem_id,
                                              usuario_id, observacao, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.empresa_id, peca_id, tipo, delta, novo_saldo, ordem_id, self.usuario.id, observacao, fmt.agora()),
        )
        return novo_saldo


class CatalogoServicoService(ServicoBase):
    """Serviços de mão de obra pré-cadastrados com preço sugerido."""

    _ERROS = {"servicos.empresa_id, servicos.descricao": "Já existe um serviço com esta descrição."}

    def listar(self, incluir_inativos: bool = False) -> list[ServicoCatalogo]:
        sql = "SELECT * FROM servicos WHERE empresa_id = ?" + ("" if incluir_inativos else " AND ativo = 1")
        return [ServicoCatalogo.da_linha(r) for r in self.db.consultar(sql + " ORDER BY descricao", (self.empresa_id,))]

    def obter(self, servico_id: int) -> ServicoCatalogo:
        linha = self.db.consultar_um("SELECT * FROM servicos WHERE id = ? AND empresa_id = ?",
                                     (servico_id, self.empresa_id))
        if not linha:
            raise NaoEncontradoError("Serviço não encontrado.")
        return ServicoCatalogo.da_linha(linha)

    def salvar(self, dados: dict, servico_id: int | None = None) -> int:
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        descricao = val.validar_texto(dados.get("descricao"), "Descrição", maximo=120)
        preco = fmt.moeda_para_centavos(dados.get("preco") or "0", "Preço")
        try:
            with self.db.conexao() as conn:
                if servico_id:
                    self.obter(servico_id)
                    conn.execute("UPDATE servicos SET descricao = ?, preco_centavos = ? WHERE id = ? AND empresa_id = ?",
                                 (descricao, preco, servico_id, self.empresa_id))
                    return servico_id
                return conn.execute("INSERT INTO servicos (empresa_id, descricao, preco_centavos) VALUES (?, ?, ?)",
                                    (self.empresa_id, descricao, preco)).lastrowid
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def definir_ativo(self, servico_id: int, ativo: bool) -> None:
        self.exigir(Permissao.GERENCIAR_CATALOGO)
        self.obter(servico_id)
        with self.db.conexao() as conn:
            conn.execute("UPDATE servicos SET ativo = ? WHERE id = ? AND empresa_id = ?",
                         (1 if ativo else 0, servico_id, self.empresa_id))
