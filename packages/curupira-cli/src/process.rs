//! Headless subprocess runner (argv only; never a shell string).

use std::collections::BTreeMap;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::process::Command;
use tokio::time::timeout;

/// Git variables that bind a process to one repository or index; cleared for task worktrees.
const REPOSITORY_BINDING_ENV: &[&str] = &[
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
];

/// Bounded process result.
#[derive(Debug, Clone)]
pub struct ProcessResult {
    pub exit_code: i32,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

/// Command builder surface shared by the std and tokio process APIs.
pub(crate) trait SpawnCommand {
    fn clear_env(&mut self);
    fn set_env(&mut self, key: &OsStr, val: &OsStr);
    fn remove_env(&mut self, key: &OsStr);
    fn set_current_dir(&mut self, dir: &Path);
}

impl SpawnCommand for std::process::Command {
    fn clear_env(&mut self) {
        self.env_clear();
    }

    fn set_env(&mut self, key: &OsStr, val: &OsStr) {
        self.env(key, val);
    }

    fn remove_env(&mut self, key: &OsStr) {
        self.env_remove(key);
    }

    fn set_current_dir(&mut self, dir: &Path) {
        self.current_dir(dir);
    }
}

impl SpawnCommand for Command {
    fn clear_env(&mut self) {
        self.env_clear();
    }

    fn set_env(&mut self, key: &OsStr, val: &OsStr) {
        self.env(key, val);
    }

    fn remove_env(&mut self, key: &OsStr) {
        self.env_remove(key);
    }

    fn set_current_dir(&mut self, dir: &Path) {
        self.current_dir(dir);
    }
}

/// Give a child a copy of Curupira's environment, then apply overwrites.
///
/// Order:
/// 1. Drop implicit inheritance (`env_clear`).
/// 2. Copy every variable the current process can see (`std::env::vars_os`).
/// 3. Replace keys from `[environment.vars]` (`overrides`).
/// 4. Apply call-site pairs (`extra`), such as an agent's database path.
/// 5. When `cwd` is set, point `PWD` at that directory and drop `OLDPWD` plus the
///    repository-binding `GIT_*` variables, even if an earlier step set them.
pub(crate) fn apply_spawn_environment(
    command: &mut impl SpawnCommand,
    overrides: &BTreeMap<String, String>,
    extra: &[(String, String)],
    cwd: Option<&Path>,
) {
    command.clear_env();
    for (key, value) in std::env::vars_os() {
        command.set_env(&key, &value);
    }
    for (key, value) in overrides {
        command.set_env(OsStr::new(key), OsStr::new(value));
    }
    for (key, value) in extra {
        command.set_env(OsStr::new(key), OsStr::new(value));
    }
    if let Some(dir) = cwd {
        command.set_current_dir(dir);
        // Tools read PWD (and Git reads GIT_*) instead of the kernel cwd. Without this, an
        // agent started in a task worktree inherits the caller's PWD and repository binding
        // and can act on the caller's checkout.
        command.set_env(OsStr::new("PWD"), dir.as_os_str());
        command.remove_env(OsStr::new("OLDPWD"));
        for var in REPOSITORY_BINDING_ENV {
            command.remove_env(OsStr::new(var));
        }
    }
}

/// Characters that `cmd.exe` treats as syntax. Mirrors `node-cross-spawn`'s meta set:
/// `()[]%!^"`<>&|;, *?` (backtick included).
fn is_cmd_meta(c: char) -> bool {
    matches!(
        c,
        '(' | ')'
            | '['
            | ']'
            | '%'
            | '!'
            | '^'
            | '"'
            | '`'
            | '<'
            | '>'
            | '&'
            | '|'
            | ';'
            | ','
            | ' '
            | '*'
            | '?'
    )
}

fn caret_escape(input: &str) -> String {
    let mut out = String::with_capacity(input.len().saturating_mul(2));
    for c in input.chars() {
        if is_cmd_meta(c) {
            out.push('^');
        }
        out.push(c);
    }
    out
}

/// Quote one argument the way `CommandLineToArgvW` reads it, before caret-escaping for `cmd.exe`.
///
/// Backslashes are doubled when they sit immediately before a quote or the end of the
/// argument, and an embedded quote becomes `\"`. This is the first half of
/// `node-cross-spawn`'s `escapeArgument`.
fn quote_for_crt(arg: &str) -> String {
    let chars: Vec<char> = arg.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '\\' {
            let start = i;
            while i < chars.len() && chars[i] == '\\' {
                i += 1;
            }
            let slashes = i - start;
            if i < chars.len() && chars[i] == '"' {
                out.extend(std::iter::repeat_n('\\', slashes * 2 + 1));
                out.push('"');
                i += 1;
            } else if i == chars.len() {
                out.extend(std::iter::repeat_n('\\', slashes * 2));
            } else {
                out.extend(std::iter::repeat_n('\\', slashes));
            }
        } else if chars[i] == '"' {
            out.push('\\');
            out.push('"');
            i += 1;
        } else {
            out.push(chars[i]);
            i += 1;
        }
    }
    format!("\"{out}\"")
}

