//! Pixel-art logo drawn with half-block characters: every cell holds two square pixels.

use ratatui::style::{Color, Style};
use ratatui::text::{Line, Span};

const FLAME_LIGHT: Color = Color::Rgb(247, 141, 37);
const FLAME_DEEP: Color = Color::Rgb(207, 82, 19);
const LEAF: Color = Color::Rgb(63, 136, 56);

/// The flame and leaf from the brand artwork (`o` flame, `d` deep flame, `g` leaf), resampled to
/// 12 × 12 while keeping both side tongues, the inner flame, and the holes in the leaf.
const ICON: [&str; 12] = [
    "......d.....",
    "......od....",
    "....d.ood...",
    "....odood...",
    "....odood.d.",
    "...dooood.o.",
    "...doododdo.",
    "...ooddooood",
    "g..ooddddood",
    "ggggododdood",
    "gg.g.ooodod.",
    ".gg.gdoood..",
];

struct Font {
    glyphs: &'static [(char, &'static [&'static str])],
    /// Color per pixel row.
    gradient: &'static [Color],
}

/// One-pixel strokes, nine rows: cap height 0-6, x-height 2-6,
/// descender 7-8.
const LIGHT: Font = Font {
    glyphs: &[
        (
            'C',
            &[
                ".##.", "#..#", "#...", "#...", "#...", "#..#", ".##.", "....", "....",
            ],
        ),
        (
            'u',
            &[
                "...", "...", "#.#", "#.#", "#.#", "#.#", "###", "...", "...",
            ],
        ),
        (
            'r',
            &[
                "...", "...", "###", "#.#", "#..", "#..", "#..", "...", "...",
            ],
        ),
        (
            'p',
            &[
                "...", "...", "##.", "#.#", "#.#", "##.", "#..", "#..", "#..",
            ],
        ),
        ('i', &["#", ".", "#", "#", "#", "#", "#", ".", "."]),
        (
            'a',
            &[
                "...", "...", "##.", "..#", "###", "#.#", "###", "...", "...",
            ],
        ),
    ],
    // Softer than the artwork: warm orange to burnt orange, without the ember red.
    gradient: &[
        Color::Rgb(250, 160, 72),
        Color::Rgb(250, 160, 72),
        Color::Rgb(248, 150, 60),
        Color::Rgb(246, 141, 50),
        Color::Rgb(243, 132, 44),
        Color::Rgb(239, 122, 40),
        Color::Rgb(234, 112, 36),
        Color::Rgb(228, 102, 33),
        Color::Rgb(228, 102, 33),
    ],
};

/// A grid of optional pixels; `None` shows the background.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pixmap {
    width: usize,
    height: usize,
    pixels: Vec<Option<Color>>,
}

impl Pixmap {
    fn new(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            pixels: vec![None; width * height],
        }
    }

    fn from_art(rows: &[&str]) -> Self {
        let width = rows.iter().map(|r| r.len()).max().unwrap_or(0);
        let mut map = Self::new(width, rows.len());
        for (y, row) in rows.iter().enumerate() {
            for (x, c) in row.chars().enumerate() {
                map.pixels[y * width + x] = match c {
                    'o' => Some(FLAME_LIGHT),
                    'd' => Some(FLAME_DEEP),
                    'g' => Some(LEAF),
                    _ => None,
                };
            }
        }
        map
    }

    fn get(&self, x: usize, y: usize) -> Option<Color> {
        if x < self.width && y < self.height {
            self.pixels[y * self.width + x]
        } else {
            None
        }
    }

    fn blit(&mut self, other: &Self, left: usize, top: usize) {
        for y in 0..other.height {
            for x in 0..other.width {
                if let Some(color) = other.get(x, y) {
                    let (tx, ty) = (left + x, top + y);
                    if tx < self.width && ty < self.height {
                        self.pixels[ty * self.width + tx] = Some(color);
                    }
                }
            }
        }
    }

    /// Terminal columns needed.
    #[must_use]
    pub fn width(&self) -> u16 {
        u16::try_from(self.width).unwrap_or(u16::MAX)
    }

    /// Terminal rows needed (two pixel rows per cell).
    #[must_use]
    pub fn rows(&self) -> u16 {
        u16::try_from(self.height.div_ceil(2)).unwrap_or(u16::MAX)
    }

    /// One `Line` per terminal row, painting empty pixels with `bg`.
    #[must_use]
    pub fn lines(&self, bg: Color) -> Vec<Line<'static>> {
        (0..self.height)
            .step_by(2)
            .map(|y| {
                let spans: Vec<Span<'static>> = (0..self.width)
                    .map(|x| match (self.get(x, y), self.get(x, y + 1)) {
                        (None, None) => Span::styled(" ", Style::new().bg(bg)),
                        (Some(top), None) => Span::styled("▀", Style::new().fg(top).bg(bg)),
                        (None, Some(bottom)) => Span::styled("▄", Style::new().fg(bottom).bg(bg)),
                        (Some(top), Some(bottom)) if top == bottom => {
                            Span::styled("█", Style::new().fg(top).bg(bg))
                        }
                        (Some(top), Some(bottom)) => {
                            Span::styled("▀", Style::new().fg(top).bg(bottom))
                        }
                    })
                    .collect();
                Line::from(spans)
            })
            .collect()
    }
}

