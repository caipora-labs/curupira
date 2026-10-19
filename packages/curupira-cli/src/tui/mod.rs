//! Interactive dashboard for `curupira tui`.

mod agent_output;
pub mod app;
#[cfg(test)]
mod fixtures;
mod logo;
pub mod theme;
pub mod ui;

use std::io::{self, Stdout};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::Receiver;
use std::time::{Duration, Instant};

use ratatui::backend::CrosstermBackend;
use ratatui::crossterm::event::{
    self, DisableMouseCapture, EnableMouseCapture, Event, KeyEventKind, MouseEventKind,
};
use ratatui::crossterm::terminal::{
    disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen,
};
use ratatui::crossterm::{cursor, execute};
use ratatui::Terminal;

use app::{App, Conversation, DispatchStatus, Entry, Feed};

const TICK: Duration = Duration::from_millis(100);
/// How long the startup logo stays up unless a key or click skips it.
const SPLASH: Duration = Duration::from_millis(1200);

/// What the dashboard shows besides demo sessions.
#[derive(Debug, Clone, Default)]
pub struct Context {
    pub default_agent: Option<String>,
    pub automations: usize,
    /// File that receives stderr while the dashboard owns the terminal.
    pub log_path: Option<PathBuf>,
}

/// Run the dashboard until the user quits or `interrupted` is set.
///
/// Returns how many dispatched tasks were still running at exit.
pub fn run(
    context: &Context,
    feed: &Receiver<Feed>,
    interrupted: &AtomicBool,
) -> io::Result<usize> {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let user = std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .unwrap_or_else(|_| "user".into());
    let mut app = App::new(
        Vec::new(),
        Conversation::new(intro(context)),
        cwd,
        &user,
        dirs::home_dir().as_deref(),
    );
    app.default_agent.clone_from(&context.default_agent);

    let _stderr = context.log_path.as_deref().map(StderrRedirect::to_file);
    install_panic_hook();
    let _guard = TerminalGuard;
    let mut terminal = enter()?;
    splash(&mut terminal, interrupted)?;
    terminal.clear()?;

    loop {
        while let Ok(item) = feed.try_recv() {
            app.push_feed(item);
        }
        if std::mem::take(&mut app.needs_clear) {
            terminal.clear()?;
        }
        terminal.draw(|frame| ui::draw(frame, &mut app))?;
        if app.should_quit || interrupted.load(Ordering::SeqCst) {
            break;
        }
        if event::poll(TICK)? {
            match event::read()? {
                Event::Key(key) => app.handle_key(key),
                Event::Mouse(mouse) => app.handle_mouse(mouse),
                _ => {}
            }
        }
    }
    Ok(match app.dispatch {
        DispatchStatus::Running { active } => active,
        DispatchStatus::Stopped { .. } => 0,
    })
}

/// Show the startup logo while the background dispatch starts.
fn splash(
    terminal: &mut Terminal<CrosstermBackend<Stdout>>,
    interrupted: &AtomicBool,
) -> io::Result<()> {
    let start = Instant::now();
    loop {
        let progress = start.elapsed().as_secs_f64() / SPLASH.as_secs_f64();
        if progress >= 1.0 || interrupted.load(Ordering::SeqCst) {
            return Ok(());
        }
        terminal.draw(|frame| ui::draw_splash(frame, progress))?;
        if event::poll(Duration::from_millis(30))? {
            let skip = match event::read()? {
                Event::Key(key) => key.kind == KeyEventKind::Press,
                Event::Mouse(mouse) => matches!(mouse.kind, MouseEventKind::Down(_)),
                _ => false,
            };
            if skip {
                return Ok(());
            }
        }
    }
}

fn intro(context: &Context) -> Vec<Entry> {
    let dispatch = match context.automations {
        0 => "No automations are configured, so nothing is dispatched. Add [automations.<name>] to settings.toml.".to_owned(),
        1 => "Dispatching 1 automation in the background. Each task opens a session in the sidebar.".to_owned(),
        n => format!("Dispatching {n} automations in the background. Each task opens a session in the sidebar."),
    };
    let agent = match &context.default_agent {
        Some(agent) => format!("Default agent: {agent} ([assistant].agent)."),
        None => "No default agent: set [assistant].agent in settings.toml.".to_owned(),
    };
    vec![Entry::Note(dispatch), Entry::Note(agent)]
}

fn enter() -> io::Result<Terminal<CrosstermBackend<Stdout>>> {
    enable_raw_mode()?;
    execute!(io::stdout(), EnterAlternateScreen, EnableMouseCapture)?;
    Terminal::new(CrosstermBackend::new(io::stdout()))
}

fn restore_terminal() {
    let _ = disable_raw_mode();
    let _ = execute!(
        io::stdout(),
        DisableMouseCapture,
        LeaveAlternateScreen,
        cursor::Show
    );
}

/// Restores the terminal on every exit path, including `?` errors.
struct TerminalGuard;

impl Drop for TerminalGuard {
    fn drop(&mut self) {
        restore_terminal();
    }
}

fn install_panic_hook() {
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        restore_terminal();
        stderr::restore();
        previous(info);
    }));
}

/// Sends fd 2 (tracing, extension and agent stderr) to a file so it cannot draw over the UI.
struct StderrRedirect;

impl StderrRedirect {
    fn to_file(path: &Path) -> Self {
        stderr::redirect(path);
        Self
    }
}

impl Drop for StderrRedirect {
    fn drop(&mut self) {
        stderr::restore();
    }
}

#[cfg(unix)]
mod stderr {
    use std::fs::OpenOptions;
    use std::os::fd::AsRawFd;
    use std::path::Path;
    use std::sync::atomic::{AtomicI32, Ordering};

    /// Duplicate of the original stderr while redirected, else -1.
    static SAVED: AtomicI32 = AtomicI32::new(-1);

    pub fn redirect(path: &Path) {
        let Ok(file) = OpenOptions::new().create(true).append(true).open(path) else {
            return;
        };
        // SAFETY: dup/dup2 on valid descriptors; `file` stays open until dup2 has copied it.
        unsafe {
            let saved = libc::dup(libc::STDERR_FILENO);
            if saved < 0 {
                return;
            }
            if libc::dup2(file.as_raw_fd(), libc::STDERR_FILENO) < 0 {
                libc::close(saved);
                return;
            }
            SAVED.store(saved, Ordering::SeqCst);
        }
    }

    pub fn restore() {
        let saved = SAVED.swap(-1, Ordering::SeqCst);
        if saved >= 0 {
            // SAFETY: `saved` came from dup() above and is restored exactly once.
            unsafe {
                libc::dup2(saved, libc::STDERR_FILENO);
                libc::close(saved);
            }
        }
    }
}

#[cfg(not(unix))]
mod stderr {
    pub fn redirect(_path: &std::path::Path) {}
    pub fn restore() {}
}