/// Escape one argument for a `.cmd` / `.bat` shim.
///
/// npm shims forward `%*` into a second `cmd.exe` parse and then into `node.exe`, so meta
/// characters are caret-escaped twice (the same rule `node-cross-spawn` uses for cmd shims).
/// A raw newline ends a `cmd /c` command, so each line is escaped on its own and joined with
/// a doubled caret-newline. The launcher batch file's parse leaves one `^<LF><LF>` for the
/// shim, and the shim's parse turns that into a single newline inside the argument.
fn escape_batch_argument(arg: &str) -> String {
    let normalized = arg.replace("\r\n", "\n").replace('\r', "\n");
    let mut parts = normalized.split('\n');
    let Some(first) = parts.next() else {
        return escape_argument("", true);
    };
    let mut out = escape_argument(first, true);
    for part in parts {
        // `^^^\r\n\r\n^\r\n\r\n` survives one caret pass as `^\n\n`.
        out.push_str("^^^\r\n\r\n^\r\n\r\n");
        out.push_str(&escape_argument(part, true));
    }
    out
}

fn escape_argument(arg: &str, double_escape: bool) -> String {
    let once = caret_escape(&quote_for_crt(arg));
    if double_escape {
        caret_escape(&once)
    } else {
        once
    }
}

fn escape_cmd_command(command: &str) -> String {
    caret_escape(command)
}

fn is_batch(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("cmd") || ext.eq_ignore_ascii_case("bat"))
}

/// Script path plus arguments, escaped for one `cmd.exe` parse on top of the shim's parse.
fn batch_command_line(script: &Path, args: &[String]) -> String {
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push(escape_cmd_command(&script.to_string_lossy()));
    for arg in args {
        parts.push(escape_batch_argument(arg));
    }
    parts.join(" ")
}

/// Batch file that runs `command`.
///
/// `cmd /c` drops everything after a newline, so the escaped command is written to a file
/// where caret continuation is real. `%` is doubled because a batch file turns `%%` into `%`
/// before the caret pass; that restores the command-line form the shim already expects.
/// Invoking the shim transfers control, so the caller deletes the file after the process exits.
fn batch_launcher_script(command: &str) -> String {
    let command = command.replace('%', "%%");
    format!("@echo off\r\nsetlocal DisableDelayedExpansion\r\n{command}\r\n")
}

/// Deletes a Windows launcher batch file when the child that reads it has exited.
pub(crate) struct BatchCleanup {
    path: Option<PathBuf>,
}

impl Drop for BatchCleanup {
    fn drop(&mut self) {
        if let Some(path) = self.path.take() {
            let _ = std::fs::remove_file(path);
        }
    }
}

fn write_batch_launcher(command: &str) -> Result<PathBuf, String> {
    use std::sync::atomic::{AtomicU64, Ordering};
    static LAUNCH_SEQ: AtomicU64 = AtomicU64::new(0);
    let seq = LAUNCH_SEQ.fetch_add(1, Ordering::Relaxed);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or(0);
    let path = std::env::temp_dir().join(format!(
        "curupira-launch-{}-{}-{seq}.cmd",
        std::process::id(),
        nanos
    ));
    std::fs::write(&path, batch_launcher_script(command))
        .map_err(|err| format!("failed to write batch launcher: {err}"))?;
    Ok(path)
}

