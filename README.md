🛠️ Operix - Gestão Inteligente de Operações

Operix é um sistema desktop desenvolvido em Python para gestão integrada de clientes, ativos, orçamentos e ordens de serviço (OS). O sistema foi projetado para pequenos e médios negócios (como oficinas mecânicas, assistências técnicas e prestadores de serviços) acompanharem todo o fluxo operacional em uma interface simples e moderna.

🚀 Funcionalidades

🔒 Autenticação & Gestão de Acesso: Tela de login integrada ao banco de dados com suporte a diferentes perfis de usuário e empresas.

📊 Dashboard Interativo: Exibição de métricas em tempo real (orçamentos pendentes, ordens de serviço em andamento e total de clientes).

👥 Clientes & Ativos: Cadastro unificado de clientes e seus respectivos ativos (veículos, equipamentos, dispositivos).

📝 Gestão de Orçamentos: Criação de orçamentos vinculados aos clientes e ativos.

🛠️ Ordens de Serviço (OS): Conversão automática de orçamentos aprovados em Ordens de Serviço e acompanhamento do status de execução até a conclusão.

🛠️ Tecnologias Utilizadas

Linguagem: Python 3

Interface Gráfica: Tkinter / ttk (com tema customizado)

Banco de Dados: SQLite3 (relacional, sem necessidade de servidor externo)

Paradigma de Programação: Orientação a Objetos (POO) com classes abstratas (abc)

🗂️ Arquitetura do Projeto

O código está estruturado em uma arquitetura limpa dentro de um único módulo:

Camada de Persistência (Database): Gerencia a criação de tabelas (empresas, usuarios, clientes, ativos, orcamentos, ordens_servico) e a carga inicial de dados de teste.

Modelos do Domínio (POO): Representação das entidades do sistema (Usuario, Ativo, Veiculo), utilizando conceitos de herança e polimorfismo.

Interface Gráfica (OperixApp): Gerencia as telas de Login, Dashboard, Clientes, Orçamentos e Ordens de Serviço com navegação por menu lateral (Sidebar).

🏁 Como Executar o Projeto

Pré-requisitos

Python 3.8 ou superior instalado no seu sistema.

Nota: A biblioteca tkinter já vem instalada por padrão com o Python no Windows e macOS. No Linux, caso receba um erro de importação, instale via gerenciador de pacotes (ex: sudo apt install python3-tk).

Passos para execução

Clone ou baixe este repositório para a sua máquina:

git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio


Execute o arquivo principal da aplicação:

python login_app.py
