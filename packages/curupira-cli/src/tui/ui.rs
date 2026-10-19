//! Frame composition. Every interactive rectangle is recorded in [`App::regions`].

use ratatui::layout::{Alignment, Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};
use ratatui::Frame;
use unicode_width::{UnicodeWidthChar, UnicodeWidthStr};

use super::app::{ActivityKind, App, DispatchStatus, Entry, Focus, SessionStatus, ViewState};
use super::logo;
use super::theme;

pub const MIN_WIDTH: u16 = 48;
pub const MIN_HEIGHT: u16 = 12;
/// Sidebar share of the screen, and its bounds in columns.
const SIDEBAR_PERCENT: u16 = 22;
const SIDEBAR_MIN: u16 = 22;
const SIDEBAR_MAX: u16 = 48;
const PROMPT: &str = "curupira > ";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Columns {
    pub sidebar: Rect,
    pub workspace: Rect,
}

/// Split the screen, or `None` when it is too small to be usable.
#[must_use]
pub fn columns(area: Rect) -> Option<Columns> {
    if area.width < MIN_WIDTH || area.height < MIN_HEIGHT {
        return None;
    }
    let width = (area.width * SIDEBAR_PERCENT / 100).clamp(SIDEBAR_MIN, SIDEBAR_MAX);
    let [sidebar, workspace] =
        Layout::horizontal([Constraint::Length(width), Constraint::Min(0)]).areas(area);
    Some(Columns { sidebar, workspace })
}

pub fn draw(frame: &mut Frame, app: &mut App) {
    let area = frame.area();
    frame.render_widget(Block::new().style(Style::new().bg(theme::BG)), area);
    // Carry over only what keyboard handling needs between frames.
    let previous = std::mem::take(&mut app.regions);
    app.regions.session_capacity = previous.session_capacity;
    let Some(cols) = columns(area) else {
        draw_too_small(frame, area);
        return;
    };
    draw_sidebar(frame, app, cols.sidebar);
    draw_workspace(frame, app, cols.workspace);
}

/// Startup screen: the logo centered with a tagline and a progress line filled to `progress`
/// (0.0 to 1.0).
pub fn draw_splash(frame: &mut Frame, progress: f64) {
    const BAR: u16 = 28;
    let area = frame.area();
    frame.render_widget(Block::new().style(Style::new().bg(theme::BG)), area);
    let tagline = format!(
        "Local automations for coding agents  ·  v{}",
        crate::version::short_version()
    );
    // The compact lockup, centered; below it: blank, tagline, blank, progress line.
    let art = logo::lockup_wide();
    if art.width() + 4 > area.width || art.rows() + 4 > area.height {
        let y = area.y + area.height / 2;
        frame.render_widget(
            Line::styled("curupira", fg(theme::BRAND).add_modifier(Modifier::BOLD))
                .alignment(Alignment::Center),
            row(area, y),
        );
        return;
    }
    let top = area.y + (area.height - (art.rows() + 4)) / 2;
    let left = area.x + (area.width - art.width()) / 2;
    frame.render_widget(
        Paragraph::new(art.lines(theme::BG)),
        Rect::new(left, top, art.width(), art.rows()),
    );
    let below = top + art.rows();
    frame.render_widget(
        Line::styled(
            truncate(&tagline, usize::from(area.width)),
            fg(theme::FAINT),
        )
        .alignment(Alignment::Center),
        row(area, below + 1),
    );
    let bar = BAR.min(area.width);
    let filled = (f64::from(bar) * progress.clamp(0.0, 1.0)).round() as u16;
    let bar_line = Line::from(vec![
        Span::styled("━".repeat(usize::from(filled)), fg(theme::ACCENT)),
        Span::styled("━".repeat(usize::from(bar - filled)), fg(theme::DIVIDER)),
    ]);
    frame.render_widget(
        bar_line,
        Rect::new(area.x + (area.width - bar) / 2, below + 3, bar, 1),
    );
}

fn fg(color: Color) -> Style {
    Style::new().fg(color)
}

fn row(area: Rect, y: u16) -> Rect {
    Rect::new(area.x, y, area.width, 1)
}

/// Inset horizontally by `pad` columns on each side.
fn inset(area: Rect, pad: u16) -> Rect {
    let pad = pad.min(area.width / 2);
    Rect::new(area.x + pad, area.y, area.width - 2 * pad, area.height)
}

fn divider(width: u16) -> Line<'static> {
    Line::styled("─".repeat(usize::from(width)), fg(theme::DIVIDER))
}

/// Cut `text` to `max` display columns, ending with `…` when shortened.
fn truncate(text: &str, max: usize) -> String {
    if text.width() <= max {
        return text.to_owned();
    }
    let mut out = String::new();
    let mut used = 0;
    for c in text.chars() {
        let w = c.width().unwrap_or(0);
        if used + w + 1 > max {
            break;
        }
        used += w;
        out.push(c);
    }
    if max > 0 {
        out.push('…');
    }
    out
}

