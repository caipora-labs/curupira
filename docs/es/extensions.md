# Extensiones de proceso

La CLI de Curupira es un binario de Rust. Las **fuentes de tareas** (excepto **cron**,
que es integrado) se ejecutan como **procesos separados** que hablan el
[protocolo de extensiones](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md)
(JSON-RPC 2.0 sobre stdin/stdout con prefijo de longitud).

Los **agentes de código** (OpenCode, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI,
Kilo, pi, Qwen Code) están **integrados en el núcleo de Rust**. No son extensiones de
proceso y no usan el protocolo de extensiones.

## Instala la CLI { #install-the-cli }

```bash
pip install curupira
# o
uv tool install curupira
```

`curupira` y `curu` son el mismo binario. La wheel base incluye solo esa CLI de Rust
(más un pequeño shim `curupira.__version__`). Los triggers oficiales se distribuyen como
un paquete opcional (`curupira-plugins`, que depende de `curupira-sdk`): instálalos con
extras o con `curupira plugins install`. El **cron** integrado no necesita ningún paquete
de extensión. Node.js solo se requiere cuando instalas una extensión de trigger de
terceros basada en Node.

```bash
# triggers oficiales (instala curupira-sdk como dependencia)
pip install 'curupira[extensions]'
# los extras con nombre de forge instalan el mismo paquete
pip install 'curupira[github]'
# o gestiona un paquete con la CLI (usa uvx)
curupira plugins install --yes pip:curupira-plugins
```

## Gestiona extensiones { #manage-extensions }

```bash
curupira plugins list
curupira plugins info curupira-plugins
curupira plugins install --yes path:./packages/curupira-python-plugins
curupira plugins install --yes pip:some-extension==1.2.3
curupira plugins install --yes npm:@acme/curupira-ext@1.2.3
curupira plugins uninstall some-extension
```

El descubrimiento lee los manifiestos `curupira-extension.toml` de
`~/.curupira/extensions/`, de `CURUPIRA_EXTENSIONS_PATH` y del directorio incluido
`packages/curupira-python-plugins/`. **Listar nunca ejecuta código de las extensiones.**

`plugins list` también muestra el cron integrado y los proveedores de agentes de código
integrados (con la etiqueta `agent:<name>` y origen `built-in`).

### Requisitos de ejecución { #runtime-requirements }

