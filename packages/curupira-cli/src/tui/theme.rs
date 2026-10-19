//! Palette for the dashboard.

use ratatui::style::Color;

pub const BG: Color = Color::Rgb(18, 18, 18);
/// Sidebar and auxiliary panel: a hair lighter than the workspace.
pub const PANEL: Color = Color::Rgb(22, 22, 22);
pub const SURFACE: Color = Color::Rgb(42, 42, 42);
/// Selected session while the sidebar is not focused.
pub const SURFACE_DIM: Color = Color::Rgb(32, 32, 32);
pub const CODE_BG: Color = Color::Rgb(27, 27, 27);

pub const TEXT: Color = Color::Rgb(224, 224, 224);
pub const MUTED: Color = Color::Rgb(145, 145, 145);
pub const FAINT: Color = Color::Rgb(98, 98, 98);
pub const DIVIDER: Color = Color::Rgb(52, 52, 52);
pub const ACCENT: Color = Color::Rgb(255, 107, 0);
/// The product name in text, matching the light wordmark's warm orange.
pub const BRAND: Color = Color::Rgb(246, 141, 50);

pub const AGENT: Color = Color::Rgb(137, 180, 250);
pub const OK: Color = Color::Rgb(140, 200, 145);
pub const FAIL: Color = Color::Rgb(232, 125, 115);

pub const CODE_TEXT: Color = Color::Rgb(205, 205, 205);
pub const CODE_KEYWORD: Color = Color::Rgb(137, 180, 250);
pub const CODE_STRING: Color = Color::Rgb(166, 218, 149);
pub const CODE_NUMBER: Color = Color::Rgb(148, 226, 213);
pub const CODE_COMMENT: Color = Color::Rgb(110, 110, 110);
pub const CODE_PUNCT: Color = Color::Rgb(150, 150, 150);