/// Resolve `program` the way the preflight check does.
///
/// A name is looked up with `which` (on Windows that honors `PATHEXT`, so `opencode` finds
/// `opencode.cmd`). A path is used as given when the file exists.
pub(crate) fn resolve_executable(program: &str) -> Result<PathBuf, String> {
    let path = Path::new(program);
    let has_separator = program.contains('/') || program.contains('\\');
    if has_separator || path.is_absolute() {
        if path.is_file() {
            Ok(path.to_path_buf())
        } else {
            Err(format!("program {program:?} not found"))
        }
    } else {
        which::which(program).map_err(|_| format!("program {program:?} not found on PATH"))
    }
}

fn comspec_path() -> PathBuf {
    std::env::var_os("COMSPEC")
        .map(PathBuf::from)
        .filter(|path| path.is_file())
        .unwrap_or_else(|| PathBuf::from(r"C:\Windows\System32\cmd.exe"))
}

trait LaunchCommand: Sized {
    fn from_program(program: &Path) -> Self;
    fn push_arg(&mut self, arg: &str);
    fn push_raw(&mut self, raw: &OsStr);
}

impl LaunchCommand for std::process::Command {
    fn from_program(program: &Path) -> Self {
        Self::new(program)
    }

    fn push_arg(&mut self, arg: &str) {
        self.arg(arg);
    }

    fn push_raw(&mut self, raw: &OsStr) {
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            self.raw_arg(raw);
        }
        #[cfg(not(windows))]
        {
            let _ = raw;
        }
    }
}

impl LaunchCommand for Command {
    fn from_program(program: &Path) -> Self {
        Self::new(program)
    }

    fn push_arg(&mut self, arg: &str) {
        self.arg(arg);
    }

    fn push_raw(&mut self, raw: &OsStr) {
        #[cfg(windows)]
        {
            self.raw_arg(raw);
        }
        #[cfg(not(windows))]
        {
            let _ = raw;
        }
    }
}

fn configure_launch<C: LaunchCommand>(
    program: &str,
    args: &[String],
) -> Result<(C, BatchCleanup), String> {
    let resolved = resolve_executable(program)?;
    if cfg!(windows) && is_batch(&resolved) {
        let launcher = write_batch_launcher(&batch_command_line(&resolved, args))?;
        let mut cmd = C::from_program(&comspec_path());
        cmd.push_arg("/d");
        cmd.push_arg("/v:off");
        cmd.push_arg("/c");
        cmd.push_raw(&OsString::from(format!("\"{}\"", launcher.display())));
        Ok((
            cmd,
            BatchCleanup {
                path: Some(launcher),
            },
        ))
    } else {
        let mut cmd = C::from_program(&resolved);
        for arg in args {
            cmd.push_arg(arg);
        }
        Ok((cmd, BatchCleanup { path: None }))
    }
}

/// `std::process::Command` for `program` plus `args`, resolving npm shims on Windows.
///
/// Keep the [`BatchCleanup`] until the child exits. Dropping it sooner deletes the launcher
/// file while `cmd.exe` may still be reading it.
pub(crate) fn std_command(
    program: &str,
    args: &[String],
) -> Result<(std::process::Command, BatchCleanup), String> {
    configure_launch(program, args)
}

fn tokio_command(program: &str, args: &[String]) -> Result<(Command, BatchCleanup), String> {
    configure_launch(program, args)
}

/// Synchronous capture used for one-shot probes such as `opencode --version`.
pub(crate) fn capture_sync(
    program: &str,
    args: &[String],
    timeout_duration: Duration,
) -> Result<ProcessResult, String> {
    let (mut cmd, _cleanup) = std_command(program, args)?;
    cmd.stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());
    apply_spawn_environment(&mut cmd, &BTreeMap::new(), &[], None);
    let mut child = cmd.spawn().map_err(|e| format!("spawn {program}: {e}"))?;
    let stdout_pipe = child.stdout.take();
    let stderr_pipe = child.stderr.take();
    let stdout_thread = std::thread::spawn(move || read_pipe(stdout_pipe));
    let stderr_thread = std::thread::spawn(move || read_pipe(stderr_pipe));
    let status = wait_child(&mut child, timeout_duration)?;
    let stdout = stdout_thread.join().unwrap_or_default();
    let stderr = stderr_thread.join().unwrap_or_default();
    Ok(ProcessResult {
        exit_code: status.code().unwrap_or(1),
        stdout,
        stderr,
    })
}

