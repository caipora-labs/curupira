# SDK de Python

`curupira-sdk` (import `curupira_sdk`) convierte funciones de Python comunes en triggers de
Curupira. Por defecto solo usa la stdlib; el soporte para Pydantic es opcional. Los
[conector de GitHub](plugins.md) está escrito con él.

## Instalar { #install }

```sh
pip install curupira-sdk
# modelos estructurados opcionales:
pip install 'curupira-sdk[pydantic]'
```

Declara `curupira-sdk` como dependencia de tu paquete y expón un script de consola, para
que `uvx` pueda ejecutarlo directamente.

## Un trigger mínimo { #minimal-trigger }

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
    """Return the next issue, or None when nothing was found."""
    return None  # (3)!


def main() -> None:
    app.run()  # (4)!


if __name__ == "__main__":
    main()
```

1.  El nombre local del trigger es el nombre de la función en kebab-case: `github-issues`.
    Usa `@app.trigger(alias="issues")` para elegir otro nombre.
2.  Los parámetros son los ajustes de la automatización. Los valores obligatorios,
    opcionales y predeterminados salen de la firma y de las anotaciones de tipo.
3.  Devuelve **un** objeto, o `None` cuando no se encontró nada.
4.  Habla el protocolo por stdin y stdout. Escribe los logs en stderr, nunca en stdout.

## Usarlo desde los ajustes { #settings }

Registra el paquete con un alias y luego coloca los parámetros del trigger junto a los
campos principales de la automatización:

```toml
[plugins.acme]
type = "uvx"
args = ["--from", "acme-issues==0.1.0", "acme-issues"]

[automations.resolve-ready-issues]
trigger_type = "acme/github-issues"
repository = "api"          # principal: el alias del checkout
repo = "acme/api"           # parámetro del trigger
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`trigger_type`, `repository`, `prompt`, `profile` y `checkout` son campos principales. No
los uses como nombres de parámetros; usa `repo` u otro nombre para los ids de la forja. El
prompt puede usar exactamente los campos que devuelve tu trigger: aquí `number`, `title` y
`url`, porque `Issue` los declara.

## Reglas { #rules }

- Devuelve **un** objeto o `None`. `None` significa que no se encontró nada. Las listas,
  tuplas, sets e iteradores se rechazan, incluida una lista de pares construida a mano.
- Un mapping vacío es un elemento sin campos, no "no se encontró nada".
- `def` síncrono y `async def` comparten el mismo decorador.
- El host no pasa `preview` ni `limit` a la función.
- Los mappings, dataclasses y TypedDicts funcionan sin configuración adicional. Los modelos
  de Pydantic v2 necesitan `curupira-sdk[pydantic]`.
- El SDK no agrega `id`, `title`, `url` ni ningún otro campo. Lo que devuelves es lo que
  recibe el prompt.
- El host se encarga del polling, la concurrencia, Git, los worktrees y los agentes de
  código. El SDK nunca planifica ni reintenta trabajo.

## Cómo un valor devuelto se convierte en campos { #serialization }

El SDK aplana el objeto devuelto en pares de cadenas `{ "key", "value" }` antes de que
llegue al host. Las claves de primer nivel conservan su orden de declaración o de inserción.

| Valor de Python | Valor del campo |
| --- | --- |
| `str` | la misma cadena, sin comillas adicionales |
| `bool` | `true` o `false` |
| `int` | texto decimal (`1` y `1.0` siguen siendo distintos) |
| `float` | el mismo texto que emitiría `json.dumps` |
| `None` | `null` (un valor de campo, no "no se encontró nada") |
| mapping, lista, tupla, dataclass o modelo anidado | JSON compacto (`sort_keys=True`, sin espacios adicionales) |

Estos casos lanzan `SerializationError`, que llega al host como un error JSON-RPC, no como
"no se encontró nada":

- una lista, tupla, set, generador u otra colección de primer nivel
- una cadena, número o booleano de primer nivel
- una clave que no es una cadena (las claves no se convierten con `str`)
- una clave vacía, o una clave que contiene `}` o `${`
- una clave duplicada
- un float no finito, `bytes`, `set`, `datetime` o cualquier otro valor que no se pueda serializar

`describe` puede listar `prompt_fields` tomados del tipo de retorno declarado. Esa lista es
una pista para editores y documentación. No hace obligatoria ninguna clave.

## Publícalo { #ship }

- Agrega un manifiesto `curupira-extension.toml` y admite `--curupira-print-manifest` para
  que `curupira plugins list` pueda describir el paquete. Consulta
  [Manifiesto](extensions-protocol.md#manifest).
- Prueba con `curupira validate` y `curupira run --dry-run` contra una ruta local:
  `args = ["--from", "/path/to/your/package", "acme-issues"]`.

Ejemplos en el repositorio:

- `packages/curupira-plugins-py/src/curupira_plugins/__main__.py`: el conector de
  GitHub, un ejemplo completo del SDK.
- `packages/curupira-cli/tests/fixtures/python-ext/`: un fixture mínimo del protocolo sin
  el SDK.
