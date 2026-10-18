# Instalação

O Curupira é um programa de linha de comando em Rust. Instale esse mesmo programa com npm ou
pelo PyPI. Os dois comandos são `curupira` e `curu`, e ambos usam `~/.curupira/` para
`settings.toml`, o arquivo de estado SQLite, workspaces e worktrees. Migrar do pip para o npm mantém esse diretório; o pacote npm não cria um
segundo caminho de configuração.

O repositório do código-fonte é [caipora-labs/curupira](https://github.com/caipora-labs/curupira).

## Requisitos

{{ requirements_list("pt") }}

Os binários publicados cobrem:

- Linux x64 e ARM64 com glibc
- Linux x64 e ARM64 com musl (Alpine)
- macOS x64 (Intel) e ARM64 (Apple Silicon)
- Windows x64 e ARM64

Sistemas de 32 bits e outros sistemas operacionais não são publicados. A instalação não
compila Rust e não precisa de toolchain Rust. O comando npm é um pequeno wrapper em Node.js
que executa diretamente o binário pré-compilado: ele não altera o diretório de trabalho, o
ambiente nem a configuração, e encerra com o status do processo Rust. Uma listagem de
processos mostra o Node.js como pai desse processo. O processo Rust é o que mantém o
`~/.curupira/dispatch.lock`.

`import curupira` e `curupira.__version__` existem apenas na instalação pelo PyPI. Os plugins
são iniciados pelo launcher definido no `settings.toml` (`uvx` ou `npx`), com qualquer uma das
instalações. O Curupira não instala Python nem um ambiente Node.js privado para eles. Se `uvx`
ou `npx` não estiver disponível, a validação informa que o launcher não foi encontrado no `PATH`.

## Instalar com Node.js

```bash
npm install -g @caipora-labs/curupira
```

Execute uma vez sem instalação global:

```bash
npx @caipora-labs/curupira --help
```

O pacote npm único inclui binários para todos os sistemas operacionais, CPUs e bibliotecas C
suportados. Ele seleciona o binário correspondente ao executar o comando; não há outros
pacotes de plataforma para instalar. Consulte o [README do pacote](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-cli-js/README.md)
para ver as plataformas suportadas.
Os conectores não estão incluídos: você os registra em `[plugins.<alias>]` nas suas
configurações, veja [Plugins e conectores](plugins.md).

## Instalar com Python

O [`uv`](https://docs.astral.sh/uv/) instala o wheel da plataforma a partir do PyPI. O wheel
contém a CLI em Rust. O Python é usado para empacotamento e para extensões `uvx` opcionais,
não para interpretar a CLI.

```bash
uv tool install curupira
# or
pip install curupira
```

O cron embutido funciona de imediato. Conectores como o do GitHub são registrados nas suas
configurações, veja [Plugins e conectores](plugins.md).

Para fixar uma versão específica, use `uv tool install "curupira==X.Y.Z"`.

## Verificar a instalação

`curupira --version` e `curu --version` exibem a versão instalada. Valide uma
configuração sem chamar as CLIs dos agentes:

```bash
curupira --config curupira.example.toml validate
```

## Criar uma configuração

O Curupira lê `~/.curupira/settings.toml` por padrão. Baixe a configuração de exemplo:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-cli/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

No Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-cli/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edite repositórios, consultas e prompts no TOML. O diretório `~/.curupira` também guarda o estado e os workspaces. Passe `--config caminho/para/settings.toml` para usar outro arquivo.