| Fuente | Necesita en el PATH |
| --- | --- |
| Extras oficiales de triggers en Python / instalaciones gestionadas | `python3` (o `uvx` para instalaciones `pip:`) |
| Instalaciones `pip:` | `uvx` (de [uv](https://docs.astral.sh/uv/)) |
| Instalaciones `npm:` | `npx` (Node.js) |
| Cron y agentes de código integrados | las CLI de agentes que configures (más `git`) |

## Extensiones oficiales { #official-extensions }

Se distribuyen como un único paquete de PyPI, `curupira-plugins`
(`packages/curupira-python-plugins/`, import `curupira_plugins`). **No** es necesario
para instalar la CLI. Los extras de PyPI `github` / `extensions`
instalan esa misma distribución. Regístralo en la configuración bajo un alias de TOML con
un lanzador independiente (`uvx` o `npx`) y sus args; las automatizaciones usan entonces
`<alias>/<local-trigger>`:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["*"]
```

El paquete incluye un script de consola `curupira-plugins`, así que `uvx` lo ejecuta
directamente (sin `python -m`). Usa `tools` para conservar solo los triggers locales que
coincidan (`github-*`) o para descartar coincidencias (`!github-project-*`).

| Trigger local (en el paquete) | `trigger_type` de automatización de ejemplo |
| --- | --- |
| `github-issues` | `plugins-py/github-issues` |
| `github-pull-requests` | `plugins-py/github-pull-requests` |
| `github-project-items` | `plugins-py/github-project-items` |

**cron** y todos los adaptadores de agentes de código siguen dentro de la CLI de Rust (no
son extensiones).

## Escribe una extensión de Python con curupira-sdk { #write-a-python-extension-with-curupira-sdk }

Instala el SDK por separado (solo biblioteca estándar por defecto; Pydantic es opcional).
Los paquetes oficiales de triggers dependen de él; los paquetes de terceros deben
declararlo explícitamente:

```bash
pip install curupira-sdk
# modelos estructurados opcionales:
pip install 'curupira-sdk[pydantic]'
```

### Trigger mínimo { #minimal-trigger }

```python
from dataclasses import dataclass

from curupira_sdk import Curupira

app = Curupira(name="acme-issues", version="0.1.0")


@dataclass
class Issue:
    number: int
    title: str
    url: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next eligible issue, or None when the round is empty."""
    # Selecciona exactamente un siguiente elemento de la API externa (nunca una lista).
    return None


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
```

Reglas:

- Usa `@app.trigger` sin paréntesis para derivar el nombre **local** del trigger a partir
  de `function.__name__` en kebab-case (`github_issues` → `github-issues`).
- Usa `@app.trigger(alias="issues")` para reemplazar el nombre local.
- Registra el lanzador bajo `[plugins.<alias>]` en la configuración (`type` + `args`).
  Las automatizaciones se dirigen al trigger como `<alias>/<local-name>` (por ejemplo
  `plugins-py/github-issues`).
- Los parámetros de la función son la fuente de verdad de los extras del TOML. Lo
  requerido / opcional / los valores por defecto / `None` provienen de la firma y de las
  anotaciones de tipo.
- Devuelve **un** objeto o `None`. Las listas, tuplas e iteradores se rechazan.
- `def` síncrono y `async def` comparten el mismo decorador.
- Los dataclasses y TypedDict funcionan sin configuración adicional. Los modelos de
  Pydantic v2 necesitan `curupira-sdk[pydantic]`.
- El host de Rust se encarga del polling, la concurrencia, Git, los worktrees y los
  agentes de código. El SDK nunca programa ni reintenta trabajo del despachador.

### TOML correspondiente { #matching-toml }

Registra el lanzador bajo `[plugins.<alias>]` y luego mantén los campos centrales de la
automatización en la tabla, con los argumentos del trigger como hermanos:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["github-*"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"          # alias de checkout (núcleo)
repo = "acme/api"           # parámetro de la función
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`repository`, `prompt`, `profile` y `checkout` son campos centrales: no los declares
como parámetros de la función (usa `repo` u otro nombre para los identificadores de la
forge).

### Cómo consulta el host { #how-the-host-polls }

1. El host elige una automatización habilitada y valida la configuración mediante
   `trigger/validate` (aplicando los valores por defecto de la firma).
2. Llama a `trigger/poll` repetidamente, hasta `settings.polling.batch_size`.
3. Cada llamada debe devolver `{ "task": <object> }` o `{ "task": null }`.
4. `null` termina la ronda actual; el trigger sigue habilitado para el siguiente
   intervalo de consulta. Los errores usan códigos de error de JSON-RPC y no equivalen a
   `null`.

### Manifiesto { #manifest }

Incluye un `curupira-extension.toml` y admite `--curupira-print-manifest` en stdout para
`plugins install pip:…`. Consulta `packages/curupira-core/tests/fixtures/python-ext/`
para ver un fixture de protocolo mínimo, y
`packages/curupira-python-plugins/src/curupira_plugins/__main__.py` para ver un ejemplo
completo del SDK.

Las extensiones descubren y normalizan tareas, validan su configuración y reciben eventos
del ciclo de vida. No deben elegir agentes de código, construir el argv del agente,
clonar repositorios ni gestionar worktrees: el host de Rust se encarga de esos pasos.

## Escribe una extensión de JavaScript / TypeScript { #write-a-javascript-typescript-extension }

Usa el mismo enmarcado y los mismos métodos. Publica un paquete de npm cuyo `bin` hable
el protocolo por stdio. Los paquetes de TypeScript deben compilarse a JS o ejecutarse con
`tsx`/`node` como se documente en el paquete. Consulta
`packages/curupira-core/tests/fixtures/node-ext/` y
`packages/curupira-core/tests/fixtures/ts-ext/`.

Los resultados de poll deben usar `{ "task": null }` o un único objeto de tarea, nunca un
arreglo de tareas.

## Seguridad { #security }

Las extensiones de terceros se ejecutan con los privilegios de tu usuario. Los
subprocesos no son un sandbox. No instales paquetes no confiables. Curupira nunca instala
paquetes durante el descubrimiento; los comandos de instalación piden confirmación salvo
que uses `--yes`.