fn wordmark(font: &Font, text: &str) -> Pixmap {
    let glyphs: Vec<&[&str]> = text
        .chars()
        .filter_map(|c| {
            font.glyphs
                .iter()
                .find(|(g, _)| *g == c)
                .map(|(_, rows)| *rows)
        })
        .collect();
    let width = glyphs.iter().map(|g| g[0].len()).sum::<usize>() + glyphs.len().saturating_sub(1);
    let mut map = Pixmap::new(width, font.gradient.len());
    let mut left = 0;
    for glyph in glyphs {
        for (y, row) in glyph.iter().enumerate() {
            for (x, c) in row.chars().enumerate() {
                if c != '#' {
                    continue;
                }
                map.pixels[y * width + left + x] = Some(font.gradient[y]);
            }
        }
        left += glyph[0].len() + 1;
    }
    map
}

/// Mark and wordmark side by side, bottoms aligned.
fn side_by_side(mark: &Pixmap, word: &Pixmap, gap: usize) -> Pixmap {
    let height = mark.height.max(word.height);
    let mut map = Pixmap::new(mark.width + gap + word.width, height);
    map.blit(mark, 0, height - mark.height);
    map.blit(word, mark.width + gap, height - word.height);
    map
}

/// The resampled flame alone.
#[must_use]
pub fn icon() -> Pixmap {
    Pixmap::from_art(&ICON)
}

/// The icon beside the wordmark (6 rows): the sidebar brand and the splash.
#[must_use]
pub fn lockup_wide() -> Pixmap {
    side_by_side(&icon(), &wordmark(&LIGHT, "Curupira"), 2)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn art_rows_have_equal_widths() {
        assert!(ICON.iter().all(|r| r.len() == ICON[0].len()));
        for font in [&LIGHT] {
            for (c, rows) in font.glyphs {
                assert!(rows.iter().all(|r| r.len() == rows[0].len()), "glyph {c}");
                assert_eq!(rows.len(), font.gradient.len(), "glyph {c}");
            }
        }
    }

    #[test]
    fn sizes() {
        assert_eq!((icon().width(), icon().rows()), (12, 6));
        assert_eq!(wordmark(&LIGHT, "Curupira").width, 30);
        assert_eq!((lockup_wide().width(), lockup_wide().rows()), (44, 6));
    }

    #[test]
    fn half_blocks_encode_both_pixels() {
        let map = Pixmap::from_art(&["o.o", ".dd"]);
        let line = &map.lines(Color::Black)[0];
        let cells: Vec<(&str, Option<Color>, Option<Color>)> = line
            .spans
            .iter()
            .map(|s| (s.content.as_ref(), s.style.fg, s.style.bg))
            .collect();
        assert_eq!(
            cells,
            vec![
                ("▀", Some(FLAME_LIGHT), Some(Color::Black)),
                ("▄", Some(FLAME_DEEP), Some(Color::Black)),
                ("▀", Some(FLAME_LIGHT), Some(FLAME_DEEP)),
            ]
        );
    }
}
