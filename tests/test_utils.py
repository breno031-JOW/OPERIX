"""Validações, máscaras, moeda e senhas."""

import pytest

from operix.errors import ValidacaoError
from operix.security import hash_senha, verificar_senha
from operix.utils import formatters as fmt
from operix.utils import validators as val


@pytest.mark.parametrize("texto, esperado", [
    ("150", 15000), ("150,50", 15050), ("1.250,90", 125090), ("R$ 1.250,90", 125090),
    ("1250.90", 125090), ("1.5", 150), ("1.250", 125000), ("0,01", 1), ("0", 0),
])
def test_moeda_para_centavos(texto, esperado):
    assert fmt.moeda_para_centavos(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "1,2,3", "-5", "1.25.0", ""])
def test_moeda_invalida(texto):
    with pytest.raises(ValidacaoError):
        fmt.moeda_para_centavos(texto)


def test_formatar_moeda():
    assert fmt.formatar_moeda(125090) == "R$ 1.250,90"
    assert fmt.formatar_moeda(5) == "R$ 0,05"
    assert fmt.formatar_moeda(123456789, simbolo=False) == "1.234.567,89"


def test_total_item_arredonda():
    assert fmt.total_item(4.5, 4500) == 20250
    assert fmt.total_item(0.333, 100) == 33


def test_cpf_cnpj():
    assert val.validar_documento("529.982.247-25") == "52998224725"
    assert val.validar_documento("11.444.777/0001-61") == "11444777000161"
    for invalido in ("111.111.111-11", "529.982.247-26", "123", "11.444.777/0001-62"):
        with pytest.raises(ValidacaoError):
            val.validar_documento(invalido)
    assert val.formatar_documento("52998224725") == "529.982.247-25"


@pytest.mark.parametrize("entrada, normalizada, exibicao", [
    ("abc-1234", "ABC1234", "ABC-1234"), ("BRA2E19", "BRA2E19", "BRA2E19"), (" bra 2e19 ", "BRA2E19", "BRA2E19"),
])
def test_placas_validas(entrada, normalizada, exibicao):
    assert val.validar_placa(entrada) == normalizada
    assert val.formatar_placa(normalizada) == exibicao


@pytest.mark.parametrize("placa", ["AB1234", "ABCD123", "1234ABC", "ABC12E4", ""])
def test_placas_invalidas(placa):
    with pytest.raises(ValidacaoError):
        val.validar_placa(placa)


def test_mascaras_parciais():
    assert val.mascara_documento_parcial("52998224725") == "529.982.247-25"
    assert val.mascara_documento_parcial("11444777000161") == "11.444.777/0001-61"
    assert val.mascara_telefone_parcial("31988887777") == "(31) 98888-7777"
    assert val.mascara_placa_parcial("abc1234") == "ABC-1234"
    assert val.mascara_placa_parcial("bra2e19") == "BRA2E19"


def test_telefone_email():
    assert val.validar_telefone("(31) 98888-7777") == "31988887777"
    assert val.validar_telefone("") is None
    with pytest.raises(ValidacaoError):
        val.validar_telefone("9999")
    assert val.validar_email(" Nome@Dominio.com ") == "nome@dominio.com"
    with pytest.raises(ValidacaoError):
        val.validar_email("nome@")


def test_hash_senha():
    armazenado = hash_senha("segredo")
    assert armazenado.startswith("pbkdf2_sha256$")
    assert "segredo" not in armazenado
    assert verificar_senha("segredo", armazenado)
    assert not verificar_senha("errada", armazenado)
    assert not verificar_senha("segredo", "lixo")
    assert hash_senha("segredo") != armazenado  # salt aleatório
