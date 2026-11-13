"""Validação e formatação de documentos e campos brasileiros.

Convenção: as funções ``validar_*`` recebem o texto digitado pelo usuário,
levantam :class:`ValidacaoError` com mensagem clara quando o dado é inválido e
devolvem o valor **normalizado** para gravação no banco (ex.: CPF só com
dígitos, placa em maiúsculas e sem hífen). As funções ``formatar_*`` fazem o
caminho inverso, para exibição.
"""

import re
from datetime import date

from operix.errors import ValidacaoError

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_RE_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")
_RE_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def somente_digitos(texto: str | None) -> str:
    """Remove tudo que não for dígito."""
    return re.sub(r"\D", "", texto or "")


# ----------------------------------------------------------------- CPF / CNPJ
def cpf_valido(cpf: str) -> bool:
    """Confere os dígitos verificadores de um CPF (aceita com ou sem máscara)."""
    numeros = somente_digitos(cpf)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(numeros[i]) * (posicao + 1 - i) for i in range(posicao))
        digito = (soma * 10) % 11 % 10
        if digito != int(numeros[posicao]):
            return False
    return True


def cnpj_valido(cnpj: str) -> bool:
    """Confere os dígitos verificadores de um CNPJ (aceita com ou sem máscara)."""
    numeros = somente_digitos(cnpj)
    if len(numeros) != 14 or numeros == numeros[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, posicao in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(n) * p for n, p in zip(numeros[:posicao], pesos, strict=True))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(numeros[posicao]):
            return False
    return True


def validar_documento(documento: str) -> str:
    """Valida CPF (11 dígitos) ou CNPJ (14 dígitos) e devolve só os dígitos."""
    numeros = somente_digitos(documento)
    if not numeros:
        raise ValidacaoError("Informe o CPF ou CNPJ do cliente.", "documento")
    if len(numeros) == 11:
        if not cpf_valido(numeros):
            raise ValidacaoError("CPF inválido. Confira os números digitados.", "documento")
    elif len(numeros) == 14:
        if not cnpj_valido(numeros):
            raise ValidacaoError("CNPJ inválido. Confira os números digitados.", "documento")
    else:
        raise ValidacaoError("O documento deve ser um CPF (11 dígitos) ou CNPJ (14 dígitos).", "documento")
    return numeros


def validar_cnpj_opcional(cnpj: str | None) -> str | None:
    """CNPJ opcional (dados da oficina). Vazio é aceito."""
    numeros = somente_digitos(cnpj)
    if not numeros:
        return None
    if not cnpj_valido(numeros):
        raise ValidacaoError("CNPJ inválido. Confira os números digitados.", "cnpj")
    return numeros


def formatar_documento(documento: str | None) -> str:
    """Aplica a máscara de CPF (000.000.000-00) ou CNPJ (00.000.000/0000-00)."""
    n = somente_digitos(documento)
    if len(n) == 11:
        return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return documento or ""


def mascara_documento_parcial(texto: str) -> str:
    """Máscara aplicada enquanto o usuário digita (decide CPF/CNPJ pelo tamanho)."""
    n = somente_digitos(texto)[:14]
    if len(n) <= 11:
        partes = [(0, 3, ""), (3, 6, "."), (6, 9, "."), (9, 11, "-")]
    else:
        partes = [(0, 2, ""), (2, 5, "."), (5, 8, "."), (8, 12, "/"), (12, 14, "-")]
    saida = ""
    for inicio, fim, separador in partes:
        trecho = n[inicio:fim]
        if trecho:
            saida += separador + trecho
    return saida


# ---------------------------------------------------------------------- placa
def normalizar_placa(placa: str | None) -> str:
    """Maiúsculas e somente letras/números (ABC-1234 -> ABC1234)."""
    return re.sub(r"[^A-Za-z0-9]", "", placa or "").upper()


def validar_placa(placa: str) -> str:
    """Valida placa no padrão antigo (ABC-1234) ou Mercosul (ABC1D23)."""
    normalizada = normalizar_placa(placa)
    if not normalizada:
        raise ValidacaoError("Informe a placa do veículo.", "placa")
    if not (_RE_PLACA_ANTIGA.match(normalizada) or _RE_PLACA_MERCOSUL.match(normalizada)):
        raise ValidacaoError(
            "Placa inválida. Use o padrão antigo (ABC-1234) ou Mercosul (ABC1D23).", "placa"
        )
    return normalizada


