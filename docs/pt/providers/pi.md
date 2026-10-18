# pi

O Curupira executa o pi em modo JSON com `pi --mode json ... -- <message>`. Um novo ID de sessão
vem do cabeçalho de sessão JSONL do pi e é retomado com `--session <id>`. O pi agrupa
as sessões por diretório de trabalho; os worktrees determinísticos de tarefa do Curupira mantêm as execuções retomadas
no mesmo diretório de projeto.

## Instalação

Instale o pi globalmente com npm. Ele exige Node.js 22.19.0 ou superior.

```sh
npm install -g @earendil-works/pi-coding-agent
node --version
```

Autentique o pi com as variáveis de ambiente de chave de API do provider de model escolhido ou use
o comando `/login` do pi. O Curupira não coleta, armazena nem repassa credenciais; o processo do pi
usa o ambiente e a autenticação configurados pelo usuário.

## Opções do profile

| Opção do Curupira | Argumento do pi | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | Padrão de model exato ou aproximado; pode incluir `provider/id`. |
| `model_provider` | `--provider <provider>` | Exige `model`; evita colisão de nome com o discriminador `provider` do Curupira. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh` ou `max`. |
| `tools` | `--tools a,b` | Lista de permissão, separada por vírgulas, das ferramentas que o pi pode usar. |
| `exclude_tools` | `--exclude-tools a,b` | Ferramentas a excluir, separadas por vírgulas. |
| `approve = true` | `--approve` | Confia explicitamente no projeto atual neste processo. |
| `approve = false` | `--no-approve` | Não confia explicitamente no projeto atual neste processo. |
| `approve` omitido | *(sem argumento)* | Mantém inalterado o comportamento de confiança de projeto configurado no pi. |

O pi não pede aprovação antes de cada chamada de ferramenta, e o seu modo JSON não consegue exibir o prompt de
confiança do projeto. Quando a confiança padrão configurada é `ask`, o pi ignora os recursos protegidos
do projeto, a menos que a invocação faça uma escolha explícita. Defina `approve` somente quando
essa decisão de confiança em nível de projeto for intencional. Use `tools` para limitar a lista de permissão,
`exclude_tools` para remover ferramentas específicas e os worktrees por tarefa do Curupira para isolar
as mudanças no repositório. O pi não tem opção nativa de agente personalizado, então os profiles do Curupira não
aceitam `agent`.

O Curupira acrescenta cada prompt depois de `--`, então um hífen no início é passado como texto do prompt. O pi
também trata `@path` como inclusão de arquivo: um prompt que começa com `@` pode ser lido como uma referência
a arquivo em vez de texto comum.

```toml
[coding_agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true # confia explicitamente nos recursos do projeto neste processo
```

O identificador de sessão emitido pelo pi é persistido e retomado no mesmo worktree determinístico
da tarefa. O Curupira usa o último evento `message_end` do assistente e junta os seus blocos de texto;
o conteúdo de raciocínio e de chamadas de ferramenta não é exibido como resultado da tarefa.

::: curupira.agents.pi.PiCliProfile
