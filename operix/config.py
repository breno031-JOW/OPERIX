"""Configurações gerais do Operix.

Todos os caminhos podem ser sobrescritos por variáveis de ambiente, o que
facilita testes e instalações em pastas diferentes:

- ``OPERIX_DB``: caminho do arquivo SQLite;
- ``OPERIX_DOCS``: pasta onde os PDFs são salvos;
- ``OPERIX_LOG``: caminho do arquivo de log.
"""

import os
from pathlib import Path

APP_NOME = "Operix"
APP_SUBTITULO = "Gestão inteligente para oficinas mecânicas"

# Pasta raiz do projeto (uma acima do pacote ``operix``)
PASTA_RAIZ = Path(__file__).resolve().parent.parent

CAMINHO_BANCO = Path(os.environ.get("OPERIX_DB", PASTA_RAIZ / "operix.db"))
PASTA_DOCUMENTOS = Path(os.environ.get("OPERIX_DOCS", PASTA_RAIZ / "documentos"))
CAMINHO_LOG = Path(os.environ.get("OPERIX_LOG", PASTA_RAIZ / "operix.log"))

# Tema visual do ttkbootstrap (claro). Alternativa escura: "darkly".
TEMA_PADRAO = "flatly"

# Iterações do PBKDF2 (recomendação OWASP para PBKDF2-HMAC-SHA256)
PBKDF2_ITERACOES = 600_000

# Tamanho mínimo de senha
SENHA_MINIMA = 6
