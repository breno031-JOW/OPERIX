"""Hash e verificação de senhas (PBKDF2-HMAC-SHA256 com salt aleatório).

Formato armazenado: ``pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>``.
Usa apenas a biblioteca padrão do Python.
"""

import hashlib
import hmac
import secrets

from operix import config

_ALGORITMO = "pbkdf2_sha256"


def hash_senha(senha: str, iteracoes: int | None = None) -> str:
    """Gera o hash seguro de uma senha."""
    iteracoes = iteracoes or config.PBKDF2_ITERACOES
    salt = secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes)
    return f"{_ALGORITMO}${iteracoes}${salt.hex()}${derivado.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    """Confere a senha com o hash armazenado (comparação em tempo constante)."""
    try:
        algoritmo, iteracoes, salt_hex, hash_hex = armazenado.split("$")
        if algoritmo != _ALGORITMO:
            return False
        derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes))
        return hmac.compare_digest(derivado.hex(), hash_hex)
    except (ValueError, AttributeError):
        # Hash corrompido ou em formato desconhecido
        return False


def precisa_rehash(armazenado: str) -> bool:
    """Indica se o hash usa menos iterações que a configuração atual."""
    try:
        return int(armazenado.split("$")[1]) < config.PBKDF2_ITERACOES
    except (IndexError, ValueError):
        return True