fn read_pipe(pipe: Option<impl std::io::Read>) -> Vec<u8> {
    let mut buf = Vec::new();
    if let Some(mut pipe) = pipe {
        let _ = std::io::Read::read_to_end(&mut pipe, &mut buf);
    }
    buf
}

fn wait_child(
    child: &mut std::process::Child,
    timeout_duration: Duration,
) -> Result<std::process::ExitStatus, String> {
    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Ok(status),
            Ok(None) if start.elapsed() >= timeout_duration => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(format!(
                    "process timed out after {}s",
                    timeout_duration.as_secs()
                ));
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(20)),
            Err(e) => return Err(format!("wait: {e}")),
        }
    }
}

/// Run an executable with an argument vector, timeout, and retained output tails.
///
/// `env_overrides` are `[environment.vars]` replacements applied on top of a full copy of
/// this process's environment. `env` is applied after those replacements.
///
/// On Windows, a `.cmd` or `.bat` resolved via `PATHEXT` is launched through `cmd.exe` so
/// npm shims (`opencode.cmd`, `claude.cmd`, …) run. Arguments are quoted for that parser.
/// Newlines are written into a temporary launcher batch file, because `cmd /c` discards
/// the text after the first newline.
pub async fn run_process(
    program: &str,
    args: &[String],
    cwd: Option<&std::path::Path>,
    env: &[(String, String)],
    env_overrides: &BTreeMap<String, String>,
    timeout_duration: Duration,
    max_output_bytes: usize,
) -> Result<ProcessResult, String> {
    run_process_with_lines(
        program,
        args,
        cwd,
        env,
        env_overrides,
        timeout_duration,
        max_output_bytes,
        None,
    )
    .await
}

/// Receives each stdout line (without the line ending) while the process runs.
pub type LineSink = std::sync::Arc<dyn Fn(String) + Send + Sync>;

/// [`run_process`] that also hands every stdout line to `on_stdout_line` as it arrives.
#[allow(clippy::too_many_arguments)]
pub async fn run_process_with_lines(
    program: &str,
    args: &[String],
    cwd: Option<&std::path::Path>,
    env: &[(String, String)],
    env_overrides: &BTreeMap<String, String>,
    timeout_duration: Duration,
    max_output_bytes: usize,
    on_stdout_line: Option<LineSink>,
) -> Result<ProcessResult, String> {
    let (mut cmd, _cleanup) =
        tokio_command(program, args).map_err(|e| format!("spawn {program}: {e}"))?;
    cmd.stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    apply_spawn_environment(&mut cmd, env_overrides, env, cwd);
    // Platform process-group isolation is applied by the OS defaults; kill_on_drop
    // covers timeout cancellation for the direct child.

    let mut child = cmd.spawn().map_err(|e| format!("spawn {program}: {e}"))?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| "missing stdout".to_string())?;
    let mut stderr = child
        .stderr
        .take()
        .ok_or_else(|| "missing stderr".to_string())?;

    let stdout_task = tokio::spawn(async move {
        let mut buf = Vec::new();
        let mut lines = on_stdout_line.map(|sink| LineSplitter::new(sink, max_output_bytes));
        let mut chunk = [0_u8; 8192];
        loop {
            match stdout.read(&mut chunk).await {
                Ok(0) => break,
                Ok(n) => {
                    if let Some(lines) = &mut lines {
                        lines.push(&chunk[..n]);
                    }
                    buf.extend_from_slice(&chunk[..n]);
                    if buf.len() > max_output_bytes {
                        let keep = max_output_bytes;
                        buf = buf[buf.len() - keep..].to_vec();
                    }
                }
                Err(_) => break,
            }
        }
        if let Some(lines) = &mut lines {
            lines.finish();
        }
        buf
    });
    let stderr_task = tokio::spawn(async move {
        let mut buf = Vec::new();
        let mut chunk = [0_u8; 8192];
        loop {
            match stderr.read(&mut chunk).await {
                Ok(0) => break,
                Ok(n) => {
                    buf.extend_from_slice(&chunk[..n]);
                    if buf.len() > max_output_bytes {
                        let keep = max_output_bytes;
                        buf = buf[buf.len() - keep..].to_vec();
                    }
                }
                Err(_) => break,
            }
        }
        buf
    });

    let wait = timeout(timeout_duration, child.wait());
    let status = match wait.await {
        Ok(Ok(status)) => status,
        Ok(Err(e)) => return Err(format!("wait: {e}")),
        Err(_) => {
            let _ = child.start_kill();
            let _ = child.wait().await;
            return Err(format!(
                "process timed out after {}s",
                timeout_duration.as_secs()
            ));
        }
    };

    let stdout = stdout_task.await.unwrap_or_default();
    let stderr = stderr_task.await.unwrap_or_default();
    Ok(ProcessResult {
        exit_code: status.code().unwrap_or(1),
        stdout,
        stderr,
    })
}