/// Keep the end of `text` (paths are most specific at the end).
fn truncate_start(text: &str, max: usize) -> String {
    if text.width() <= max {
        return text.to_owned();
    }
    let mut kept: Vec<char> = Vec::new();
    let mut used = 1;
    for c in text.chars().rev() {
        let w = c.width().unwrap_or(0);
        if used + w > max {
            break;
        }
        used += w;
        kept.push(c);
    }
    let tail: String = kept.into_iter().rev().collect();
    if max == 0 {
        tail
    } else {
        format!("…{tail}")
    }
}

/// Word-wrap into lines of `first` columns, then `rest` columns. Long words are split.
fn wrap(text: &str, first: usize, rest: usize) -> Vec<String> {
    let mut lines = Vec::new();
    for paragraph in text.split('\n') {
        let mut line = String::new();
        let mut used = 0;
        for word in paragraph.split_whitespace() {
            let limit = if lines.is_empty() { first } else { rest }.max(1);
            let w = word.width();
            let gap = usize::from(used > 0);
            if used + gap + w <= limit {
                if gap == 1 {
                    line.push(' ');
                }
                line.push_str(word);
                used += gap + w;
                continue;
            }
            if used > 0 {
                lines.push(std::mem::take(&mut line));
                used = 0;
            }
            for c in word.chars() {
                let limit = if lines.is_empty() { first } else { rest }.max(1);
                let cw = c.width().unwrap_or(0);
                if used + cw > limit && used > 0 {
                    lines.push(std::mem::take(&mut line));
                    used = 0;
                }
                line.push(c);
                used += cw;
            }
        }
        lines.push(line);
    }
    lines
}

fn draw_too_small(frame: &mut Frame, area: Rect) {
    let lines = vec![
        Line::styled("Terminal too small", fg(theme::TEXT)),
        Line::styled(
            format!("Resize to at least {MIN_WIDTH} × {MIN_HEIGHT}"),
            fg(theme::FAINT),
        ),
    ];
    let y = area.y + area.height.saturating_sub(2) / 2;
    let target = Rect::new(area.x, y, area.width, area.height.min(2));
    frame.render_widget(Paragraph::new(lines).alignment(Alignment::Center), target);
}

fn draw_sidebar(frame: &mut Frame, app: &mut App, area: Rect) {
    frame.render_widget(Block::new().style(Style::new().bg(theme::PANEL)), area);
    app.regions.sidebar = area;
    let pad = if area.width < 24 { 1 } else { 2 };
    let inner = inset(area, pad);
    let compact = area.height < 20;
    let gap = u16::from(!compact);
    let bottom = area.bottom().saturating_sub(1);
    let mut y = area.y + 1;

    y += draw_brand(frame, inner, y, bottom.saturating_sub(y)) + gap + u16::from(!compact);

    let home_active = app.view == ViewState::Home;
    let (bracket, label) = if home_active {
        (
            fg(theme::MUTED),
            fg(theme::TEXT).add_modifier(Modifier::BOLD),
        )
    } else {
        (fg(theme::FAINT), fg(theme::MUTED))
    };
    let home = Line::from(vec![
        Span::styled("[ ", bracket),
        Span::styled("Home", label),
        Span::styled(" ]", bracket),
    ]);
    let home_row = row(inner, y);
    if home_active {
        let chip = Rect::new(home_row.x, y, (home.width() as u16).min(home_row.width), 1);
        frame.render_widget(
            Block::new().style(Style::new().bg(theme::SURFACE_DIM)),
            chip,
        );
    }
    frame.render_widget(home, home_row);
    right_label(frame, home_row, "h");
    app.regions.home = row(area, y);
    y += 1 + gap;

    frame.render_widget(divider(inner.width), row(inner, y));
    y += 1 + gap;

    let title_row = row(inner, y);
    frame.render_widget(
        Line::styled("SESSIONS", fg(theme::MUTED).add_modifier(Modifier::BOLD)),
        title_row,
    );
    let running = app
        .sessions
        .iter()
        .filter(|s| s.status == SessionStatus::Running)
        .count();
    if running > 0 {
        right_label(frame, title_row, &format!("{running} running"));
    }
    y += 1 + gap;

    if app.sessions.is_empty() {
        let hint = Paragraph::new(vec![
            Line::styled("No sessions yet.", fg(theme::FAINT)),
            Line::styled("Tasks appear here.", fg(theme::FAINT)),
        ]);
        frame.render_widget(
            hint,
            Rect::new(inner.x, y, inner.width, 2.min(bottom.saturating_sub(y))),
        );
        app.regions.session_capacity = 0;
        return;
    }

    if y >= bottom {
        app.regions.session_capacity = 0;
        return;
    }
    let list = Rect::new(area.x, y, area.width, bottom - y);
    draw_sessions(frame, app, list, pad, gap);
}

