//! Dashboard state and input handling. Rendering lives in [`super::ui`].

use std::path::{Path, PathBuf};

use ratatui::crossterm::event::{
    KeyCode, KeyEvent, KeyEventKind, KeyModifiers, MouseButton, MouseEvent, MouseEventKind,
};
use ratatui::layout::{Position, Rect};
use unicode_width::UnicodeWidthChar;

use super::agent_output;
use crate::dispatch::{DispatchEvent, TaskStart};

/// Lines moved per mouse-wheel notch in the history.
const WHEEL_LINES: isize = 3;
/// Oldest entries are dropped past this many, so a chatty agent cannot grow memory forever.
const MAX_ENTRIES: usize = 2000;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ViewState {
    Home,
    Attached(usize),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Focus {
    Sidebar,
    Input,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Entry {
    User(String),
    Agent {
        name: String,
        text: String,
    },
    Code {
        lang: String,
        lines: Vec<String>,
    },
    Tool {
        name: String,
        detail: String,
    },
    Note(String),
    Error(String),
    /// A dispatch milestone on Home.
    Activity {
        kind: ActivityKind,
        title: String,
        detail: Option<String>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivityKind {
    Started,
    Finished,
    Failed,
}

#[derive(Debug, Default)]
pub struct Conversation {
    pub entries: Vec<Entry>,
    /// First visible line while scrolled back; `None` follows the newest entry.
    pub scroll: Option<usize>,
    unsent_noted: bool,
}

impl Conversation {
    #[must_use]
    pub fn new(entries: Vec<Entry>) -> Self {
        Self {
            entries,
            ..Self::default()
        }
    }

    fn push(&mut self, entry: Entry) {
        self.entries.push(entry);
        if self.entries.len() > MAX_ENTRIES {
            let excess = self.entries.len() - MAX_ENTRIES;
            self.entries.drain(..excess);
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionStatus {
    Running,
    Finished,
    Failed,
}

/// One dispatched task and what its coding agent has reported so far.
#[derive(Debug)]
pub struct Session {
    pub key: String,
    /// Alias from `[repositories.<alias>]`.
    pub repository: String,
    /// The task's name (issue or pull request title, else the automation) until the coding
    /// agent titles its session; then the agent's title.
    pub name: String,
    pub agent: String,
    pub status: SessionStatus,
    pub conversation: Conversation,
}

impl Session {
    fn from_start(start: TaskStart) -> Self {
        let mut context = format!("Automation {}", start.automation);
        if start.title != start.automation {
            context.push_str(&format!("  ·  {}", start.title));
        }
        if let Some(url) = &start.url {
            context.push_str(&format!("  ·  {url}"));
        }
        Self {
            key: start.key,
            repository: start.repository,
            name: start.title,
            agent: start.agent,
            status: SessionStatus::Running,
            conversation: Conversation::new(vec![Entry::Note(context), Entry::User(start.prompt)]),
        }
    }

    /// Provider name for history labels: `opencode` from `opencode · openai/gpt-5.5`.
    fn provider(&self) -> &str {
        self.agent.split(" · ").next().unwrap_or(&self.agent)
    }
}

/// What the event loop feeds the app besides terminal input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Feed {
    Dispatch(DispatchEvent),
    /// The background dispatch loop ended, with its error if it failed.
    Stopped(Option<String>),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DispatchStatus {
    Running { active: usize },
    Stopped { error: Option<String> },
}

/// Interactive areas from the last frame. `ui::draw` writes them; mouse handling only reads them.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Regions {
    pub home: Rect,
    pub sidebar: Rect,
    pub sessions: Vec<(usize, Rect)>,
    /// Rows available to the repository list. Scroll math uses this with `sidebar_gap`.
    pub list_height: u16,
    /// Blank rows between sidebar items. `0` when the sidebar is compact.
    pub sidebar_gap: u16,
    pub history: Rect,
    pub history_max_scroll: usize,
    pub input: Rect,
    /// Column where the input text (after the prompt) starts.
    pub input_text_x: u16,
}

/// One row group in the sidebar: a repository header, or a session under it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SidebarItem {
    Repository {
        name: String,
        /// An agent is running in this repository.
        running: bool,
        /// At least one session, finished or not.
        occupied: bool,
    },
    Session(usize),
}

impl SidebarItem {
    /// Terminal rows this item occupies, before the gap that follows it.
    #[must_use]
    pub fn rows(&self) -> u16 {
        match self {
            Self::Repository { .. } => 1,
            Self::Session(_) => 2,
        }
    }
}

/// First index after `start` that does not fit in `height` rows.
pub(crate) fn visible_end(items: &[SidebarItem], start: usize, height: u16, gap: u16) -> usize {
    if height == 0 || start >= items.len() {
        return start.min(items.len());
    }
    let mut used = 0u16;
    let mut end = start;
    while end < items.len() {
        let extra = if end > start { gap } else { 0 };
        if used.saturating_add(extra) >= height {
            break;
        }
        let row_budget = height - used - extra;
        used += extra + items[end].rows().min(row_budget);
        end += 1;
        if used >= height {
            break;
        }
    }
    end
}

/// Largest first-item index from which the last item is still on screen.
pub(crate) fn max_item_scroll(items: &[SidebarItem], height: u16, gap: u16) -> usize {
    if items.is_empty() || height == 0 {
        return 0;
    }
    let mut start = items.len() - 1;
    while start > 0 && visible_end(items, start - 1, height, gap) == items.len() {
        start -= 1;
    }
    start
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Target {
    Home,
    Session(usize),
    Input { column: u16 },
    Sidebar,
    History,
}

/// Single-line editor; `cursor` and `view_offset` count chars, not bytes.
#[derive(Debug, Default)]
pub struct InputLine {
    text: String,
    cursor: usize,
    /// First char shown when the text is wider than the field.
    pub view_offset: usize,
}

impl InputLine {
    #[must_use]
    pub fn text(&self) -> &str {
        &self.text
    }

    #[must_use]
    pub fn cursor(&self) -> usize {
        self.cursor
    }

    fn len(&self) -> usize {
        self.text.chars().count()
    }

    fn byte_at(&self, index: usize) -> usize {
        self.text
            .char_indices()
            .nth(index)
            .map_or(self.text.len(), |(i, _)| i)
    }

    pub fn insert(&mut self, c: char) {
        let at = self.byte_at(self.cursor);
        self.text.insert(at, c);
        self.cursor += 1;
    }

    pub fn backspace(&mut self) {
        if self.cursor > 0 {
            self.cursor -= 1;
            let at = self.byte_at(self.cursor);
            self.text.remove(at);
        }
    }

    pub fn delete(&mut self) {
        if self.cursor < self.len() {
            let at = self.byte_at(self.cursor);
            self.text.remove(at);
        }
    }

    pub fn left(&mut self) {
        self.cursor = self.cursor.saturating_sub(1);
    }

    pub fn right(&mut self) {
        self.cursor = (self.cursor + 1).min(self.len());
    }

    pub fn home(&mut self) {
        self.cursor = 0;
    }

    pub fn end(&mut self) {
        self.cursor = self.len();
    }

    /// Place the cursor at `columns` display columns past `view_offset`.
    pub fn set_cursor_at_column(&mut self, columns: u16) {
        let mut used = 0;
        let mut index = self.view_offset.min(self.len());
        for c in self.text.chars().skip(index) {
            let width = c.width().unwrap_or(0);
            if used + width > usize::from(columns) {
                break;
            }
            used += width;
            index += 1;
        }
        self.cursor = index;
    }

    /// Return the text and clear the field.
    pub fn take(&mut self) -> String {
        self.cursor = 0;
        self.view_offset = 0;
        std::mem::take(&mut self.text)
    }
}

pub struct App {
    pub view: ViewState,
    pub focus: Focus,
    pub sessions: Vec<Session>,
    /// Registered repository aliases, in display order. Sessions for an alias that is not
    /// listed here are grouped after these.
    pub repositories: Vec<String>,
    pub selected: usize,
    /// Index of the first [`SidebarItem`] drawn in the repository list.
    pub sidebar_scroll: usize,
    pub home: Conversation,
    pub input: InputLine,
    pub cwd: PathBuf,
    /// `cwd` with the home directory as `~`, for tight spaces.
    pub cwd_short: String,
    /// Shell-style prompt shown before user messages, e.g. `curupira@ana:~/repo`.
    pub prompt_label: String,
    pub default_agent: Option<String>,
    pub dispatch: DispatchStatus,
    pub regions: Regions,
    pub should_quit: bool,
    /// Repaint the whole screen next frame (task end, Ctrl+L). An agent can write straight to
    /// the terminal as soon as it starts, before this loop paints the new session, so task start
    /// must not clear or that text disappears immediately.
    pub needs_clear: bool,
}

impl App {
    #[must_use]
    pub fn new(
        sessions: Vec<Session>,
        repositories: Vec<String>,
        home: Conversation,
        cwd: PathBuf,
        user: &str,
        home_dir: Option<&Path>,
    ) -> Self {
        let cwd_short = tilde_path(&cwd, home_dir);
        let prompt_label = format!("curupira@{user}:{}", prompt_path(&cwd, &cwd_short));
        Self {
            view: ViewState::Home,
            focus: Focus::Input,
            sessions,
            repositories,
            selected: 0,
            sidebar_scroll: 0,
            home,
            input: InputLine::default(),
            cwd,
            cwd_short,
            prompt_label,
            default_agent: None,
            dispatch: DispatchStatus::Running { active: 0 },
            regions: Regions::default(),
            should_quit: false,
            needs_clear: false,
        }
    }

    #[must_use]
    pub fn attached(&self) -> Option<&Session> {
        match self.view {
            ViewState::Home => None,
            ViewState::Attached(index) => self.sessions.get(index),
        }
    }

    #[must_use]
    pub fn conversation(&self) -> &Conversation {
        self.attached().map_or(&self.home, |s| &s.conversation)
    }

    pub fn conversation_mut(&mut self) -> &mut Conversation {
        match self.view {
            ViewState::Attached(index) if index < self.sessions.len() => {
                &mut self.sessions[index].conversation
            }
            _ => &mut self.home,
        }
    }

    pub fn go_home(&mut self) {
        self.view = ViewState::Home;
    }

    pub fn attach(&mut self, index: usize) {
        if index < self.sessions.len() {
            self.selected = index;
            self.view = ViewState::Attached(index);
            self.keep_selected_visible();
        }
    }

    pub fn select_next(&mut self) {
        if self.selected + 1 < self.sessions.len() {
            self.selected += 1;
            self.keep_selected_visible();
        }
    }

    pub fn select_previous(&mut self) {
        if self.selected > 0 {
            self.selected -= 1;
            self.keep_selected_visible();
        }
    }

    /// Registered repositories first, then any alias that only appears on a session.
    /// Sessions under a name stay in dispatch order.
    #[must_use]
    pub fn sidebar_items(&self) -> Vec<SidebarItem> {
        let mut names = self.repositories.clone();
        for session in &self.sessions {
            if !names.iter().any(|name| name == &session.repository) {
                names.push(session.repository.clone());
            }
        }
        let mut items = Vec::new();
        for name in names {
            let indexes: Vec<usize> = self
                .sessions
                .iter()
                .enumerate()
                .filter(|(_, session)| session.repository == name)
                .map(|(index, _)| index)
                .collect();
            let running = indexes
                .iter()
                .any(|index| self.sessions[*index].status == SessionStatus::Running);
            items.push(SidebarItem::Repository {
                name,
                running,
                occupied: !indexes.is_empty(),
            });
            for index in indexes {
                items.push(SidebarItem::Session(index));
            }
        }
        items
    }

    fn keep_selected_visible(&mut self) {
        let height = self.regions.list_height;
        if height == 0 {
            return;
        }
        let items = self.sidebar_items();
        let Some(index) = items.iter().position(
            |item| matches!(item, SidebarItem::Session(selected) if *selected == self.selected),
        ) else {
            return;
        };
        let gap = self.regions.sidebar_gap;
        if index < self.sidebar_scroll {
            self.sidebar_scroll = index;
            if self.sidebar_scroll > 0
                && matches!(
                    items[self.sidebar_scroll - 1],
                    SidebarItem::Repository { .. }
                )
                && visible_end(&items, self.sidebar_scroll - 1, height, gap) > index
            {
                self.sidebar_scroll -= 1;
            }
        }
        while self.sidebar_scroll < index
            && visible_end(&items, self.sidebar_scroll, height, gap) <= index
        {
            self.sidebar_scroll += 1;
        }
        let max = max_item_scroll(&items, height, gap);
        self.sidebar_scroll = self.sidebar_scroll.min(max);
    }

    pub fn scroll_sessions(&mut self, delta: isize) {
        let max = max_item_scroll(
            &self.sidebar_items(),
            self.regions.list_height,
            self.regions.sidebar_gap,
        );
        self.sidebar_scroll = self.sidebar_scroll.saturating_add_signed(delta).min(max);
    }

    /// Move the history view by `delta` lines (negative is older).
    pub fn scroll_history(&mut self, delta: isize) {
        let max = self.regions.history_max_scroll;
        let conversation = self.conversation_mut();
        let top = conversation.scroll.unwrap_or(max).min(max);
        let top = top.saturating_add_signed(delta).min(max);
        conversation.scroll = (top < max).then_some(top);
    }

    fn history_page(&self) -> isize {
        isize::try_from(self.regions.history.height.saturating_sub(2).max(1)).unwrap_or(1)
    }

    pub fn toggle_focus(&mut self) {
        self.focus = match self.focus {
            Focus::Sidebar => Focus::Input,
            Focus::Input => Focus::Sidebar,
        };
    }

    /// Record the typed message. Nothing is sent: sessions are not connected to the TUI yet.
    pub fn submit(&mut self) {
        if self.input.text().trim().is_empty() {
            return;
        }
        let text = self.input.take();
        let conversation = self.conversation_mut();
        conversation.push(Entry::User(text.trim().to_owned()));
        if !conversation.unsent_noted {
            conversation.unsent_noted = true;
            conversation.push(Entry::Note(
                "Not sent: agent sessions are not connected to the TUI yet.".into(),
            ));
        }
        conversation.scroll = None;
    }

    fn session_mut(&mut self, key: &str) -> Option<&mut Session> {
        self.sessions.iter_mut().find(|s| s.key == key)
    }

    fn session_name(&self, key: &str) -> String {
        self.sessions
            .iter()
            .find(|s| s.key == key)
            .map_or_else(|| key.to_owned(), |s| s.name.clone())
    }

    pub fn push_feed(&mut self, feed: Feed) {
        match feed {
            Feed::Dispatch(DispatchEvent::Output { key, line }) => {
                if let Some(session) = self.session_mut(&key) {
                    for entry in agent_output::entries(&line, session.provider()) {
                        session.conversation.push(entry);
                    }
                }
            }
            Feed::Dispatch(DispatchEvent::Titled { key, title }) => {
                if let Some(session) = self.session_mut(&key) {
                    session.name = title;
                }
            }
            Feed::Dispatch(DispatchEvent::Started(start)) => {
                self.home.push(Entry::Activity {
                    kind: ActivityKind::Started,
                    title: start.title.clone(),
                    detail: None,
                });
                self.sessions.push(Session::from_start(start));
                self.adjust_active(1);
            }
            Feed::Dispatch(DispatchEvent::Ok(key)) => {
                let title = self.session_name(&key);
                if let Some(session) = self.session_mut(&key) {
                    session.status = SessionStatus::Finished;
                    session
                        .conversation
                        .push(Entry::Note("Task finished.".into()));
                }
                self.home.push(Entry::Activity {
                    kind: ActivityKind::Finished,
                    title,
                    detail: None,
                });
                self.adjust_active(-1);
                self.needs_clear = true;
            }
            Feed::Dispatch(DispatchEvent::Fail { key, error }) => {
                let title = self.session_name(&key);
                if let Some(session) = self.session_mut(&key) {
                    session.status = SessionStatus::Failed;
                    session.conversation.push(Entry::Error(error.clone()));
                }
                self.home.push(Entry::Activity {
                    kind: ActivityKind::Failed,
                    title,
                    detail: Some(error),
                });
                self.adjust_active(-1);
                self.needs_clear = true;
            }
            Feed::Stopped(error) => {
                let text = match &error {
                    Some(error) => format!("Background dispatch stopped: {error}"),
                    None => "Background dispatch stopped.".into(),
                };
                self.home.push(Entry::Note(text));
                self.dispatch = DispatchStatus::Stopped { error };
            }
        }
    }

    fn adjust_active(&mut self, delta: isize) {
        if let DispatchStatus::Running { active } = &mut self.dispatch {
            *active = active.saturating_add_signed(delta);
        }
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        if key.kind == KeyEventKind::Release {
            return;
        }
        let ctrl = key.modifiers.contains(KeyModifiers::CONTROL);
        match key.code {
            KeyCode::Char('c') if ctrl => self.should_quit = true,
            KeyCode::Char('l') if ctrl => self.needs_clear = true,
            KeyCode::Esc => self.should_quit = true,
            KeyCode::Tab | KeyCode::BackTab => self.toggle_focus(),
            KeyCode::PageUp => self.scroll_history(-self.history_page()),
            KeyCode::PageDown => self.scroll_history(self.history_page()),
            _ => match self.focus {
                Focus::Sidebar => self.sidebar_key(key.code),
                Focus::Input if !ctrl => self.input_key(key.code),
                Focus::Input => {}
            },
        }
    }

    fn sidebar_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Up | KeyCode::Char('k') => self.select_previous(),
            KeyCode::Down | KeyCode::Char('j') => self.select_next(),
            KeyCode::Enter => self.attach(self.selected),
            KeyCode::Char('h') => self.go_home(),
            KeyCode::Char('q') => self.should_quit = true,
            _ => {}
        }
    }

    fn input_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Enter => self.submit(),
            KeyCode::Char(c) => self.input.insert(c),
            KeyCode::Backspace => self.input.backspace(),
            KeyCode::Delete => self.input.delete(),
            KeyCode::Left => self.input.left(),
            KeyCode::Right => self.input.right(),
            KeyCode::Home => self.input.home(),
            KeyCode::End => self.input.end(),
            KeyCode::Up => self.scroll_history(-1),
            KeyCode::Down => self.scroll_history(1),
            _ => {}
        }
    }

    #[must_use]
    pub fn hit_test(&self, column: u16, row: u16) -> Option<Target> {
        let at = Position::new(column, row);
        let r = &self.regions;
        if r.home.contains(at) {
            return Some(Target::Home);
        }
        if let Some((index, _)) = r.sessions.iter().find(|(_, rect)| rect.contains(at)) {
            return Some(Target::Session(*index));
        }
        if r.input.contains(at) {
            return Some(Target::Input {
                column: column.saturating_sub(r.input_text_x),
            });
        }
        if r.sidebar.contains(at) {
            return Some(Target::Sidebar);
        }
        if r.history.contains(at) {
            return Some(Target::History);
        }
        None
    }

    pub fn handle_mouse(&mut self, mouse: MouseEvent) {
        let target = self.hit_test(mouse.column, mouse.row);
        match mouse.kind {
            MouseEventKind::Down(MouseButton::Left) => match target {
                Some(Target::Home) => {
                    self.focus = Focus::Sidebar;
                    self.go_home();
                }
                Some(Target::Session(index)) => {
                    self.focus = Focus::Sidebar;
                    self.attach(index);
                }
                Some(Target::Input { column }) => {
                    self.focus = Focus::Input;
                    self.input.set_cursor_at_column(column);
                }
                Some(Target::Sidebar) => self.focus = Focus::Sidebar,
                Some(Target::History) | None => {}
            },
            MouseEventKind::ScrollUp | MouseEventKind::ScrollDown => {
                let down = mouse.kind == MouseEventKind::ScrollDown;
                match target {
                    Some(Target::Home | Target::Session(_) | Target::Sidebar) => {
                        self.scroll_sessions(if down { 1 } else { -1 });
                    }
                    Some(Target::History) => {
                        self.scroll_history(if down { WHEEL_LINES } else { -WHEEL_LINES });
                    }
                    Some(Target::Input { .. }) | None => {}
                }
            }
            _ => {}
        }
    }
}

/// Short directory for the shell-style prompt: `~/x/y`, or `…/y` when that is long.
fn prompt_path(cwd: &Path, short: &str) -> String {
    const MAX: usize = 24;
    if short.chars().count() <= MAX {
        return short.to_owned();
    }
    cwd.file_name().map_or_else(
        || short.to_owned(),
        |name| format!("…/{}", name.to_string_lossy()),
    )
}

/// `path` with the home directory shortened to `~`.
#[must_use]
pub fn tilde_path(path: &Path, home: Option<&Path>) -> String {
    match home.and_then(|h| path.strip_prefix(h).ok()) {
        Some(rest) if rest.as_os_str().is_empty() => "~".into(),
        Some(rest) => format!("~/{}", rest.display()),
        None => path.display().to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tui::fixtures;
    use ratatui::crossterm::event::KeyEventState;

    fn app() -> App {
        App::new(
            fixtures::sessions(),
            fixtures::repositories(),
            Conversation::default(),
            PathBuf::from("/home/ana/repo"),
            "ana",
            Some(Path::new("/home/ana")),
        )
    }

    fn press(app: &mut App, code: KeyCode) {
        app.handle_key(KeyEvent::new(code, KeyModifiers::NONE));
    }

    fn type_text(app: &mut App, text: &str) {
        for c in text.chars() {
            press(app, KeyCode::Char(c));
        }
    }

    fn click(app: &mut App, column: u16, row: u16) {
        app.handle_mouse(MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column,
            row,
            modifiers: KeyModifiers::NONE,
        });
    }

    fn wheel(app: &mut App, down: bool, column: u16, row: u16) {
        app.handle_mouse(MouseEvent {
            kind: if down {
                MouseEventKind::ScrollDown
            } else {
                MouseEventKind::ScrollUp
            },
            column,
            row,
            modifiers: KeyModifiers::NONE,
        });
    }

    fn regions() -> Regions {
        Regions {
            home: Rect::new(0, 3, 20, 1),
            sidebar: Rect::new(0, 0, 20, 30),
            sessions: vec![(0, Rect::new(0, 9, 20, 2)), (1, Rect::new(0, 12, 20, 2))],
            list_height: 4,
            sidebar_gap: 1,
            history: Rect::new(22, 3, 60, 20),
            history_max_scroll: 10,
            input: Rect::new(22, 26, 60, 1),
            input_text_x: 33,
        }
    }

    #[test]
    fn starts_home_with_input_focus() {
        let app = app();
        assert_eq!(app.view, ViewState::Home);
        assert_eq!(app.focus, Focus::Input);
        assert_eq!(app.prompt_label, "curupira@ana:~/repo");
    }

    #[test]
    fn keyboard_navigation_attaches_and_returns_home_without_losing_data() {
        let mut app = app();
        press(&mut app, KeyCode::Tab);
        assert_eq!(app.focus, Focus::Sidebar);
        press(&mut app, KeyCode::Up);
        assert_eq!(app.selected, 0, "no wrap above the first session");
        press(&mut app, KeyCode::Down);
        press(&mut app, KeyCode::Down);
        press(&mut app, KeyCode::Down);
        assert_eq!(app.selected, 2, "no wrap below the last session");
        press(&mut app, KeyCode::Enter);
        assert_eq!(app.view, ViewState::Attached(2));
        assert_eq!(app.attached().unwrap().name, "DB Migration");
        let entries = app.conversation().entries.len();
        press(&mut app, KeyCode::Char('h'));
        assert_eq!(app.view, ViewState::Home);
        assert_eq!(app.sessions.len(), 3);
        assert_eq!(app.sessions[2].conversation.entries.len(), entries);
        assert_eq!(app.selected, 2, "selection survives going home");
    }

    #[test]
    fn letters_are_text_while_the_input_is_focused() {
        let mut app = app();
        app.attach(1);
        type_text(&mut app, "hq");
        assert_eq!(app.input.text(), "hq");
        assert_eq!(app.view, ViewState::Attached(1));
        assert!(!app.should_quit);
        press(&mut app, KeyCode::Down);
        assert_eq!(app.selected, 1, "arrows do not move the session list");
    }

    #[test]
    fn enter_depends_on_focus() {
        let mut app = app();
        type_text(&mut app, "hello");
        press(&mut app, KeyCode::Enter);
        assert_eq!(
            app.view,
            ViewState::Home,
            "enter in the input never attaches"
        );
        assert_eq!(app.home.entries[0], Entry::User("hello".into()));
        assert!(app.input.text().is_empty());

        press(&mut app, KeyCode::Tab);
        type_text(&mut app, "x");
        press(&mut app, KeyCode::Enter);
        assert_eq!(app.view, ViewState::Attached(0));
        assert_eq!(
            app.home.entries.len(),
            2,
            "enter on the sidebar sends nothing"
        );
    }

    #[test]
    fn submit_records_once_noted_and_ignores_blank() {
        let mut app = app();
        app.attach(0);
        let before = app.conversation().entries.len();
        type_text(&mut app, "   ");
        press(&mut app, KeyCode::Enter);
        assert_eq!(app.conversation().entries.len(), before);
        type_text(&mut app, " one ");
        press(&mut app, KeyCode::Enter);
        type_text(&mut app, "two");
        press(&mut app, KeyCode::Enter);
        let entries = &app.conversation().entries[before..];
        assert_eq!(entries[0], Entry::User("one".into()));
        assert!(matches!(entries[1], Entry::Note(_)));
        assert_eq!(entries[2], Entry::User("two".into()));
        assert_eq!(entries.len(), 3, "no fake agent reply");
    }

    #[test]
    fn quit_keys() {
        let mut esc = app();
        press(&mut esc, KeyCode::Esc);
        assert!(esc.should_quit);
        let mut q = app();
        press(&mut q, KeyCode::Tab);
        press(&mut q, KeyCode::Char('q'));
        assert!(q.should_quit);
        let mut ctrl_c = app();
        ctrl_c.handle_key(KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(ctrl_c.should_quit);
        assert!(ctrl_c.input.text().is_empty());
    }

    #[test]
    fn key_release_is_ignored() {
        let mut app = app();
        app.handle_key(KeyEvent {
            code: KeyCode::Char('a'),
            modifiers: KeyModifiers::NONE,
            kind: KeyEventKind::Release,
            state: KeyEventState::NONE,
        });
        assert!(app.input.text().is_empty());
    }

    #[test]
    fn input_editing_handles_unicode() {
        let mut input = InputLine::default();
        for c in "aé🔥b".chars() {
            input.insert(c);
        }
        input.left();
        input.backspace();
        assert_eq!(input.text(), "aéb");
        input.home();
        input.delete();
        assert_eq!(input.text(), "éb");
        input.end();
        input.right();
        assert_eq!(input.cursor(), 2);
        input.insert('!');
        assert_eq!(input.take(), "éb!");
        assert_eq!(input.cursor(), 0);
    }

    #[test]
    fn cursor_placement_from_click_column_respects_wide_chars() {
        let mut input = InputLine::default();
        for c in "a🔥bc".chars() {
            input.insert(c);
        }
        input.set_cursor_at_column(0);
        assert_eq!(input.cursor(), 0);
        input.set_cursor_at_column(2);
        assert_eq!(input.cursor(), 1, "inside the emoji lands before it");
        input.set_cursor_at_column(3);
        assert_eq!(input.cursor(), 2);
        input.set_cursor_at_column(50);
        assert_eq!(input.cursor(), 4);
        input.view_offset = 2;
        input.set_cursor_at_column(1);
        assert_eq!(input.cursor(), 3);
    }

    #[test]
    fn hit_test_maps_regions() {
        let mut app = app();
        app.regions = regions();
        assert_eq!(app.hit_test(5, 3), Some(Target::Home));
        assert_eq!(app.hit_test(0, 9), Some(Target::Session(0)));
        assert_eq!(app.hit_test(19, 10), Some(Target::Session(0)));
        assert_eq!(app.hit_test(4, 13), Some(Target::Session(1)));
        assert_eq!(app.hit_test(4, 11), Some(Target::Sidebar));
        assert_eq!(app.hit_test(40, 26), Some(Target::Input { column: 7 }));
        assert_eq!(app.hit_test(25, 26), Some(Target::Input { column: 0 }));
        assert_eq!(app.hit_test(30, 10), Some(Target::History));
        assert_eq!(app.hit_test(100, 1), None);
    }

    #[test]
    fn clicks_change_state_only_on_interactive_targets() {
        let mut app = app();
        app.regions = regions();
        click(&mut app, 3, 13);
        assert_eq!(app.view, ViewState::Attached(1));
        assert_eq!(app.focus, Focus::Sidebar);
        click(&mut app, 30, 10);
        click(&mut app, 100, 1);
        click(&mut app, 4, 11);
        assert_eq!(
            app.view,
            ViewState::Attached(1),
            "history/outside/gap clicks"
        );
        click(&mut app, 40, 26);
        assert_eq!(app.focus, Focus::Input);
        type_text(&mut app, "hi");
        assert_eq!(app.input.text(), "hi");
        click(&mut app, 2, 3);
        assert_eq!(app.view, ViewState::Home);
    }

    #[test]
    fn cleared_regions_ignore_clicks() {
        let mut app = app();
        app.regions = Regions::default();
        click(&mut app, 0, 0);
        click(&mut app, 5, 3);
        assert_eq!(app.view, ViewState::Home);
        assert_eq!(app.focus, Focus::Input);
    }

    #[test]
    fn wheel_scrolls_history_and_follows_bottom_again() {
        let mut app = app();
        app.regions = regions();
        wheel(&mut app, false, 30, 10);
        assert_eq!(app.home.scroll, Some(7));
        wheel(&mut app, false, 30, 10);
        wheel(&mut app, false, 30, 10);
        wheel(&mut app, false, 30, 10);
        assert_eq!(app.home.scroll, Some(0));
        wheel(&mut app, true, 30, 10);
        wheel(&mut app, true, 30, 10);
        wheel(&mut app, true, 30, 10);
        wheel(&mut app, true, 30, 10);
        assert_eq!(
            app.home.scroll, None,
            "back at the bottom follows new entries"
        );
        wheel(&mut app, true, 100, 1);
        assert_eq!(app.home.scroll, None);
    }

    #[test]
    fn wheel_scrolls_session_list_within_bounds() {
        let mut app = app();
        app.regions = regions();
        let max = max_item_scroll(
            &app.sidebar_items(),
            app.regions.list_height,
            app.regions.sidebar_gap,
        );
        assert!(max >= 1, "the sample list is taller than the viewport");
        for _ in 0..max + 3 {
            wheel(&mut app, true, 3, 20);
        }
        assert_eq!(app.sidebar_scroll, max);
        for _ in 0..max + 3 {
            wheel(&mut app, false, 3, 20);
        }
        assert_eq!(app.sidebar_scroll, 0);
    }

    #[test]
    fn keyboard_selection_scrolls_list() {
        let mut app = app();
        app.regions = regions();
        app.focus = Focus::Sidebar;
        press(&mut app, KeyCode::Down);
        press(&mut app, KeyCode::Down);
        assert_eq!(app.selected, 2);
        assert!(
            session_visible(&app, 2),
            "the selected session stays in the viewport"
        );
        press(&mut app, KeyCode::Up);
        press(&mut app, KeyCode::Up);
        assert_eq!(app.selected, 0);
        assert!(session_visible(&app, 0));
    }

    fn session_visible(app: &App, session: usize) -> bool {
        let items = app.sidebar_items();
        let Some(index) = items.iter().position(
            |item| matches!(item, SidebarItem::Session(selected) if *selected == session),
        ) else {
            return false;
        };
        let end = visible_end(
            &items,
            app.sidebar_scroll,
            app.regions.list_height,
            app.regions.sidebar_gap,
        );
        (app.sidebar_scroll..end).contains(&index)
    }

    #[test]
    fn sidebar_items_follow_registered_order_then_unknown_aliases() {
        let mut app = app();
        app.sessions[0].repository = "other".into();
        let names: Vec<_> = app
            .sidebar_items()
            .into_iter()
            .map(|item| match item {
                SidebarItem::Repository { name, .. } => name,
                SidebarItem::Session(index) => format!("session:{index}"),
            })
            .collect();
        assert_eq!(
            names,
            [
                "api",
                "session:1",
                "web",
                "session:2",
                "docs",
                "other",
                "session:0",
            ]
        );
    }

    #[test]
    fn sidebar_scroll_stops_when_the_last_item_is_visible() {
        let items = [
            SidebarItem::Repository {
                name: "api".into(),
                running: true,
                occupied: true,
            },
            SidebarItem::Session(0),
            SidebarItem::Session(1),
        ];
        assert_eq!(visible_end(&items, 0, 5, 1), 2);
        assert_eq!(max_item_scroll(&items, 5, 1), 1);
        assert_eq!(max_item_scroll(&items, 20, 1), 0);
        assert_eq!(max_item_scroll(&items, 0, 1), 0);
    }

    #[test]
    fn dispatched_tasks_become_live_sessions() {
        let mut app = App::new(
            Vec::new(),
            vec!["api".into()],
            Conversation::default(),
            PathBuf::from("/repo"),
            "ana",
            None,
        );
        let start = |key: &str| {
            Feed::Dispatch(DispatchEvent::Started(TaskStart {
                key: key.into(),
                automation: "merge-dependabot".into(),
                repository: "api".into(),
                title: format!("#{key} bump x"),
                url: Some(format!("https://github.com/o/r/pull/{key}")),
                agent: "opencode · openai/gpt-5.5".into(),
                prompt: "Analyze it".into(),
            }))
        };
        app.push_feed(start("1"));
        app.push_feed(start("2"));
        assert!(
            !app.needs_clear,
            "task start leaves an agent's direct terminal writes on screen"
        );
        assert_eq!(app.dispatch, DispatchStatus::Running { active: 2 });
        assert_eq!(app.sessions.len(), 2);
        let first = &app.sessions[0];
        assert_eq!(
            (first.name.as_str(), first.repository.as_str(), first.status),
            ("#1 bump x", "api", SessionStatus::Running)
        );
        assert_eq!(
            first.conversation.entries[1],
            Entry::User("Analyze it".into())
        );

        app.push_feed(Feed::Dispatch(DispatchEvent::Output {
            key: "1".into(),
            line: r#"{"type":"text","part":{"text":"Checks are green."}}"#.into(),
        }));
        assert_eq!(
            app.sessions[0].conversation.entries.last(),
            Some(&Entry::Agent {
                name: "opencode".into(),
                text: "Checks are green.".into()
            })
        );

        app.push_feed(Feed::Dispatch(DispatchEvent::Titled {
            key: "1".into(),
            title: "Revisão do PR de dependências".into(),
        }));
        assert_eq!(app.sessions[0].name, "Revisão do PR de dependências");
        assert_eq!(
            app.sessions[0].conversation.entries[0],
            Entry::Note(
                "Automation merge-dependabot  ·  #1 bump x  ·  https://github.com/o/r/pull/1"
                    .into()
            ),
            "the task's own name stays in the session details"
        );

        app.push_feed(Feed::Dispatch(DispatchEvent::Ok("1".into())));
        assert!(
            std::mem::take(&mut app.needs_clear),
            "task end repaints over text the agent wrote to the terminal"
        );
        assert_eq!(
            app.home.entries.last(),
            Some(&Entry::Activity {
                kind: ActivityKind::Finished,
                title: "Revisão do PR de dependências".into(),
                detail: None,
            })
        );
        app.push_feed(Feed::Dispatch(DispatchEvent::Fail {
            key: "2".into(),
            error: "agent exited 1: Model unavailable".into(),
        }));
        assert!(app.needs_clear, "task failure repaints");
        assert_eq!(app.sessions[0].status, SessionStatus::Finished);
        assert_eq!(app.sessions[1].status, SessionStatus::Failed);
        assert_eq!(
            app.sessions[1].conversation.entries.last(),
            Some(&Entry::Error("agent exited 1: Model unavailable".into()))
        );
        assert_eq!(app.dispatch, DispatchStatus::Running { active: 0 });
        assert_eq!(
            app.home.entries.last(),
            Some(&Entry::Activity {
                kind: ActivityKind::Failed,
                title: "#2 bump x".into(),
                detail: Some("agent exited 1: Model unavailable".into()),
            })
        );

        app.push_feed(Feed::Stopped(Some("boom".into())));
        assert_eq!(
            app.dispatch,
            DispatchStatus::Stopped {
                error: Some("boom".into())
            }
        );
    }

    #[test]
    fn output_for_unknown_tasks_is_ignored_and_history_is_capped() {
        let mut app = app();
        app.push_feed(Feed::Dispatch(DispatchEvent::Output {
            key: "missing".into(),
            line: "hello".into(),
        }));
        let mut conversation = Conversation::default();
        for n in 0..MAX_ENTRIES + 5 {
            conversation.push(Entry::Note(n.to_string()));
        }
        assert_eq!(conversation.entries.len(), MAX_ENTRIES);
        assert_eq!(conversation.entries[0], Entry::Note("5".into()));
    }

    #[test]
    fn ctrl_l_requests_a_full_repaint() {
        let mut app = app();
        app.handle_key(KeyEvent::new(KeyCode::Char('l'), KeyModifiers::CONTROL));
        assert!(app.needs_clear);
        assert!(app.input.text().is_empty());
    }

    #[test]
    fn tilde_path_shortens_home() {
        let home = Path::new("/home/ana");
        assert_eq!(tilde_path(Path::new("/home/ana"), Some(home)), "~");
        assert_eq!(tilde_path(Path::new("/home/ana/x/y"), Some(home)), "~/x/y");
        assert_eq!(tilde_path(Path::new("/srv/x"), Some(home)), "/srv/x");
        assert_eq!(tilde_path(Path::new("/srv/x"), None), "/srv/x");
    }

    #[test]
    fn long_prompt_paths_keep_the_directory_name() {
        let cwd = Path::new("/srv/very/long/path/to/the/project");
        assert_eq!(
            prompt_path(cwd, "/srv/very/long/path/to/the/project"),
            "…/project"
        );
        assert_eq!(prompt_path(Path::new("/srv/x"), "/srv/x"), "/srv/x");
    }
}
