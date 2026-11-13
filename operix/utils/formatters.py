"""Conversão de valores monetários, quantidades e datas.

Valores em dinheiro são guardados no banco como **centavos (int)** para evitar
erros de arredondamento de ponto flutuante (ex.: 0.1 + 0.2 != 0.3).
"""

import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from operix.errors import ValidacaoError

FORMATO_DATA_BANCO = "%Y-%m-%d %H:%M:%S"


def _texto_para_decimal(texto: str) -> Decimal:
    """Interpreta números no padrão brasileiro e também com ponto decimal.

    Regras:
    - ``1.250,90`` -> ponto é milhar, vírgula é decimal;
    - ``150,5``    -> vírgula é decimal;
    - ``1250.90`` / ``1.5`` -> um único ponto seguido de 1 ou 2 dígitos é decimal;
    - ``1.250`` / ``1.250.000`` -> pontos separando grupos de 3 são milhar.
    """
    limpo = texto.strip().replace("R$", "").replace(" ", "")
    if not limpo:
        raise InvalidOperation
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") == 1 and re.fullmatch(r"-?\d+\.\d{1,2}", limpo):
        pass  # ponto decimal
    elif "." in limpo:
        if not re.fullmatch(r"-?\d{1,3}(\.\d{3})+", limpo):
            raise InvalidOperation
        limpo = limpo.replace(".", "")
    return Decimal(limpo)


def moeda_para_centavos(texto, rotulo: str = "Valor", permitir_zero: bool = True) -> int:
    """Converte o texto digitado (ex.: 'R$ 1.250,90') em centavos (125090)."""
    if isinstance(texto, int):
        valor = Decimal(texto)
    else:
        try:
            valor = _texto_para_decimal(str(texto))
        except (InvalidOperation, ValueError):
            raise ValidacaoError(
                f"{rotulo} inválido. Use o formato 150, 150,50 ou 1.250,90.", rotulo
            ) from None
    if valor < 0:
        raise ValidacaoError(f"{rotulo} não pode ser negativo.", rotulo)
    if valor == 0 and not permitir_zero:
        raise ValidacaoError(f"{rotulo} deve ser maior que zero.", rotulo)
    if valor > Decimal("10000000"):
        raise ValidacaoError(f"{rotulo} muito alto. Confira o valor digitado.", rotulo)
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatar_moeda(centavos: int | None, simbolo: bool = True) -> str:
    """125090 -> 'R$ 1.250,90'."""
    centavos = int(centavos or 0)
    sinal = "-" if centavos < 0 else ""
    reais, cent = divmod(abs(centavos), 100)
    texto = f"{reais:,}".replace(",", ".") + f",{cent:02d}"
    return f"{sinal}R$ {texto}" if simbolo else f"{sinal}{texto}"


def texto_para_quantidade(texto, rotulo: str = "Quantidade", permitir_zero: bool = False) -> float:
    """Quantidade de peças (aceita fração, ex.: 4,5 litros de óleo)."""
    if permitir_zero and str(texto if texto is not None else "").strip() == "":
        return 0.0
    try:
        valor = _texto_para_decimal(str(texto))
    except (InvalidOperation, ValueError):
        raise ValidacaoError(f"{rotulo} inválida. Exemplo: 1, 2 ou 4,5.", rotulo) from None
    if valor < 0 or (valor == 0 and not permitir_zero):
        raise ValidacaoError(f"{rotulo} deve ser maior que zero.", rotulo)
    if valor > 100000:
        raise ValidacaoError(f"{rotulo} muito alta. Confira o valor digitado.", rotulo)
    return float(valor.quantize(Decimal("0.001")))


def formatar_quantidade(valor: float | None) -> str:
    """4.0 -> '4' ; 4.5 -> '4,5'."""
    valor = float(valor or 0)
    if valor == int(valor):
        return str(int(valor))
    return f"{valor:.3f}".rstrip("0").replace(".", ",")


def total_item(quantidade: float, valor_unitario_centavos: int) -> int:
    """Total de um item em centavos, arredondado ao centavo mais próximo."""
    total = Decimal(str(quantidade)) * Decimal(int(valor_unitario_centavos))
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def agora() -> str:
    """Data/hora atual no formato gravado no banco."""
    return datetime.now().strftime(FORMATO_DATA_BANCO)


def formatar_data(valor: str | None, com_hora: bool = True) -> str:
    """'2026-11-13 14:30:00' -> '13/11/2026 14:30'."""
    if not valor:
        return ""
    for formato in (FORMATO_DATA_BANCO, "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            data = datetime.strptime(valor, formato)
            return data.strftime("%d/%m/%Y %H:%M" if com_hora and formato != "%Y-%m-%d" else "%d/%m/%Y")
        except ValueError:
            continue
    return valor


def normalizar_busca(texto: str | None) -> str:
    """Minúsculas e sem acentos, para buscas tolerantes ('Joao' acha 'João')."""
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()