/// Faint text at the right end of `row`, leaving the rest of the row's styles alone.
fn right_label(frame: &mut Frame, row: Rect, text: &str) {
    let width = (text.width() as u16).min(row.width);
    frame.render_widget(
        Span::styled(text.to_owned(), fg(theme::FAINT)),
        Rect::new(row.right() - width, row.y, width, 1),
    );
}

/// The icon beside the wordmark, with the version below, when it fits; the icon with the name
/// as text otherwise; just the name when even the icon does not. Returns the rows used.
fn draw_brand(frame: &mut Frame, inner: Rect, y: u16, available: u16) -> u16 {
    // Navigation, the session title, and one session still fit below the brand.
    const BELOW: u16 = 12;
    let name = Span::styled("curupira", fg(theme::BRAND).add_modifier(Modifier::BOLD));
    let version = Span::styled(
        format!("v{}", crate::version::short_version()),
        fg(theme::FAINT),
    );
    let fits = |art: &logo::Pixmap, extra: u16| {
        art.width() <= inner.width && art.rows() + extra + BELOW <= available
    };
    let paint = |frame: &mut Frame, art: &logo::Pixmap| {
        frame.render_widget(
            Paragraph::new(art.lines(theme::PANEL)),
            Rect::new(inner.x, y, art.width(), art.rows()),
        );
    };
    let art = logo::lockup_wide();
    if fits(&art, 1) {
        paint(frame, &art);
        frame.render_widget(version, row(inner, y + art.rows()));
        return art.rows() + 1;
    }
    let icon = logo::icon();
    if !fits(&icon, 1) {
        frame.render_widget(name, row(inner, y));
        return 1;
    }
    paint(frame, &icon);
    let beside = inner.x + icon.width() + 2;
    if beside + 8 <= inner.right() {
        // Name and version sit level with the body of the flame.
        let text = Rect::new(beside, y + 3, inner.right() - beside, 1);
        frame.render_widget(name, text);
        frame.render_widget(version, Rect { y: y + 4, ..text });
        return icon.rows();
    }
    let below = y + icon.rows();
    frame.render_widget(
        Line::from(vec![name, Span::raw(" "), version]),
        row(inner, below),
    );
    icon.rows() + 1
}

fn draw_sessions(frame: &mut Frame, app: &mut App, list: Rect, pad: u16, gap: u16) {
    const ITEM: u16 = 2;
    let capacity = usize::from((list.height + gap) / (ITEM + gap)).max(1);
    app.regions.session_capacity = capacity;
    let max_scroll = app.sessions.len().saturating_sub(capacity);
    app.sidebar_scroll = app.sidebar_scroll.min(max_scroll);
    let focused = app.focus == Focus::Sidebar;
    let attached = match app.view {
        ViewState::Attached(index) => Some(index),
        ViewState::Home => None,
    };
    let text_width = usize::from(list.width.saturating_sub(pad + 3));

    let mut y = list.y;
    for (index, session) in app
        .sessions
        .iter()
        .enumerate()
        .skip(app.sidebar_scroll)
        .take(capacity)
    {
        let item = Rect::new(list.x, y, list.width, ITEM.min(list.bottom() - y));
        let is_attached = attached == Some(index);
        // The cursor shows while the sidebar is focused; otherwise only the open session does.
        let highlighted = if focused {
            index == app.selected
        } else {
            is_attached
        };
        if highlighted {
            let bg = if focused {
                theme::SURFACE
            } else {
                theme::SURFACE_DIM
            };
            frame.render_widget(Block::new().style(Style::new().bg(bg)), item);
            if focused {
                let bar = Rect::new(item.x, item.y, 1, item.height);
                frame.render_widget(
                    Paragraph::new(vec![Line::raw("▎"); usize::from(item.height)])
                        .style(fg(theme::ACCENT)),
                    bar,
                );
            }
        }
        let dot = match session.status {
            SessionStatus::Running => theme::ACCENT,
            SessionStatus::Finished => theme::OK,
            SessionStatus::Failed => theme::FAIL,
        };
        let name_style = if highlighted {
            fg(theme::TEXT).add_modifier(Modifier::BOLD)
        } else {
            fg(theme::TEXT)
        };
        let lines = vec![
            Line::from(vec![
                Span::styled("● ", fg(dot)),
                Span::styled(truncate(&session.name, text_width), name_style),
            ]),
            Line::from(vec![
                Span::raw("  "),
                Span::styled("Agent: ", fg(theme::FAINT)),
                Span::styled(
                    truncate(&session.agent, text_width.saturating_sub(7)),
                    fg(theme::MUTED),
                ),
            ]),
        ];
        frame.render_widget(Paragraph::new(lines), inset(item, pad));
        app.regions.sessions.push((index, item));
        y += ITEM + gap;
        if y >= list.bottom() {
            break;
        }
    }

    let arrow_x = list.right().saturating_sub(pad);
    if app.sidebar_scroll > 0 {
        frame.render_widget(
            Span::styled("↑", fg(theme::FAINT)),
            Rect::new(arrow_x, list.y.saturating_sub(1), 1, 1),
        );
    }
    if app.sidebar_scroll < max_scroll {
        frame.render_widget(
            Span::styled("↓", fg(theme::FAINT)),
            Rect::new(arrow_x, list.bottom(), 1, 1),
        );
    }
}

