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
# Node.js
npm install -g @caipora/curupira

# Python
pip install curupira
# o
uv tool install curupira
```

`curupira` y `curu` ejecutan el mismo binario de Rust en ambos casos, y ambos usan
`~/.curupira/`. El paquete de npm no cambia los lanzadores de extensiones y no instala un
entorno propio de Python ni de Node.js. La wheel de PyPI también incluye un pequeño shim
`curupira.__version__`. Los triggers oficiales se distribuyen como un paquete opcional
(`curupira-plugins`, que depende de `curupira-sdk`): instálalos con extras o con
`curupira plugins install`. El **cron** integrado no necesita ningún paquete de extensión.
Las extensiones `uvx` necesitan `uvx` en el `PATH`; las extensiones `npx` necesitan `npx`
en el `PATH`. Si falta el lanzador configurado, la validación lo indica.

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


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next issue, or None when nothing was found."""
    # Selecciona exactamente un objeto (nunca una lista). None significa que no se encontró nada.
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
- Devuelve **un** objeto o `None`. `None` significa que no se encontró nada y se convierte
  en `null` de JSON. Las listas, tuplas, conjuntos e iteradores se rechazan, incluida una
  lista de pares construida a mano. Un mapeo vacío se convierte en una lista de pares
  vacía, que es un elemento sin datos, no "no se encontró nada".
- `def` síncrono y `async def` comparten el mismo decorador. El host no pasa `preview` ni
  `limit` a la función.
- Los mapeos, dataclasses y TypedDict funcionan sin configuración adicional. Los modelos de
  Pydantic v2 necesitan `curupira-sdk[pydantic]`. El SDK convierte ese objeto en una lista
  de pares de cadenas `{ "key", "value" }`. No añade `id`, `title`, `url` ni ningún otro
  campo.
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
forge). Los nombres usados en el prompt son los campos que devuelve el trigger. Este
ejemplo usa solo `number`, `title` y `url` porque `Issue` declara esos campos.

### Cómo un valor devuelto se convierte en pares { #how-a-return-value-becomes-pairs }

El SDK convierte el objeto antes de que llegue al host. Las claves de nivel superior
conservan el orden de declaración o de inserción. Cada valor se convierte en una cadena:

| Valor de Python | `value` del par |
| --- | --- |
| `str` | la misma cadena, sin comillas adicionales |
| `bool` | `true` o `false` |
| `int` | texto decimal (`1` y `1.0` siguen siendo distintos) |
| `float` | el mismo texto que emitiría `json.dumps` |
| `None` | `null` (es un valor de campo, no "no se encontró nada") |
| mapeo anidado, lista, tupla, dataclass o modelo | JSON compacto (`sort_keys=True`, sin espacios adicionales) |

Se rechazan con `SerializationError` (se reporta como error de JSON-RPC, no como `null`):

- una lista, tupla, conjunto, generador u otra colección de nivel superior
- una cadena, número o booleano de nivel superior
- una clave que no es una cadena (las claves no se convierten con `str`)
- una clave vacía, o una clave que contiene `}` o `${`
- una clave duplicada
- un float no finito, `bytes`, `set`, `datetime` o cualquier otro valor que no se pueda serializar

`describe` aún puede listar `prompt_fields` tomados del tipo de retorno declarado. Esa
lista es una pista. No forma parte del resultado y no hace que ninguna clave sea
obligatoria.

### Cómo consulta e interpola el host { #how-the-host-polls }

1. El host elige una automatización habilitada y valida la configuración mediante
   `trigger/validate` (aplicando los valores por defecto de la firma).
2. Llama a `trigger/poll` repetidamente, hasta `settings.polling.batch_size`.
   Los argumentos de polling no se pasan a la función del trigger.
3. Cada llamada devuelve `{ "values": [ {"key", "value"}, ... ] }`,
   `{ "values": [] }` o `{ "values": null }`.
4. `null` termina la ronda actual. Una lista vacía sigue siendo un resultado. Los errores
   usan códigos de error de JSON-RPC y no equivalen a `null`.

La CLI sustituye `${key}` por el valor de cadena del par en una sola pasada. El texto que
inserta un valor no se vuelve a analizar, así que un valor `${other}` se queda literal. Un
marcador sin clave coincidente se deja sin cambios. `${repository}` (la identidad de la
forge derivada del remoto de Git) y `${automation}` (el nombre de la automatización) los
proporciona el host. Una clave de resultado con cualquiera de esos nombres es un error. Las
claves que no son identificadores ordinarios se siguen escribiendo como
`${issue-number}`, `${foo.bar}`, `${123}` o `${a b}`.

El host no sabe qué claves usa un plugin. Dos listas idénticas son la misma tarea; la
identidad es un hash de la lista en el orden en que la envió la extensión, almacenado con
el estado de finalización y de reanudación. Las tareas completadas del protocolo v1 no
coinciden con estas claves.

### Manifiesto { #manifest }

Incluye un `curupira-extension.toml` y admite `--curupira-print-manifest` en stdout para
`plugins install pip:…`. Consulta `packages/curupira-core/tests/fixtures/python-ext/`
para ver un fixture de protocolo mínimo, y
`packages/curupira-python-plugins/src/curupira_plugins/__main__.py` para ver un ejemplo
completo del SDK.

Las extensiones descubren y normalizan tareas, validan su configuración y reciben eventos
del ciclo de vida. No deben elegir agentes de código, construir el argv del agente,
clonar repositorios ni gestionar worktrees: el host de Rust se encarga de esos pasos.

## Escribe una extensión de JavaScript / TypeScript con `@caipora/curupira-sdk` { #javascript-extension }

Instala el SDK en tu paquete de npm (Node.js 20+). La CLI lanza el paquete publicado con
`npx`; no necesitas una instalación global del plugin ni del SDK.

```bash
npm install @caipora/curupira-sdk
```

### Trigger mínimo en JavaScript (JSDoc opcional) { #minimal-javascript-trigger }

```js
import { defineTriggers } from "@caipora/curupira-sdk";

/**
 * @typedef {Object} GitHubIssueParams
 * @property {string} repo
 * @property {string[]} [labels]
 */

/**
 * @param {GitHubIssueParams} params
 */
async function githubIssue({ repo, labels = [] }) {
  // Devuelve un objeto, o null cuando no se encontró nada.
  return { repo, labels, title: "Fix authentication" };
}

export default defineTriggers({
  githubIssue,
});
```

JSDoc es documentación para los editores. No se lee en tiempo de ejecución.

### Trigger mínimo en TypeScript { #minimal-typescript-trigger }

```ts
import { defineTriggers } from "@caipora/curupira-sdk";

export default defineTriggers({
  githubIssue: async (params: { repo: string; labels?: string[] }) => ({
    repo: params.repo,
    labels: params.labels ?? [],
    title: "Fix authentication",
  }),
});
```

Compila TypeScript a JavaScript ESM simple antes de publicar. Curupira no transpila
TypeScript arbitrario cuando inicia el plugin.

### Punto de entrada `bin` del plugin { #plugin-bin-entrypoint }

```js
#!/usr/bin/env node
import { runExtension } from "@caipora/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  // Opcional: se imprime para `curupira plugins install npm:…`
  manifestTemplate: `manifest_version = 1
name = "acme-curupira-ext"
version = "{version}"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@acme/curupira-ext"
version = "{version}"
`,
});
```

Declara el ejecutable en `package.json`:

```json
{
  "name": "@acme/curupira-ext",
  "version": "1.2.0",
  "type": "module",
  "bin": {
    "curupira-acme-ext": "./bin.js"
  },
  "dependencies": {
    "@caipora/curupira-sdk": "^0.1.0"
  }
}
```

Publica en npm. Registra el lanzador en la configuración (fija la versión en `args`):

```toml
[plugins.acme]
type = "npx"
args = ["--yes", "@acme/curupira-ext@1.2.0"]
tools = ["*"]