def formatar_placa(placa: str | None) -> str:
    """Exibe a placa antiga com hífen; a Mercosul fica sem hífen."""
    p = normalizar_placa(placa)
    if _RE_PLACA_ANTIGA.match(p):
        return f"{p[:3]}-{p[3:]}"
    return p


def mascara_placa_parcial(texto: str) -> str:
    """Máscara aplicada enquanto o usuário digita a placa."""
    p = normalizar_placa(texto)[:7]
    if len(p) > 3 and len(p) >= 5 and p[4].isdigit():
        return f"{p[:3]}-{p[3:]}"
    return p


# ------------------------------------------------------------ telefone/e-mail
def validar_telefone(telefone: str | None, obrigatorio: bool = False) -> str | None:
    """Telefone com DDD: 10 dígitos (fixo) ou 11 dígitos (celular)."""
    n = somente_digitos(telefone)
    if not n:
        if obrigatorio:
            raise ValidacaoError("Informe o telefone com DDD.", "telefone")
        return None
    if len(n) not in (10, 11):
        raise ValidacaoError("Telefone inválido. Informe o DDD + número, ex.: (31) 98888-7777.", "telefone")
    return n


def formatar_telefone(telefone: str | None) -> str:
    n = somente_digitos(telefone)
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return telefone or ""


def mascara_telefone_parcial(texto: str) -> str:
    n = somente_digitos(texto)[:11]
    if not n:
        return ""
    if len(n) <= 2:
        return f"({n}"
    meio = 5 if len(n) == 11 else 4
    if len(n) <= 2 + meio:
        return f"({n[:2]}) {n[2:]}"
    return f"({n[:2]}) {n[2:2 + meio]}-{n[2 + meio:]}"


def validar_email(email: str | None, obrigatorio: bool = False) -> str | None:
    texto = (email or "").strip().lower()
    if not texto:
        if obrigatorio:
            raise ValidacaoError("Informe o e-mail.", "email")
        return None
    if not _RE_EMAIL.match(texto):
        raise ValidacaoError("E-mail inválido. Exemplo: nome@dominio.com", "email")
    return texto


# ------------------------------------------------------------------ genéricos
def validar_texto(valor: str | None, rotulo: str, obrigatorio: bool = True, maximo: int = 200) -> str | None:
    """Remove espaços extras e confere obrigatoriedade/tamanho."""
    texto = " ".join((valor or "").split())
    if not texto:
        if obrigatorio:
            raise ValidacaoError(f"O campo '{rotulo}' é obrigatório.", rotulo)
        return None
    if len(texto) > maximo:
        raise ValidacaoError(f"O campo '{rotulo}' aceita no máximo {maximo} caracteres.", rotulo)
    return texto


def validar_texto_longo(valor: str | None, maximo: int = 4000) -> str | None:
    """Textos multilinha (defeito, diagnóstico): mantém quebras de linha."""
    texto = (valor or "").strip()
    if len(texto) > maximo:
        raise ValidacaoError(f"Texto muito longo (máximo {maximo} caracteres).")
    return texto or None


def validar_inteiro(valor, rotulo: str, obrigatorio: bool = False, minimo: int = 0, maximo: int | None = None):
    """Converte para inteiro (aceita '120.000' como 120000)."""
    if valor is None or str(valor).strip() == "":
        if obrigatorio:
            raise ValidacaoError(f"O campo '{rotulo}' é obrigatório.", rotulo)
        return None
    texto = str(valor).strip().replace(".", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+", texto):
        raise ValidacaoError(f"O campo '{rotulo}' deve ser um número inteiro.", rotulo)
    numero = int(texto)
    if numero < minimo or (maximo is not None and numero > maximo):
        faixa = f"entre {minimo} e {maximo}" if maximo is not None else f"maior ou igual a {minimo}"
        raise ValidacaoError(f"O campo '{rotulo}' deve ser {faixa}.", rotulo)
    return numero


def validar_ano_veiculo(valor) -> int | None:
    return validar_inteiro(valor, "Ano", minimo=1900, maximo=date.today().year + 1)