fn draw_workspace(frame: &mut Frame, app: &mut App, area: Rect) {
    let pad = if area.width < 50 { 1 } else { 3 };
    let inner = inset(area, pad);
    let hints = area.height >= 16;
    let bottom = area.bottom();
    let input_y = bottom - 1 - u16::from(hints);
    let divider_y = input_y - 1;
    let header_y = area.y + 1;

    frame.render_widget(header(app, usize::from(inner.width)), row(inner, header_y));

    let history_top = header_y + 2;
    let history = Rect::new(
        inner.x,
        history_top,
        inner.width,
        divider_y.saturating_sub(1).saturating_sub(history_top),
    );
    draw_history(frame, app, history);

    frame.render_widget(divider(inner.width), row(inner, divider_y));
    draw_input(frame, app, row(inner, input_y));
    if hints {
        frame.render_widget(hint_line(app, inner.width), row(inner, bottom - 1));
    }
}

fn header(app: &App, width: usize) -> Line<'static> {
    let bold = fg(theme::TEXT).add_modifier(Modifier::BOLD);
    match app.attached() {
        Some(session) => {
            let label = "ATTACHED: ";
            let agent = format!(" - {}", session.agent);
            let name = truncate(
                &session.name,
                width.saturating_sub(label.width() + agent.width()),
            );
            Line::from(vec![
                Span::styled(label, fg(theme::MUTED)),
                Span::styled(name, bold),
                Span::styled(agent, fg(theme::MUTED)),
            ])
        }
        None => {
            let label = "DEFAULT AGENT";
            let room = width.saturating_sub(label.width() + 5);
            let full = app.cwd.display().to_string();
            let path = if full.width() <= room {
                full
            } else {
                truncate_start(&app.cwd_short, room)
            };
            Line::from(vec![
                Span::styled(label, bold),
                Span::styled(" - ", fg(theme::FAINT)),
                Span::styled(format!("({path})"), fg(theme::MUTED)),
            ])
        }
    }
}

fn draw_history(frame: &mut Frame, app: &mut App, area: Rect) {
    app.regions.history = area;
    if area.height == 0 || area.width == 0 {
        return;
    }
    let lines = history_lines(app, usize::from(area.width));
    let height = usize::from(area.height);
    let max = lines.len().saturating_sub(height);
    app.regions.history_max_scroll = max;
    let conversation = app.conversation_mut();
    let top = conversation.scroll.map_or(max, |t| t.min(max));
    if top >= max {
        conversation.scroll = None;
    }
    let visible: Vec<Line> = lines.into_iter().skip(top).take(height).collect();
    frame.render_widget(Paragraph::new(visible), area);

    if top < max {
        let label = " ↓ newer";
        let w = (label.width() as u16).min(area.width);
        frame.render_widget(
            Span::styled(label, fg(theme::FAINT).bg(theme::BG)),
            Rect::new(area.right() - w, area.bottom() - 1, w, 1),
        );
    }
}

fn history_lines(app: &App, width: usize) -> Vec<Line<'static>> {
    let mut out: Vec<Line<'static>> = Vec::new();
    let mut previous: Option<&Entry> = None;
    for entry in &app.conversation().entries {
        // Consecutive activity or tool lines read as one log; everything else gets breathing room.
        let log_run = matches!(
            (previous, entry),
            (Some(Entry::Activity { .. }), Entry::Activity { .. })
                | (Some(Entry::Tool { .. }), Entry::Tool { .. })
        );
        if previous.is_some() && !log_run {
            out.push(Line::raw(""));
        }
        previous = Some(entry);
        match entry {
            Entry::User(text) => {
                let mut prompt = format!("{}$ ", app.prompt_label);
                if prompt.width() > width / 2 {
                    prompt = "curupira$ ".into();
                }
                let rows = wrap(text, width.saturating_sub(prompt.width()), width);
                for (n, text) in rows.into_iter().enumerate() {
                    let mut spans = Vec::new();
                    if n == 0 {
                        spans.push(Span::styled(prompt.clone(), fg(theme::MUTED)));
                    }
                    spans.push(Span::styled(text, fg(theme::TEXT)));
                    out.push(Line::from(spans));
                }
            }
            Entry::Agent { name, text } => {
                let label = format!("{name}: ");
                let rows = wrap(text, width.saturating_sub(label.width()), width);
                for (n, text) in rows.into_iter().enumerate() {
                    let mut spans = Vec::new();
                    if n == 0 {
                        spans.push(Span::styled(
                            label.clone(),
                            fg(theme::AGENT).add_modifier(Modifier::BOLD),
                        ));
                    }
                    spans.push(Span::styled(text, fg(theme::TEXT)));
                    out.push(Line::from(spans));
                }
            }
            Entry::Code { lang, lines } => code_block(&mut out, lang, lines, width),
            Entry::Note(text) => {
                for (n, text) in wrap(text, width.saturating_sub(2), width.saturating_sub(2))
                    .into_iter()
                    .enumerate()
                {
                    let lead = if n == 0 { "· " } else { "  " };
                    out.push(Line::styled(format!("{lead}{text}"), fg(theme::FAINT)));
                }
            }
            Entry::Tool { name, detail } => {
                let lead = format!("▸ {name}  ");
                out.push(Line::from(vec![
                    Span::styled(lead.clone(), fg(theme::MUTED)),
                    Span::styled(
                        truncate(detail, width.saturating_sub(lead.width())),
                        fg(theme::FAINT),
                    ),
                ]));
            }
            Entry::Error(text) => {
                for (n, text) in wrap(text, width.saturating_sub(2), width.saturating_sub(2))
                    .into_iter()
                    .enumerate()
                {
                    let lead = if n == 0 { "✗ " } else { "  " };
                    out.push(Line::styled(format!("{lead}{text}"), fg(theme::FAIL)));
                }
            }
            Entry::Activity {
                kind,
                title,
                detail,
            } => activity_lines(&mut out, *kind, title, detail.as_deref(), width),
        }
    }
    out
}