/// Splits a byte stream into lines for a [`LineSink`]. A line longer than `max` is delivered in
/// pieces so a stream without newlines cannot grow without bound.
struct LineSplitter {
    sink: LineSink,
    pending: Vec<u8>,
    max: usize,
}

impl LineSplitter {
    fn new(sink: LineSink, max: usize) -> Self {
        Self {
            sink,
            pending: Vec::new(),
            max: max.max(1),
        }
    }

    fn push(&mut self, bytes: &[u8]) {
        self.pending.extend_from_slice(bytes);
        while let Some(end) = self.pending.iter().position(|&b| b == b'\n') {
            let line: Vec<u8> = self.pending.drain(..=end).collect();
            self.emit(&line[..end]);
        }
        if self.pending.len() > self.max {
            let line = std::mem::take(&mut self.pending);
            self.emit(&line);
        }
    }

    fn finish(&mut self) {
        if !self.pending.is_empty() {
            let line = std::mem::take(&mut self.pending);
            self.emit(&line);
        }
    }

    fn emit(&self, line: &[u8]) {
        let line = line.strip_suffix(b"\r").unwrap_or(line);
        (self.sink)(String::from_utf8_lossy(line).into_owned());
    }
}

/// Write bytes to a child's stdin then close (unused helper for future setup scripts).
pub async fn write_all_close<W: AsyncWriteExt + Unpin>(
    writer: &mut W,
    data: &[u8],
) -> Result<(), String> {
    writer.write_all(data).await.map_err(|e| e.to_string())?;
    writer.shutdown().await.map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[tokio::test]
    async fn child_pwd_follows_its_working_directory() {
        let dir = tempfile::tempdir().unwrap();
        let expected = dir.path().canonicalize().unwrap();

        let result = run_process(
            "sh",
            &["-c".into(), "printf %s \"$PWD\"".into()],
            Some(dir.path()),
            &[],
            &BTreeMap::new(),
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        assert_eq!(result.exit_code, 0);
        let pwd = String::from_utf8(result.stdout).unwrap();
        assert_eq!(std::path::Path::new(&pwd).canonicalize().unwrap(), expected);
    }

    #[tokio::test]
    async fn child_copies_parent_env_and_applies_overrides() {
        let inherited = "CURUPIRA_SPAWN_INHERITED";
        let replaced = "CURUPIRA_SPAWN_OVERRIDE";
        let only_config = "CURUPIRA_SPAWN_ONLY_CONFIG";
        std::env::set_var(inherited, "from-parent");
        std::env::set_var(replaced, "parent-value");
        std::env::remove_var(only_config);

        let mut overrides = BTreeMap::new();
        overrides.insert(replaced.into(), "from-config".into());
        overrides.insert(only_config.into(), "config-only".into());

        let script = format!(
            "printf '%s\\n%s\\n%s' \"${{{inherited}}}\" \"${{{replaced}}}\" \"${{{only_config}}}\""
        );
        let result = run_process(
            "sh",
            &["-c".into(), script],
            None,
            &[],
            &overrides,
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        std::env::remove_var(inherited);
        std::env::remove_var(replaced);

        assert_eq!(
            result.exit_code,
            0,
            "{:?}",
            String::from_utf8_lossy(&result.stderr)
        );
        let stdout = String::from_utf8(result.stdout).unwrap();
        assert_eq!(stdout, "from-parent\nfrom-config\nconfig-only");
    }

    #[tokio::test]
    async fn call_site_env_and_workdir_win_over_overrides() {
        let dir = tempfile::tempdir().unwrap();
        let mut overrides = BTreeMap::new();
        overrides.insert("GIT_DIR".into(), "/should-not-leak".into());
        overrides.insert("CURUPIRA_SPAWN_EXTRA".into(), "from-config".into());
        overrides.insert("PWD".into(), "/not-the-workdir".into());

        let result = run_process(
            "sh",
            &[
                "-c".into(),
                "printf '%s\\n%s\\n%s' \"${GIT_DIR-unset}\" \"$CURUPIRA_SPAWN_EXTRA\" \"$PWD\""
                    .into(),
            ],
            Some(dir.path()),
            &[("CURUPIRA_SPAWN_EXTRA".into(), "from-extra".into())],
            &overrides,
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        assert_eq!(
            result.exit_code,
            0,
            "{:?}",
            String::from_utf8_lossy(&result.stderr)
        );
        let stdout = String::from_utf8(result.stdout).unwrap();
        let mut lines = stdout.lines();
        assert_eq!(lines.next(), Some("unset"));
        assert_eq!(lines.next(), Some("from-extra"));
        let pwd = std::path::Path::new(lines.next().unwrap())
            .canonicalize()
            .unwrap();
        assert_eq!(pwd, dir.path().canonicalize().unwrap());
    }
}

#[cfg(test)]
mod launch_tests {
    use super::*;

    fn collector() -> (LineSink, std::sync::Arc<std::sync::Mutex<Vec<String>>>) {
        let lines = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
        let sink = std::sync::Arc::clone(&lines);
        (
            std::sync::Arc::new(move |line| sink.lock().unwrap().push(line)),
            lines,
        )
    }

    #[test]
    fn line_splitter_joins_chunks_and_flushes_the_tail() {
        let (sink, lines) = collector();
        let mut splitter = LineSplitter::new(sink, 1000);
        splitter.push(b"one\r\ntw");
        splitter.push(b"o\n\nthree");
        splitter.finish();
        assert_eq!(*lines.lock().unwrap(), vec!["one", "two", "", "three"]);
    }

    #[test]
    fn line_splitter_bounds_lines_without_newlines() {
        let (sink, lines) = collector();
        let mut splitter = LineSplitter::new(sink, 4);
        splitter.push(b"abcdefgh");
        splitter.finish();
        assert_eq!(*lines.lock().unwrap(), vec!["abcdefgh"]);
        assert!(splitter.pending.is_empty());
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn streams_stdout_lines_while_keeping_the_captured_output() {
        let (sink, lines) = collector();
        let result = run_process_with_lines(
            "printf",
            &["a\nb\nc".to_string()],
            None,
            &[],
            &BTreeMap::new(),
            Duration::from_secs(10),
            1024,
            Some(sink),
        )
        .await
        .unwrap();
        assert_eq!(result.exit_code, 0);
        assert_eq!(result.stdout, b"a\nb\nc");
        assert_eq!(*lines.lock().unwrap(), vec!["a", "b", "c"]);
    }

    #[test]
    fn missing_name_reports_path() {
        let err = resolve_executable("curupira-definitely-missing-bin").unwrap_err();
        assert!(err.contains("not found on PATH"), "{err}");
    }

    #[test]
    fn missing_path_is_not_described_as_path_lookup() {
        let err = resolve_executable("/no/such/curupira-bin").unwrap_err();
        assert!(err.contains("not found"), "{err}");
        assert!(!err.contains("PATH"), "{err}");
    }

    #[test]
    fn batch_arguments_match_cmd_shim_escaping() {
        // Expected strings are `node-cross-spawn`'s escapeArgument(..., true).
        assert_eq!(escape_argument("", true), r#"^^^"^^^""#);
        assert_eq!(escape_argument("hello", true), r#"^^^"hello^^^""#);
        assert_eq!(
            escape_argument("hello world", true),
            r#"^^^"hello^^^ world^^^""#
        );
        assert_eq!(escape_argument("100%", true), r#"^^^"100^^^%^^^""#);
        assert_eq!(escape_argument("%PATH%", true), r#"^^^"^^^%PATH^^^%^^^""#);
        assert_eq!(escape_argument("a^b", true), r#"^^^"a^^^^b^^^""#);
        assert_eq!(escape_argument("a&b", true), r#"^^^"a^^^&b^^^""#);
        assert_eq!(
            escape_argument("say \"hi\"", true),
            r#"^^^"say^^^ \^^^"hi\^^^"^^^""#
        );
    }

    #[test]
    fn batch_launcher_doubles_percents_and_embeds_newlines_for_the_shim() {
        let command = batch_command_line(
            Path::new(r"C:\npm\opencode.cmd"),
            &["hello".into(), "line1\nline2".into(), "100%".into()],
        );
        let script = batch_launcher_script(&command);
        assert!(
            script.contains("^^^\"line1^^^\"^^^\r\n\r\n^\r\n\r\n^^^\"line2^^^\""),
            "{script:?}"
        );
        assert!(script.contains("^^^\"100^^^%%^^^\""));
        assert!(script.starts_with("@echo off\r\nsetlocal DisableDelayedExpansion\r\n"));
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn cmd_shim_on_path_receives_arguments_intact() {
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("args.json");
        let shim = dir.path().join("curupira_argv_shim.cmd");
        let dumper_rs = dir.path().join("dump_args.rs");
        let dumper_exe = dir.path().join("dump_args.exe");
        // npm shims end in `node.exe script %*`, and node reads that with CommandLineToArgvW.
        // cscript does not, so the recorder is a tiny executable with the same parser.
        std::fs::write(
            &dumper_rs,
            r#"fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let out = std::env::var("CURUPIRA_SHIM_OUT").unwrap();
    let mut json = String::from("[");
    for (i, arg) in args.iter().enumerate() {
        if i > 0 { json.push(','); }
        json.push('"');
        for c in arg.chars() {
            match c {
                '"' => json.push_str("\\\""),
                '\\' => json.push_str("\\\\"),
                '\n' => json.push_str("\\n"),
                '\r' => json.push_str("\\r"),
                c => json.push(c),
            }
        }
        json.push('"');
    }
    json.push(']');
    std::fs::write(out, json).unwrap();
}
"#,
        )
        .unwrap();
        let compiled = std::process::Command::new("rustc")
            .arg("--edition=2021")
            .arg(&dumper_rs)
            .arg("-o")
            .arg(&dumper_exe)
            .output()
            .unwrap();
        assert!(
            compiled.status.success(),
            "rustc failed: {}",
            String::from_utf8_lossy(&compiled.stderr)
        );
        std::fs::write(
            &shim,
            format!(
                "@echo off\r\nsetlocal DisableDelayedExpansion\r\n\"{}\" %*\r\n",
                dumper_exe.display()
            ),
        )
        .unwrap();

        let old_path = std::env::var_os("PATH");
        let old_pathext = std::env::var_os("PATHEXT");
        let mut parts = vec![dir.path().to_path_buf()];
        if let Some(old) = &old_path {
            parts.extend(std::env::split_paths(old));
        }
        std::env::set_var("PATH", std::env::join_paths(parts).unwrap());
        std::env::set_var("PATHEXT", ".COM;.EXE;.BAT;.CMD");

        let args = vec![
            String::new(),
            "hello world".into(),
            "%PATH%".into(),
            "a^b".into(),
            "a&b".into(),
            "say \"hi\"".into(),
            "line1\nline2".into(),
            "100%".into(),
        ];
        let result = run_process(
            "curupira_argv_shim",
            &args,
            Some(dir.path()),
            &[(
                "CURUPIRA_SHIM_OUT".into(),
                out.to_string_lossy().into_owned(),
            )],
            &BTreeMap::new(),
            Duration::from_secs(20),
            64 * 1024,
        )
        .await;

        match &old_path {
            Some(value) => std::env::set_var("PATH", value),
            None => std::env::remove_var("PATH"),
        }
        match &old_pathext {
            Some(value) => std::env::set_var("PATHEXT", value),
            None => std::env::remove_var("PATHEXT"),
        }

        let result = result.unwrap();
        let captured = std::fs::read_to_string(&out).unwrap_or_default();
        assert_eq!(
            result.exit_code,
            0,
            "stdout={:?} stderr={:?} file={captured:?}",
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr)
        );
        let parsed: Vec<String> = serde_json::from_str(captured.trim()).unwrap_or_else(|err| {
            panic!(
                "json {err}: {captured:?} stderr={:?}",
                String::from_utf8_lossy(&result.stderr)
            )
        });
        assert_eq!(parsed, args, "file={captured:?}");
    }
}
