"""Indicadores operacionais e financeiros."""

from datetime import date, timedelta

from operix.models import Permissao, StatusOrdem
from operix.services.base import ServicoBase
from operix.services.ordens import SQL_PAGO, SQL_SUBTOTAL


def periodo_mes_atual() -> tuple[date, date]:
    hoje = date.today()
    inicio = hoje.replace(day=1)
    proximo = (inicio + timedelta(days=32)).replace(day=1)
    return inicio, proximo - timedelta(days=1)


class DashboardService(ServicoBase):
    def operacional(self) -> dict:
        """Contadores do dia a dia (visíveis para todos os perfis)."""
        self.exigir(Permissao.VER_DASHBOARD)
        filtro_mecanico = ""
        parametros: list = [self.empresa_id]
        if not self.sessao.pode(Permissao.VER_TODAS_ORDENS):
            filtro_mecanico = " AND (mecanico_id = ? OR (mecanico_id IS NULL AND status = 'APROVADA'))"
            parametros.append(self.usuario.id)
        linhas = self.db.consultar(
            f"SELECT status, COUNT(*) AS qtd FROM ordens WHERE empresa_id = ?{filtro_mecanico} GROUP BY status",
            tuple(parametros),
        )
        por_status = {s: 0 for s in StatusOrdem}
        for linha in linhas:
            por_status[StatusOrdem(linha["status"])] = linha["qtd"]

        estoque_baixo = self.db.escalar(
            "SELECT COUNT(*) FROM pecas WHERE empresa_id = ? AND ativo = 1 AND estoque_minimo > 0 "
            "AND estoque <= estoque_minimo",
            (self.empresa_id,),
        )
        clientes = self.db.escalar("SELECT COUNT(*) FROM clientes WHERE empresa_id = ? AND ativo = 1",
                                   (self.empresa_id,))
        no_patio = sum(q for s, q in por_status.items() if s.em_aberto)
        return {
            "por_status": por_status,
            "orcamentos_pendentes": por_status[StatusOrdem.ORCAMENTO],
            "em_execucao": por_status[StatusOrdem.EM_EXECUCAO] + por_status[StatusOrdem.APROVADA],
            "aguardando_peca": por_status[StatusOrdem.AGUARDANDO_PECA],
            "prontas": por_status[StatusOrdem.CONCLUIDA],
            "no_patio": no_patio,
            "estoque_baixo": estoque_baixo,
            "clientes": clientes,
        }

    def financeiro(self, inicio: date, fim: date) -> dict:
        """Resumo financeiro do período (somente administrador)."""
        self.exigir(Permissao.VER_FINANCEIRO)
        ini, fim_txt = inicio.isoformat(), f"{fim.isoformat()} 23:59:59"
        p = (self.empresa_id, ini, fim_txt)

        recebido = self.db.escalar(
            "SELECT COALESCE(SUM(valor_centavos), 0) FROM pagamentos WHERE empresa_id = ? AND data BETWEEN ? AND ?", p
        )
        por_forma = [dict(r) for r in self.db.consultar(
            """SELECT forma, SUM(valor_centavos) AS total, COUNT(*) AS qtd FROM pagamentos
                WHERE empresa_id = ? AND data BETWEEN ? AND ? GROUP BY forma ORDER BY total DESC""", p)]

        # OS finalizadas no período (concluídas ou entregues), pela data de conclusão
        finalizadas = self.db.consultar(
            f"""SELECT o.id, {SQL_SUBTOTAL} - o.desconto_centavos AS total,
                       COALESCE((SELECT SUM(CAST(ROUND(i.quantidade * i.valor_unitario_centavos) AS INTEGER))
                                   FROM ordem_itens i WHERE i.ordem_id = o.id AND i.tipo = 'PECA'), 0) AS pecas,
                       COALESCE((SELECT SUM(CAST(ROUND(i.quantidade * p.custo_centavos) AS INTEGER))
                                   FROM ordem_itens i JOIN pecas p ON p.id = i.peca_id
                                  WHERE i.ordem_id = o.id AND i.tipo = 'PECA'), 0) AS custo_pecas
                  FROM ordens o
                 WHERE o.empresa_id = ? AND o.status IN ('CONCLUIDA', 'ENTREGUE')
                   AND o.concluido_em BETWEEN ? AND ?""", p)
        faturado = sum(max(r["total"], 0) for r in finalizadas)
        qtd_finalizadas = len(finalizadas)
        receita_pecas = sum(r["pecas"] for r in finalizadas)
        custo_pecas = sum(r["custo_pecas"] for r in finalizadas)

        a_receber = self.db.consultar(
            f"""SELECT o.id, o.numero, c.nome AS cliente_nome, c.telefone, o.status, v.placa,
                       {SQL_SUBTOTAL} - o.desconto_centavos AS total, {SQL_PAGO} AS pago
                  FROM ordens o JOIN clientes c ON c.id = o.cliente_id JOIN veiculos v ON v.id = o.veiculo_id
                 WHERE o.empresa_id = ? AND o.status IN ('APROVADA', 'EM_EXECUCAO', 'AGUARDANDO_PECA',
                                                         'CONCLUIDA', 'ENTREGUE')""",
            (self.empresa_id,),
        )
        pendencias = []
        for r in a_receber:
            saldo = max(r["total"], 0) - r["pago"]
            if saldo > 0:
                pendencias.append({**dict(r), "saldo": saldo})
        pendencias.sort(key=lambda x: (x["status"] != "ENTREGUE", -x["saldo"]))

        top_pecas = [dict(r) for r in self.db.consultar(
            """SELECT i.descricao, SUM(i.quantidade) AS quantidade,
                      SUM(CAST(ROUND(i.quantidade * i.valor_unitario_centavos) AS INTEGER)) AS total
                 FROM ordem_itens i JOIN ordens o ON o.id = i.ordem_id
                WHERE o.empresa_id = ? AND i.tipo = 'PECA' AND o.status IN ('CONCLUIDA', 'ENTREGUE')
                  AND o.concluido_em BETWEEN ? AND ?
                GROUP BY i.peca_id ORDER BY quantidade DESC LIMIT 10""", p)]

        return {
            "recebido": recebido,
            "faturado": faturado,
            "qtd_finalizadas": qtd_finalizadas,
            "ticket_medio": faturado // qtd_finalizadas if qtd_finalizadas else 0,
            "receita_pecas": receita_pecas,
            "receita_servicos": faturado - receita_pecas if faturado > receita_pecas else 0,
            "lucro_bruto_pecas": receita_pecas - custo_pecas,
            "por_forma": por_forma,
            "a_receber_total": sum(x["saldo"] for x in pendencias),
            "a_receber": pendencias,
            "top_pecas": top_pecas,
        }