fn activity_lines(
    out: &mut Vec<Line<'static>>,
    kind: ActivityKind,
    title: &str,
    detail: Option<&str>,
    width: usize,
) {
    let (mark, color, word) = match kind {
        ActivityKind::Started => ("▸ ", theme::MUTED, "started"),
        ActivityKind::Finished => ("✓ ", theme::OK, "done"),
        ActivityKind::Failed => ("✗ ", theme::FAIL, "failed"),
    };
    let room = width.saturating_sub(2 + word.width() + 2);
    out.push(Line::from(vec![
        Span::styled(mark, fg(color)),
        Span::styled(word, fg(color)),
        Span::raw("  "),
        Span::styled(truncate(title, room), fg(theme::TEXT)),
    ]));
    if let Some(detail) = detail {
        for text in wrap(detail, width.saturating_sub(2), width.saturating_sub(2)) {
            out.push(Line::styled(format!("  {text}"), fg(theme::FAINT)));
        }
    }
}

fn code_block(out: &mut Vec<Line<'static>>, lang: &str, lines: &[String], width: usize) {
    let block = Style::new().bg(theme::CODE_BG);
    let room = width.saturating_sub(4);
    let pad_line = |spans: Vec<Span<'static>>| {
        let used: usize = spans.iter().map(Span::width).sum();
        let mut spans = spans;
        spans.push(Span::raw(" ".repeat(width.saturating_sub(used))));
        Line::from(spans).style(block)
    };
    out.push(pad_line(vec![Span::styled(
        format!("{lang:>width$}", width = width.saturating_sub(2)),
        fg(theme::FAINT),
    )]));
    for source in lines {
        let shown = truncate(source, room);
        let mut spans = vec![Span::raw("  ")];
        spans.extend(highlight(&shown, lang));
        out.push(pad_line(spans));
    }
    out.push(pad_line(Vec::new()));
}

const KEYWORDS: &[&str] = &[
    "async",
    "await",
    "const",
    "let",
    "var",
    "function",
    "return",
    "if",
    "else",
    "new",
    "true",
    "false",
    "null",
    "undefined",
    "require",
    "import",
    "from",
    "export",
    "describe",
    "it",
    "expect",
    "fn",
    "pub",
    "use",
    "impl",
    "struct",
    "match",
    "mut",
];
const SQL_KEYWORDS: &[&str] = &[
    "ALTER",
    "TABLE",
    "ADD",
    "COLUMN",
    "CREATE",
    "INDEX",
    "CONCURRENTLY",
    "ON",
    "NULL",
    "NOT",
    "SELECT",
    "FROM",
    "WHERE",
    "INSERT",
    "INTO",
    "VALUES",
    "UPDATE",
    "SET",
    "TIMESTAMPTZ",
    "PRIMARY",
    "KEY",
];

