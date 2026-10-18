# Instalación

Curupira es un programa de línea de comandos en Rust. Instala ese mismo programa con npm o
desde PyPI. Ambos comandos son `curupira` y `curu`, y ambos usan `~/.curupira/` para
`settings.toml`, el archivo de estado SQLite, los espacios de trabajo y los worktrees. Pasar de pip a npm conserva ese directorio; el paquete de npm
no crea una segunda ruta de configuración.

El repositorio de código fuente es [caipora-labs/curupira](https://github.com/caipora-labs/curupira).

## Requisitos

{{ requirements_list("es") }}

Los binarios publicados cubren:

- Linux x64 y ARM64 con glibc
- Linux x64 y ARM64 con musl (Alpine)
- macOS x64 (Intel) y ARM64 (Apple Silicon)
- Windows x64 y ARM64

No se publican sistemas de 32 bits ni otros sistemas operativos. La instalación no compila Rust
y no necesita una cadena de herramientas de Rust. El comando de npm es un pequeño envoltorio de
Node.js que ejecuta directamente el binario precompilado: no cambia el directorio de trabajo, el
entorno ni la configuración, y termina con el estado del proceso de Rust. Un listado de procesos
muestra a Node.js como padre de ese proceso. El proceso de Rust es el que mantiene
`~/.curupira/dispatch.lock`.

`import curupira` y `curupira.__version__` existen solo en la instalación de PyPI. Los plugins
los inicia el lanzador que defines en `settings.toml` (`uvx` o `npx`), con cualquiera de las dos
instalaciones. Curupira no instala Python ni un entorno privado de Node.js para ellos. Si falta
`uvx` o `npx`, la validación informa que no se encontró el lanzador en el `PATH`.

## Instalar con Node.js

```bash
npm install -g @caipora-labs/curupira
```

Ejecútalo una vez sin instalación global:

```bash
npx @caipora-labs/curupira --help
```

El único paquete de npm incluye binarios para todos los sistemas operativos, CPU y bibliotecas C
compatibles. Selecciona el binario correspondiente al ejecutar el comando; no hay paquetes
adicionales de plataforma que instalar. Consulta el [README del paquete](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-cli-js/README.md)
para ver las plataformas compatibles.
Los conectores no están incluidos: los registras en `[plugins.<alias>]` dentro de tu
configuración, consulta [Plugins y conectores](plugins.md).

## Instalar con Python

[`uv`](https://docs.astral.sh/uv/) instala la wheel de plataforma desde PyPI. La wheel contiene
la CLI de Rust. Python se usa para el empaquetado y para las extensiones opcionales con `uvx`,
no para interpretar la CLI.

```bash
uv tool install curupira
# o
pip install curupira
```

El cron integrado funciona de inmediato. Los conectores como GitHub se registran en tu
configuración, consulta [Plugins y conectores](plugins.md).

Para fijar una versión concreta, usa `uv tool install "curupira==X.Y.Z"`.

## Comprobar la instalación

`curupira --version` y `curu --version` muestran la versión instalada. Valida una configuración
sin llamar a las CLI de los agentes:

```bash
curupira --config curupira.example.toml validate
```

## Crear una configuración

Curupira lee `~/.curupira/settings.toml` de forma predeterminada. Descarga la configuración de ejemplo:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-cli/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

En Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-cli/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edita los repositorios, las consultas y los prompts en el TOML. El directorio `~/.curupira` también guarda el estado y los espacios de trabajo. Pasa `--config path/to/settings.toml` para usar otro archivo.
