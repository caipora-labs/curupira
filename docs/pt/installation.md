# Instalação

## Requisitos

{{ requirements_list("pt") }}

- [`uv`](https://docs.astral.sh/uv/) para instalar a aplicação.

## Instalar

Instale o pacote publicado no PyPI. O repositório do código-fonte é
[caipora-labs/curupira](https://github.com/caipora-labs/curupira).
O pacote é Python puro (`py3-none-any`), então a instalação não exige toolchain de compilação
em nenhuma plataforma suportada.

```bash
uv tool install curupira
```

Isso instala apenas a CLI em Rust. O cron embutido funciona de imediato. Para fontes de tarefas de
forges, adicione um extra opcional (ou use `curupira plugins install`). Os extras instalam o pacote
consolidado `curupira-plugins`:

```bash
uv tool install 'curupira[extensions]'
# extras com nome de forge (github) instalam o mesmo pacote
uv tool install 'curupira[github]'
```

Para fixar uma versão específica, use `uv tool install "curupira==X.Y.Z"`.

Confirme que o comando está disponível com `curupira --version`. O alias curto `curu --version` executa o mesmo programa. Valide uma configuração sem chamar as CLIs dos agentes:

```bash
curupira --config curupira.example.toml validate
```

## Criar uma configuração

O Curupira lê `~/.curupira/settings.toml` por padrão. Baixe a configuração de exemplo:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

No Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edite repositórios, consultas e prompts no TOML. O diretório `~/.curupira` também guarda o estado e os logs. Passe `--config caminho/para/settings.toml` para usar outro arquivo.