/// A small lexer for demo snippets: keywords, strings, numbers, comments.
fn highlight(line: &str, lang: &str) -> Vec<Span<'static>> {
    let comment = if lang == "sql" { "--" } else { "//" };
    let (code, rest) = match line.find(comment) {
        Some(at) => line.split_at(at),
        None => (line, ""),
    };
    let mut spans = Vec::new();
    let chars: Vec<char> = code.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        let start = i;
        let style = if c == '"' || c == '\'' || c == '`' {
            i += 1;
            while i < chars.len() && chars[i] != c {
                i += 1;
            }
            i = (i + 1).min(chars.len());
            fg(theme::CODE_STRING)
        } else if c.is_ascii_digit() {
            while i < chars.len() && (chars[i].is_ascii_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            fg(theme::CODE_NUMBER)
        } else if c.is_alphabetic() || c == '_' {
            while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            let keyword = if lang == "sql" {
                SQL_KEYWORDS.contains(&word.as_str())
            } else {
                KEYWORDS.contains(&word.as_str())
            };
            fg(if keyword {
                theme::CODE_KEYWORD
            } else {
                theme::CODE_TEXT
            })
        } else if c.is_whitespace() {
            while i < chars.len() && chars[i].is_whitespace() {
                i += 1;
            }
            Style::new()
        } else {
            i += 1;
            fg(theme::CODE_PUNCT)
        };
        spans.push(Span::styled(
            chars[start..i].iter().collect::<String>(),
            style,
        ));
    }
    if !rest.is_empty() {
        spans.push(Span::styled(rest.to_owned(), fg(theme::CODE_COMMENT)));
    }
    spans
}

fn draw_input(frame: &mut Frame, app: &mut App, area: Rect) {
    let focused = app.focus == Focus::Input;
    let prompt_style = if focused {
        fg(theme::ACCENT).add_modifier(Modifier::BOLD)
    } else {
        fg(theme::FAINT)
    };
    let prompt_width = (PROMPT.width() as u16).min(area.width);
    let text_x = area.x + prompt_width;
    let room = usize::from(area.width - prompt_width).saturating_sub(1);
    app.regions.input = area;
    app.regions.input_text_x = text_x;

    let chars: Vec<char> = app.input.text().chars().collect();
    let cursor = app.input.cursor();
    let width_of = |range: &[char]| -> usize { range.iter().map(|c| c.width().unwrap_or(0)).sum() };
    let mut offset = app.input.view_offset.min(cursor);
    while offset < cursor && width_of(&chars[offset..cursor]) > room {
        offset += 1;
    }
    app.input.view_offset = offset;

    let mut spans = vec![Span::styled(PROMPT, prompt_style)];
    if chars.is_empty() {
        let hint = match app.attached() {
            Some(session) => format!("Message {}", session.agent),
            None => "Message the default agent".into(),
        };
        spans.push(Span::styled(truncate(&hint, room), fg(theme::FAINT)));
    } else {
        let mut shown = String::new();
        let mut used = 0;
        for c in &chars[offset..] {
            let w = c.width().unwrap_or(0);
            if used + w > room + 1 {
                break;
            }
            used += w;
            shown.push(*c);
        }
        spans.push(Span::styled(shown, fg(theme::TEXT)));
    }
    frame.render_widget(Line::from(spans), area);
    if focused {
        let x = text_x + width_of(&chars[offset..cursor]) as u16;
        frame.set_cursor_position((x.min(area.right().saturating_sub(1)), area.y));
    }
}

