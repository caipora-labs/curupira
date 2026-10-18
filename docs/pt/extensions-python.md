# SDK Python

O `curupira-sdk` (import `curupira_sdk`) transforma funções Python comuns em triggers do
Curupira. Por padrão ele usa apenas a biblioteca padrão; o suporte a Pydantic é opcional. Os
[conector do GitHub](plugins.md) é escrito com ele.

## Instalação { #install }

```sh
pip install curupira-sdk
# modelos estruturados opcionais:
pip install 'curupira-sdk[pydantic]'
```

Declare o `curupira-sdk` como dependência do seu pacote e exponha um console script, para que
o `uvx` possa executá-lo diretamente.

## Um trigger mínimo { #minimal-trigger }

```python
from dataclasses import dataclass

from curupira_sdk import Curupira

app = Curupira(name="acme-issues", version="0.1.0")


@dataclass
class Issue:
    number: int
    title: str
    url: str


@app.trigger  # (1)!
async def github_issues(
    repo: str,  # (2)!
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Retorna a próxima issue, ou None quando nada foi encontrado."""
    return None  # (3)!


def main() -> None:
    app.run()  # (4)!


if __name__ == "__main__":
    main()
```

1.  O nome local do trigger é o nome da função em kebab-case: `github-issues`. Use
    `@app.trigger(alias="issues")` para escolher outro nome.
2.  Os parâmetros são as configurações da automação. Valores obrigatórios, opcionais e padrões vêm
    da assinatura e dos type hints.
3.  Retorne **um** objeto, ou `None` quando nada foi encontrado.
4.  Fala o protocolo por stdin e stdout. Escreva logs no stderr, nunca no stdout.

## Use-o nas configurações { #settings }

Registre o pacote sob um alias e coloque os parâmetros do trigger ao lado dos campos
centrais da automação:

```toml
[plugins.acme]
type = "uvx"
args = ["--from", "acme-issues==0.1.0", "acme-issues"]

[automations.resolve-ready-issues]
trigger_type = "acme/github-issues"
repository = "api"          # central: o alias do checkout
repo = "acme/api"           # parâmetro do trigger
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`trigger_type`, `repository`, `prompt`, `profile` e `checkout` são campos centrais. Não
os use como nomes de parâmetro; use `repo` ou outro nome para ids da forge. O prompt pode usar
exatamente os campos que o seu trigger retorna: `number`, `title` e `url` aqui, porque
`Issue` os declara.

## Regras { #rules }

- Retorne **um** objeto ou `None`. `None` significa que nada foi encontrado. Listas, tuplas, sets
  e iteradores são rejeitados, incluindo uma lista de pares montada à mão.
- Um mapeamento vazio é um item sem campos, e não "nada encontrado".
- `def` síncrono e `async def` compartilham o mesmo decorator.
- O host não passa `preview` nem `limit` para a função.
- Mapeamentos, dataclasses e TypedDicts funcionam sem configuração extra. Modelos Pydantic v2 precisam de
  `curupira-sdk[pydantic]`.
- O SDK não adiciona `id`, `title`, `url` nem nenhum outro campo. O que você retorna é o que
  o prompt recebe.
- O host cuida das consultas, da concorrência, do Git, dos worktrees e dos agentes de código. O SDK nunca
  agenda nem repete trabalho.

## Como um valor de retorno vira campos { #serialization }

O SDK achata o objeto retornado em pares de strings `{ "key", "value" }` antes que ele
chegue ao host. As chaves de nível superior mantêm a ordem de declaração ou de inserção.

| Valor Python | Valor do campo |
| --- | --- |
| `str` | a mesma string, sem aspas extras |
| `bool` | `true` ou `false` |
| `int` | texto decimal (`1` e `1.0` continuam distintos) |
| `float` | o mesmo texto que `json.dumps` emitiria |
| `None` | `null` (um valor de campo, e não "nada encontrado") |
| mapeamento, lista, tupla, dataclass ou modelo aninhado | JSON compacto (`sort_keys=True`, sem espaços extras) |

Estes casos levantam `SerializationError`, que chega ao host como um erro JSON-RPC, e não como
"nada encontrado":

- uma lista, tupla, set, gerador ou outra coleção no nível superior
- uma string, número ou booleano no nível superior
- uma chave que não é string (as chaves não são convertidas com `str`)
- uma chave vazia, ou uma chave que contém `}` ou `${`
- uma chave duplicada
- um float não finito, `bytes`, `set`, `datetime` ou qualquer outro valor que não possa ser serializado

O `describe` pode listar `prompt_fields` obtidos do tipo de retorno declarado. Essa lista é uma
dica para editores e para a documentação. Ela não torna nenhuma chave obrigatória.

## Publique { #ship }

- Adicione um manifesto `curupira-extension.toml` e suporte `--curupira-print-manifest` para que
  `curupira plugins list` possa descrever o pacote. Veja
  [Manifesto](extensions-protocol.md#manifest).
- Teste com `curupira validate` e `curupira run --dry-run` apontando para um caminho local:
  `args = ["--from", "/path/to/your/package", "acme-issues"]`.

Exemplos no repositório:

- `packages/curupira-python-plugins/src/curupira_plugins/__main__.py`: o conector do GitHub,
  um exemplo completo do SDK.
- `packages/curupira-core/tests/fixtures/python-ext/`: uma fixture mínima do protocolo sem
  o SDK.
