# Instalación

## Requisitos

{{ requirements_list("es") }}

- [`uv`](https://docs.astral.sh/uv/) para instalar la aplicación.

## Instalar

Instala el paquete publicado desde PyPI. El repositorio de código fuente es
[caipora-labs/curupira](https://github.com/caipora-labs/curupira).
El paquete es Python puro (`py3-none-any`), así que la instalación no necesita ninguna
cadena de herramientas de compilación en ninguna plataforma compatible.

```bash
uv tool install curupira
```

Eso instala solo la CLI de Rust. El cron integrado funciona de inmediato. Para las fuentes de
tareas de forges, añade un extra opcional (o usa `curupira plugins install`). Los extras instalan el
paquete consolidado `curupira-plugins`:

```bash
uv tool install 'curupira[extensions]'
# los extras con nombre de forge (github) instalan el mismo paquete
uv tool install 'curupira[github]'
```

Para fijar una versión concreta, usa `uv tool install "curupira==X.Y.Z"`.

Confirma que el comando está disponible con `curupira --version`. El alias corto `curu --version` ejecuta el mismo programa. Valida una configuración sin llamar a las CLI de los agentes:

```bash
curupira --config curupira.example.toml validate
```

## Crear una configuración

Curupira lee `~/.curupira/settings.toml` de forma predeterminada. Descarga la configuración de ejemplo:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

En Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edita los repositorios, las consultas y los prompts en el TOML. El directorio `~/.curupira` también guarda el estado y los logs. Pasa `--config path/to/settings.toml` para usar otro archivo.
