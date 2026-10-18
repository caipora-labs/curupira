# Manifiesto y protocolo

Los SDK implementan por ti todo lo que describe esta página. Léela cuando escribas una
extensión sin un SDK, cuando depures una o cuando quieras saber exactamente qué hace el
host. La especificación normativa es
[`PROTOCOL.md`](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-cli/PROTOCOL.md).

## Transporte { #transport }

Versión del protocolo **2**: JSON-RPC 2.0 por stdin y stdout, en **frames con prefijo de
longitud** (nunca JSON delimitado por saltos de línea). Cada frame son ocho dígitos
hexadecimales con la longitud en bytes del cuerpo JSON en UTF-8, seguidos directamente del
cuerpo, sin separador ni salto de línea:

```text
0000002c{"jsonrpc":"2.0","id":1,"method":"describe"}
```

- **stdout** transporta solo frames del protocolo. **stderr** es para los logs.
- El tamaño máximo predeterminado de un frame es 16 MiB.
- El host envía `initialize` con `protocol_version`; la extensión responde con la misma
  versión mayor. Las demás versiones se rechazan con un error claro.

## Métodos { #methods }

| Método | Cuándo lo llama el host |
| --- | --- |
| `initialize` | Primero, para acordar la versión del protocolo |
| `describe` | Para listar los triggers |
| `trigger/schema` | Para obtener el JSON Schema y los campos del prompt de un trigger |
| `trigger/validate` | Durante `curupira validate` y antes de consultar, con la tabla de la automatización |
| `trigger/poll` | Para obtener el siguiente elemento |
| `trigger/onStarted` | Antes de que empiece el agente de código, con los campos del elemento |
| `trigger/onFinished` | Después de que termina el agente de código, con los campos del elemento |
| `shutdown` | Para que el proceso salga de forma limpia |

`trigger/onStarted` y `trigger/onFinished` reciben
`{ "trigger_type": "<local>", "values": [ ... ] }`. No reciben estado del host, como el
prompt renderizado o la ruta del worktree.

## Resultados de la consulta { #results }

`trigger/poll` siempre devuelve un objeto con un miembro `values` obligatorio:

| `values` | Significado |
| --- | --- |
| `null` | No se encontró nada. El host termina la ronda actual para esta automatización. |
| `[]` | Se encontró un elemento, y no tiene campos. |
| `[{ "key": "issue_number", "value": "42" }, …]` | Los campos del elemento, como cadenas. |

Omitir `values` es un error de protocolo, distinto de `null`. El protocolo no exige `id`,
`title`, `url` ni ninguna otra clave, y el host no las interpreta.

## Qué hace el host con un elemento { #polling }

1. Valida la automatización con `trigger/validate`, con los valores predeterminados aplicados.
2. Llama a `trigger/poll` repetidamente, hasta `[settings.polling].batch_size` veces por
   ronda. Los argumentos de polling no se pasan a la función del trigger.
3. Calcula un hash del JSON canónico de los pares, en el orden recibido, que forma la
   identidad de la tarea. Una identidad completada nunca vuelve a ejecutarse; los mismos
   pares en otro orden son una tarea distinta.
4. Completa `${key}` en el prompt con el valor de cada par, en una sola pasada. El texto
   insertado no se vuelve a analizar, así que un valor `${other}` se queda literal, y un
   placeholder sin una clave correspondiente se deja sin cambios.

El host agrega `${repository}` (la identidad de la forja derivada del remoto de Git) y
`${automation}` (el nombre de la automatización). Una clave del resultado con cualquiera de
esos nombres es un error. Las claves que no son identificadores también funcionan:
`${issue-number}`, `${foo.bar}`, `${123}`.

## Códigos de error { #errors }

| Código | Significado |
| --- | --- |
| `-32700` | Error de análisis |
| `-32600` | Solicitud inválida |
| `-32601` | Método no encontrado |
| `-32602` | Parámetros inválidos |
| `-32603` | Error interno |
| `-32000` | Falla de transporte |
| `-32001` | Falla de protocolo o de versión |
| `-32002` | Falla al ejecutar un comando |
| `-32003` | Falla en la validación de la configuración |
| `-32004` | Tiempo de espera agotado |

## Manifiesto { #manifest }

`curupira-extension.toml` (formato de manifiesto `1`) describe un paquete para que Curupira
pueda listarlo sin ejecutarlo. Una extensión debe declarar `kind = "trigger"`
y al menos una entrada en `trigger_types`.

```toml
manifest_version = 1
name = "acme-curupira-ext"
version = "1.2.0"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@acme/curupira-ext"
version = "1.2.0"
```

El paquete debería imprimir este manifiesto cuando se inicia con `--curupira-print-manifest`,
para que `curupira plugins list` pueda describirlo sin ejecutar código de ningún trigger.