fn hint_line(app: &App, width: u16) -> Line<'static> {
    let keys: &[(&str, &str)] = match app.focus {
        Focus::Input => &[("enter", "send"), ("tab", "sessions"), ("esc", "quit")],
        Focus::Sidebar => &[
            ("↑↓", "select"),
            ("enter", "open"),
            ("h", "home"),
            ("tab", "type"),
            ("q", "quit"),
        ],
    };
    let status = match &app.dispatch {
        DispatchStatus::Running { active: 0 } => "dispatch idle".to_owned(),
        DispatchStatus::Running { active } => format!("dispatch · {active} running"),
        DispatchStatus::Stopped { error: None } => "dispatch stopped".to_owned(),
        DispatchStatus::Stopped { error: Some(_) } => "dispatch failed".to_owned(),
    };
    let mut spans = Vec::new();
    let mut used = 0;
    let room = usize::from(width).saturating_sub(status.width() + 2);
    for (n, (key, label)) in keys.iter().enumerate() {
        let sep = if n == 0 { "" } else { "   " };
        let w = sep.width() + key.width() + 1 + label.width();
        if used + w > room {
            break;
        }
        used += w;
        spans.push(Span::raw(sep));
        spans.push(Span::styled(*key, fg(theme::MUTED)));
        spans.push(Span::styled(format!(" {label}"), fg(theme::FAINT)));
    }
    let status_color = match &app.dispatch {
        DispatchStatus::Stopped { error: Some(_) } => theme::FAIL,
        _ => theme::FAINT,
    };
    if usize::from(width) >= used + status.width() + 2 {
        spans.push(Span::raw(
            " ".repeat(usize::from(width) - used - status.width()),
        ));
        spans.push(Span::styled(status, fg(status_color)));
    }
    Line::from(spans)
}

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};

    use ratatui::backend::TestBackend;
    use ratatui::buffer::Buffer;
    use ratatui::crossterm::event::{KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
    use ratatui::Terminal;

    use super::*;
    use crate::tui::app::{Conversation, Target};
    use crate::tui::fixtures;

    fn app() -> App {
        App::new(
            fixtures::sessions(),
            Conversation::new(vec![Entry::Note("intro".into())]),
            PathBuf::from("/home/ana/curupira"),
            "ana",
            Some(Path::new("/home/ana")),
        )
    }

    fn render(app: &mut App, width: u16, height: u16) -> Buffer {
        let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
        terminal.draw(|frame| draw(frame, app)).unwrap();
        terminal.backend().buffer().clone()
    }

    fn text(buffer: &Buffer) -> Vec<String> {
        let area = buffer.area;
        (0..area.height)
            .map(|y| {
                (0..area.width)
                    .map(|x| buffer[(x, y)].symbol())
                    .collect::<String>()
            })
            .collect()
    }

    fn contains(lines: &[String], needle: &str) -> bool {
        lines.iter().any(|l| l.contains(needle))
    }

    #[test]
    fn sidebar_takes_about_a_fifth_within_bounds() {
        let cols = columns(Rect::new(0, 0, 120, 36)).unwrap();
        assert_eq!((cols.sidebar.width, cols.workspace.width), (26, 94));
        let cols = columns(Rect::new(0, 0, 200, 50)).unwrap();
        assert_eq!((cols.sidebar.width, cols.workspace.width), (44, 156));
        assert_eq!(columns(Rect::new(0, 0, 80, 24)).unwrap().sidebar.width, 22);
        assert_eq!(columns(Rect::new(0, 0, 400, 60)).unwrap().sidebar.width, 48);
        assert!(columns(Rect::new(0, 0, MIN_WIDTH - 1, 30)).is_none());
        assert!(columns(Rect::new(0, 0, 120, MIN_HEIGHT - 1)).is_none());
    }

    #[test]
    fn home_frame_shows_brand_header_sessions_input_and_wip() {
        let mut app = app();
        let lines = text(&render(&mut app, 120, 36));
        assert!(contains(&lines, "curupira"));
        assert!(contains(&lines, "Home"));
        assert!(contains(&lines, "SESSIONS"));
        assert!(contains(&lines, "3 running"));
        assert!(contains(&lines, "Login Feature"));
        assert!(contains(&lines, "Agent: Codegen-01"));
        assert!(contains(&lines, "DEFAULT AGENT - (/home/ana/curupira)"));
        assert!(!contains(&lines, "WIP"), "no auxiliary panel");
        let input_row = usize::from(app.regions.input.y);
        assert!(lines[input_row].contains("curupira > "));
        assert!(input_row >= 33, "input sits at the bottom");
    }

    #[test]
    fn attached_frame_shows_session_header_and_code() {
        let mut app = app();
        app.attach(0);
        let lines = text(&render(&mut app, 120, 36));
        assert!(contains(&lines, "ATTACHED: Login Feature - Cursor"));
        assert!(contains(&lines, "res.json({ token });"));
    }

    #[test]
    fn small_sizes_render_without_panicking() {
        for (w, h) in [
            (80, 24),
            (60, 20),
            (48, 12),
            (100, 30),
            (47, 12),
            (30, 10),
            (1, 1),
            (0, 0),
        ] {
            let mut app = app();
            app.attach(1);
            app.focus = Focus::Sidebar;
            let lines = text(&render(&mut app, w, h));
            if w >= MIN_WIDTH && h >= MIN_HEIGHT {
                assert!(contains(&lines, "curupira > "), "{w}x{h}");
            } else if h >= 2 && w >= 20 {
                assert!(contains(&lines, "Terminal too small"), "{w}x{h}");
            }
        }
    }

    #[test]
    fn too_small_clears_regions() {
        let mut app = app();
        render(&mut app, 120, 36);
        assert!(app
            .hit_test(app.regions.home.x, app.regions.home.y)
            .is_some());
        render(&mut app, 30, 10);
        assert_eq!(app.hit_test(2, 3), None);
        assert!(app.regions.sessions.is_empty());
    }

    #[test]
    fn rendered_regions_drive_clicks() {
        let mut app = app();
        render(&mut app, 120, 36);
        let (_, rect) = app.regions.sessions[1];
        for (x, y) in [(rect.x, rect.y), (rect.right() - 1, rect.bottom() - 1)] {
            assert_eq!(app.hit_test(x, y), Some(Target::Session(1)));
        }
        app.handle_mouse(MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column: rect.x + 4,
            row: rect.y + 1,
            modifiers: KeyModifiers::NONE,
        });
        assert_eq!(app.view, ViewState::Attached(1));
        let lines = text(&render(&mut app, 120, 36));
        assert!(contains(&lines, "ATTACHED: Auth Test - Codegen-01"));

        let home = app.regions.home;
        app.handle_mouse(MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column: home.x + 3,
            row: home.y,
            modifiers: KeyModifiers::NONE,
        });
        assert_eq!(app.view, ViewState::Home);
    }

    #[test]
    fn resize_recomputes_regions() {
        let mut app = app();
        render(&mut app, 120, 36);
        let wide = app.regions.clone();
        render(&mut app, 80, 24);
        assert_ne!(wide.input, app.regions.input);
        assert_eq!(app.regions.input.y, 22);
        assert!(app.regions.input.right() <= 80);
    }

    #[test]
    fn long_history_follows_newest_and_scrolls_back() {
        let mut app = app();
        app.attach(0);
        let lines = text(&render(&mut app, 80, 24));
        assert!(app.regions.history_max_scroll > 0, "demo overflows 80x24");
        assert!(contains(&lines, "rotating the secret"), "newest visible");
        app.scroll_history(-100);
        let lines = text(&render(&mut app, 80, 24));
        assert!(contains(&lines, "Please implement a JWT"));
        assert!(contains(&lines, "↓ newer"));
    }

    #[test]
    fn splash_centers_the_compact_logo() {
        for (w, h) in [(200, 50), (120, 36), (80, 24)] {
            let mut terminal = Terminal::new(TestBackend::new(w, h)).unwrap();
            terminal.draw(|frame| draw_splash(frame, 0.5)).unwrap();
            let lines = text(terminal.backend().buffer());
            assert!(
                contains(&lines, "Local automations for coding agents"),
                "{w}x{h}"
            );
            let first = lines.iter().position(|l| l.trim() != "").unwrap();
            let last = lines.iter().rposition(|l| l.contains('━')).unwrap();
            assert_eq!(
                last - first + 1,
                6 + 4,
                "logo rows, tagline, progress at {w}x{h}"
            );
            let below = lines.len() - 1 - last;
            assert!(
                first.abs_diff(below) <= 1,
                "{w}x{h}: top {first} bottom {below}"
            );
        }
        for (w, h) in [(40, 10), (1, 1)] {
            let mut terminal = Terminal::new(TestBackend::new(w, h)).unwrap();
            terminal.draw(|frame| draw_splash(frame, 1.0)).unwrap();
            let lines = text(terminal.backend().buffer());
            assert!(contains(&lines, "curupira") || w < 8, "{w}x{h}");
        }
    }

    #[test]
    fn home_has_no_banner_in_the_history() {
        let mut app = app();
        let lines = text(&render(&mut app, 120, 36));
        assert!(!contains(&lines, "Local automations for coding agents"));
    }

    #[test]
    fn sidebar_brand_has_no_emoji() {
        let mut app = app();
        let lines = text(&render(&mut app, 120, 36));
        assert!(contains(&lines, "curupira"));
        assert!(contains(
            &lines,
            &format!("v{}", crate::version::short_version())
        ));
        assert!(contains(&lines, "[ Home ]"));
        assert!(!lines.iter().any(|l| l.chars().any(|c| c as u32 >= 0x1F300)));
    }

    #[test]
    fn empty_sidebar_explains_where_sessions_come_from() {
        let mut app = App::new(
            Vec::new(),
            Conversation::default(),
            PathBuf::from("/repo"),
            "ana",
            None,
        );
        let lines = text(&render(&mut app, 120, 36));
        assert!(contains(&lines, "No sessions yet."));
        assert!(!contains(&lines, "running"));
        assert!(app.regions.sessions.is_empty());
    }

    #[test]
    fn session_dot_follows_status() {
        let mut app = app();
        app.sessions[1].status = SessionStatus::Finished;
        app.sessions[2].status = SessionStatus::Failed;
        let buffer = render(&mut app, 120, 36);
        let dots: Vec<_> = app
            .regions
            .sessions
            .iter()
            .map(|(_, rect)| {
                let x = (rect.x..rect.right())
                    .find(|&x| buffer[(x, rect.y)].symbol() == "●")
                    .unwrap();
                buffer[(x, rect.y)].fg
            })
            .collect();
        assert_eq!(dots, vec![theme::ACCENT, theme::OK, theme::FAIL]);
        let lines = text(&buffer);
        assert!(contains(&lines, "1 running"));
    }

    #[test]
    fn wrap_respects_widths() {
        assert_eq!(wrap("aa bb cc", 5, 5), vec!["aa bb", "cc"]);
        assert_eq!(wrap("abcdefgh", 3, 4), vec!["abc", "defg", "h"]);
        assert_eq!(wrap("a\nb", 10, 10), vec!["a", "b"]);
        assert_eq!(wrap("", 10, 10), vec![""]);
    }

    #[test]
    fn truncation_keeps_width() {
        assert_eq!(truncate("hello", 10), "hello");
        assert_eq!(truncate("hello world", 6), "hello…");
        assert_eq!(truncate_start("/a/b/c/d", 5), "…/c/d");
        assert_eq!(truncate("🔥🔥🔥", 4).width(), 3);
    }

    #[test]
    fn highlight_preserves_text() {
        let line = r#"const x = "a"; // note 42"#;
        let joined: String = highlight(line, "js")
            .iter()
            .map(|s| s.content.as_ref())
            .collect();
        assert_eq!(joined, line);
        let spans = highlight("ALTER TABLE users", "sql");
        assert_eq!(spans[0].style.fg, Some(theme::CODE_KEYWORD));
    }
}
