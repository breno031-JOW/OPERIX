"""Cadastro de clientes e veículos, incluindo o histórico por placa."""

import sqlite3

from operix.errors import NaoEncontradoError, RegraNegocioError, ValidacaoError
from operix.models import Cliente, Permissao, StatusOrdem, Veiculo
from operix.services.base import ServicoBase, traduzir_integridade
from operix.utils import validators as val

_STATUS_ABERTOS = tuple(s.value for s in StatusOrdem if not s.finalizada and s is not StatusOrdem.REPROVADA)
_MARCADORES = ",".join("?" * len(_STATUS_ABERTOS))


class ClienteService(ServicoBase):
    _ERROS = {"clientes.empresa_id, clientes.documento": "Já existe um cliente cadastrado com este CPF/CNPJ."}

    def listar(self, busca: str = "", incluir_inativos: bool = False) -> list[dict]:
        """Clientes com a quantidade de veículos (para a tabela principal)."""
        sql = """
            SELECT c.*, COUNT(v.id) AS qtd_veiculos,
                   GROUP_CONCAT(v.placa, ' ') AS placas
              FROM clientes c
              LEFT JOIN veiculos v ON v.cliente_id = c.id AND v.ativo = 1
             WHERE c.empresa_id = ?
        """
        parametros: list = [self.empresa_id]
        if not incluir_inativos:
            sql += " AND c.ativo = 1"
        if busca.strip():
            condicoes = ["c.nome LIKE ?"]
            parametros.append(f"%{busca.strip()}%")
            placa = val.normalizar_placa(busca)
            if len(placa) >= 2:
                condicoes.append("v.placa LIKE ?")
                parametros.append(f"%{placa}%")
            digitos = val.somente_digitos(busca)
            if digitos:
                condicoes += ["c.documento LIKE ?", "c.telefone LIKE ?"]
                parametros += [f"%{digitos}%", f"%{digitos}%"]
            sql += " AND (" + " OR ".join(condicoes) + ")"
        sql += " GROUP BY c.id ORDER BY c.nome COLLATE NOCASE"
        return [dict(r) for r in self.db.consultar(sql, tuple(parametros))]

    def obter(self, cliente_id: int) -> Cliente:
        linha = self.db.consultar_um(
            "SELECT * FROM clientes WHERE id = ? AND empresa_id = ?", (cliente_id, self.empresa_id)
        )
        if not linha:
            raise NaoEncontradoError("Cliente não encontrado.")
        return Cliente.da_linha(linha)

    def _validar(self, dados: dict) -> tuple:
        return (
            val.validar_texto(dados.get("nome"), "Nome", maximo=120),
            val.validar_documento(dados.get("documento") or ""),
            val.validar_telefone(dados.get("telefone")),
            val.validar_email(dados.get("email")),
            val.validar_texto(dados.get("endereco"), "Endereço", obrigatorio=False, maximo=300),
            val.validar_texto_longo(dados.get("observacoes"), 1000),
        )

    def criar(self, dados: dict) -> int:
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        valores = self._validar(dados)
        try:
            with self.db.conexao() as conn:
                return conn.execute(
                    """INSERT INTO clientes (empresa_id, nome, documento, telefone, email, endereco, observacoes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.empresa_id, *valores),
                ).lastrowid
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def atualizar(self, cliente_id: int, dados: dict) -> None:
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        self.obter(cliente_id)
        valores = self._validar(dados)
        try:
            with self.db.conexao() as conn:
                conn.execute(
                    """UPDATE clientes SET nome = ?, documento = ?, telefone = ?, email = ?, endereco = ?,
                              observacoes = ? WHERE id = ? AND empresa_id = ?""",
                    (*valores, cliente_id, self.empresa_id),
                )
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def definir_ativo(self, cliente_id: int, ativo: bool) -> None:
        """Inativa (não apaga) o cliente, preservando o histórico de OS."""
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        self.obter(cliente_id)
        if not ativo:
            abertas = self.db.escalar(
                f"SELECT COUNT(*) FROM ordens WHERE cliente_id = ? AND status IN ({_MARCADORES})",
                (cliente_id, *_STATUS_ABERTOS),
            )
            if abertas:
                raise RegraNegocioError(
                    f"O cliente possui {abertas} ordem(ns) de serviço em aberto. Finalize ou cancele antes de inativar."
                )
        with self.db.conexao() as conn:
            conn.execute("UPDATE clientes SET ativo = ? WHERE id = ? AND empresa_id = ?",
                         (1 if ativo else 0, cliente_id, self.empresa_id))


class VeiculoService(ServicoBase):
    _ERROS = {"veiculos.empresa_id, veiculos.placa": "Esta placa já está cadastrada em outro veículo."}

    def listar(self, cliente_id: int | None = None, busca: str = "", incluir_inativos: bool = False) -> list[dict]:
        sql = """
            SELECT v.*, c.nome AS cliente_nome
              FROM veiculos v JOIN clientes c ON c.id = v.cliente_id
             WHERE v.empresa_id = ?
        """
        parametros: list = [self.empresa_id]
        if cliente_id is not None:
            sql += " AND v.cliente_id = ?"
            parametros.append(cliente_id)
        if not incluir_inativos:
            sql += " AND v.ativo = 1"
        if busca.strip():
            sql += " AND (v.placa LIKE ? OR v.modelo LIKE ? OR v.marca LIKE ? OR c.nome LIKE ?)"
            termo = f"%{busca.strip()}%"
            placa = val.normalizar_placa(busca) or "\x00"  # evita '%%' (casaria com tudo)
            parametros += [f"%{placa}%", termo, termo, termo]
        sql += " ORDER BY v.placa"
        return [dict(r) for r in self.db.consultar(sql, tuple(parametros))]

    def obter(self, veiculo_id: int) -> Veiculo:
        linha = self.db.consultar_um(
            "SELECT * FROM veiculos WHERE id = ? AND empresa_id = ?", (veiculo_id, self.empresa_id)
        )
        if not linha:
            raise NaoEncontradoError("Veículo não encontrado.")
        return Veiculo.da_linha(linha)

    def buscar_por_placa(self, placa: str) -> Veiculo | None:
        linha = self.db.consultar_um(
            "SELECT * FROM veiculos WHERE empresa_id = ? AND placa = ?",
            (self.empresa_id, val.normalizar_placa(placa)),
        )
        return Veiculo.da_linha(linha) if linha else None

    def _validar(self, dados: dict) -> tuple:
        return (
            val.validar_placa(dados.get("placa") or ""),
            val.validar_texto(dados.get("marca"), "Marca", obrigatorio=False, maximo=40),
            val.validar_texto(dados.get("modelo"), "Modelo", maximo=60),
            val.validar_ano_veiculo(dados.get("ano")),
            val.validar_texto(dados.get("cor"), "Cor", obrigatorio=False, maximo=30),
            val.validar_inteiro(dados.get("km_atual"), "Km atual", maximo=5_000_000) or 0,
            val.validar_texto_longo(dados.get("observacoes"), 1000),
        )

    def criar(self, cliente_id: int, dados: dict) -> int:
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        cliente = ClienteService(self.db, self.sessao).obter(cliente_id)
        if not cliente.ativo:
            raise RegraNegocioError("Não é possível cadastrar veículo para um cliente inativo.")
        valores = self._validar(dados)
        try:
            with self.db.conexao() as conn:
                return conn.execute(
                    """INSERT INTO veiculos (empresa_id, cliente_id, placa, marca, modelo, ano, cor, km_atual, observacoes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.empresa_id, cliente_id, *valores),
                ).lastrowid
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def atualizar(self, veiculo_id: int, dados: dict) -> None:
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        atual = self.obter(veiculo_id)
        valores = list(self._validar(dados))
        if valores[5] < (atual.km_atual or 0) and not dados.get("permitir_km_menor"):
            raise ValidacaoError(
                f"A quilometragem informada é menor que a registrada ({atual.km_atual:,} km).".replace(",", "."),
                "km_atual",
            )
        try:
            with self.db.conexao() as conn:
                conn.execute(
                    """UPDATE veiculos SET placa = ?, marca = ?, modelo = ?, ano = ?, cor = ?, km_atual = ?,
                              observacoes = ? WHERE id = ? AND empresa_id = ?""",
                    (*valores, veiculo_id, self.empresa_id),
                )
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, self._ERROS) from erro

    def transferir(self, veiculo_id: int, novo_cliente_id: int) -> None:
        """Troca o proprietário do veículo (venda do carro)."""
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        self.obter(veiculo_id)
        ClienteService(self.db, self.sessao).obter(novo_cliente_id)
        with self.db.conexao() as conn:
            conn.execute("UPDATE veiculos SET cliente_id = ? WHERE id = ? AND empresa_id = ?",
                         (novo_cliente_id, veiculo_id, self.empresa_id))

    def definir_ativo(self, veiculo_id: int, ativo: bool) -> None:
        self.exigir(Permissao.GERENCIAR_CLIENTES)
        self.obter(veiculo_id)
        if not ativo:
            abertas = self.db.escalar(
                f"SELECT COUNT(*) FROM ordens WHERE veiculo_id = ? AND status IN ({_MARCADORES})",
                (veiculo_id, *_STATUS_ABERTOS),
            )
            if abertas:
                raise RegraNegocioError("O veículo possui ordem de serviço em aberto.")
        with self.db.conexao() as conn:
            conn.execute("UPDATE veiculos SET ativo = ? WHERE id = ? AND empresa_id = ?",
                         (1 if ativo else 0, veiculo_id, self.empresa_id))

    def historico(self, veiculo_id: int) -> list[dict]:
        """Todas as OS do veículo, da mais recente para a mais antiga, com as peças trocadas."""
        self.obter(veiculo_id)
        ordens = self.db.consultar(
            """
            SELECT o.id, o.numero, o.status, o.criado_em, o.entregue_em, o.concluido_em, o.km_entrada,
                   o.defeito_relatado, o.diagnostico, o.desconto_centavos, u.nome AS mecanico_nome,
                   COALESCE((SELECT SUM(CAST(ROUND(i.quantidade * i.valor_unitario_centavos) AS INTEGER))
                               FROM ordem_itens i WHERE i.ordem_id = o.id), 0) AS subtotal,
                   (SELECT GROUP_CONCAT(i.descricao, '; ') FROM ordem_itens i
                     WHERE i.ordem_id = o.id AND i.tipo = 'PECA') AS pecas,
                   (SELECT GROUP_CONCAT(i.descricao, '; ') FROM ordem_itens i
                     WHERE i.ordem_id = o.id AND i.tipo = 'SERVICO') AS servicos
              FROM ordens o LEFT JOIN usuarios u ON u.id = o.mecanico_id
             WHERE o.veiculo_id = ? AND o.empresa_id = ?
             ORDER BY o.criado_em DESC, o.id DESC
            """,
            (veiculo_id, self.empresa_id),
        )
        resultado = []
        for r in ordens:
            item = dict(r)
            item["total"] = max(item["subtotal"] - item["desconto_centavos"], 0)
            resultado.append(item)
        return resultado