[automations.demo]
trigger_type = "acme/github-issue"
repository = "api"
repo = "acme/api"
labels = ["bug"]
prompt = """
Resolve ${title} in ${repo}
"""
```

La CLI ejecuta `npx --yes @acme/curupira-ext@1.2.0` como argv (nunca como cadena de shell),
reenvía stdin/stdout para los frames del protocolo y deja stderr para los logs. Se usa la
caché normal de npm. Si falta `npx`, la validación falla con un mensaje que indica instalar
Node.js.

### Reglas del SDK de JS/TS { #rules-for-the-js-ts-sdk }

- El nombre de la propiedad del objeto es el id local del trigger, convertido a kebab-case
  (`githubIssue` → `github-issue`).
- Se admiten funciones síncronas y asíncronas.
- Devuelve **un** objeto simple o `null`. El SDK convierte el objeto en pares de cadenas
  `{ "values": [{ "key", "value" }, ...] }`. `null` se convierte en
  `{ "values": null }`. Un objeto vacío se convierte en `{ "values": [] }`.
- No construyas a mano la lista de pares. No devuelvas un arreglo de elementos de negocio.
- Los valores anidados usan las mismas reglas de serialización que el SDK de Python (ver
  arriba).
- Los campos centrales de la automatización (`trigger_type`, `repository`, `prompt`,
  `profile`, `checkout`) no son parámetros de la función: usa `repo` (o similar) para los
  identificadores de la forge.
- Las banderas de polling (`preview`, `limit`) no se pasan a la función del trigger.
- El paquete es ESM. Es preferible publicar JavaScript compilado más archivos `.d.ts`.

Los fixtures de protocolo de bajo nivel sin el SDK siguen en
`packages/curupira-core/tests/fixtures/node-ext/` y `ts-ext/`. Los ejemplos completos están
en `packages/curupira-js-sdk/examples/`.

## Seguridad { #security }

Las extensiones de terceros se ejecutan con los privilegios de tu usuario. Los
subprocesos no son un sandbox. No instales paquetes no confiables. Curupira nunca instala
paquetes durante el descubrimiento; los comandos de instalación piden confirmación salvo
que uses `--yes`.
