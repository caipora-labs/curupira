#!/bin/sh
# Stand-in for the opencode CLI in TUI end-to-end tests. It never contacts a model.
#
# `opencode run ... -- PROMPT` prints OpenCode 2.x JSON events chosen by a marker in the prompt
# (the last argument) and registers the session's title under $HOME/.fake-opencode:
#   SCENARIO:ok     titled "Revisão automática do repositório"
#   SCENARIO:fail   reports a provider error, exits 1, and never gets a title
#   SCENARIO:noise  also writes straight to the terminal, as some agents do, and runs longer
# `opencode session list --format json` prints the registered sessions, like OpenCode does.
registry="$HOME/.fake-opencode"

if [ "$1" = "session" ] && [ "$2" = "list" ]; then
    printf '['
    sep=''
    for file in "$registry"/*; do
        [ -f "$file" ] || continue
        printf '%s{"id":"%s","title":"%s"}' "$sep" "$(basename "$file")" "$(cat "$file")"
        sep=','
    done
    printf ']\n'
    exit 0
fi

for prompt; do :; done
session="ses_fake_$$"
event() {
    printf '{"type":"%s","sessionID":"%s",%s}\n' "$1" "$session" "$2"
}

case "$prompt" in
*SCENARIO:fail*)
    event error '"error":{"type":"provider.no-route","message":"Model unavailable: test/model"}'
    exit 1
    ;;
*SCENARIO:noise*) title="Agente que escreve no terminal" ;;
*) title="Revisão automática do repositório" ;;
esac
mkdir -p "$registry"
printf '%s' "$title" >"$registry/$session"

event step_start '"part":{"type":"step-start"}'
event text '"part":{"type":"text","text":"Analisando a tarefa de teste."}'
event tool_use '"part":{"tool":"shell","state":{"status":"completed","title":"gh pr checks 1","input":{"command":"gh pr checks 1"}}}'
seconds=4
case "$prompt" in
*SCENARIO:noise*)
    printf 'NOISE-FROM-AGENT' >/dev/tty 2>/dev/null
    seconds=10 # long enough for a test to see the noise before the task ends
    ;;
esac
sleep "$seconds"
event text '"part":{"type":"text","text":"Tudo certo, nada a fazer."}'
exit 0
