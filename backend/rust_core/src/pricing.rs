//! Price / currency parsing primitives.
//!
//! Line-for-line semantic port of `backend/app/common/html_parsing.py`
//! (Tier-0 closure). Any behavioural change here MUST be mirrored in the
//! Python reference until the flag flips, and is guarded by the parity
//! harness in `backend/tests/test_rust_core_parity.py`.

use once_cell::sync::Lazy;
use regex::Regex;

/// Symbol -> ISO code. Order matters: iterated in declaration order like the
/// Python dict.
pub const CURRENCY_SYMBOLS: &[(&str, &str)] = &[
    ("€", "EUR"),
    ("$", "USD"),
    ("£", "GBP"),
    ("₴", "UAH"),
    ("₽", "RUB"),
    ("zł", "PLN"),
    ("₺", "TRY"),
    ("₸", "KZT"),
    ("₾", "GEL"),
    ("₼", "AZN"),
    ("лв", "BGN"),
    ("kč", "CZK"),
    ("kr", "SEK"),
    ("ft", "HUF"),
    ("lei", "RON"),
    ("din", "RSD"),
    ("ден", "MKD"),
    ("сўм", "UZS"),
    ("сом", "KGS"),
    ("br", "BYN"),
    ("sm", "TJS"),
];

/// Textual ISO codes / abbreviations near prices.
pub const CURRENCY_TEXT_CODES: &[(&str, &str)] = &[
    ("usd", "USD"),
    ("eur", "EUR"),
    ("gbp", "GBP"),
    ("uah", "UAH"),
    ("грн", "UAH"),
    ("rub", "RUB"),
    ("руб", "RUB"),
    ("р.", "RUB"),
    ("pln", "PLN"),
    ("ron", "RON"),
    ("try", "TRY"),
    ("tl", "TRY"),
    ("kzt", "KZT"),
    ("тг", "KZT"),
    ("тенге", "KZT"),
    ("byn", "BYN"),
    ("бел.руб", "BYN"),
    ("gel", "GEL"),
    ("azn", "AZN"),
    ("man", "AZN"),
    ("bgn", "BGN"),
    ("czk", "CZK"),
    ("sek", "SEK"),
    ("nok", "NOK"),
    ("dkk", "DKK"),
    ("huf", "HUF"),
    ("hrk", "HRK"),
    ("rsd", "RSD"),
    ("mdl", "MDL"),
    ("лей", "MDL"),
    ("лэй", "MDL"),
    ("chf", "CHF"),
    ("uzs", "UZS"),
    ("kgs", "KGS"),
    ("tjs", "TJS"),
];

pub const AMBIGUOUS_TOKENS: &[&str] = &["lei", "лей", "kr", "kr."];

/// Sibling sets for shared currency tokens (RON<->MDL, Nordic kr family).
pub fn ambiguous_siblings(code: &str) -> Option<&'static [&'static str]> {
    match code {
        "RON" => Some(&["MDL"]),
        "MDL" => Some(&["RON"]),
        "SEK" => Some(&["NOK", "DKK", "ISK"]),
        "NOK" => Some(&["SEK", "DKK", "ISK"]),
        "DKK" => Some(&["SEK", "NOK", "ISK"]),
        "ISK" => Some(&["SEK", "NOK", "DKK"]),
        _ => None,
    }
}

const PRICE_CONTEXT_POSITIVE: &[&str] = &[
    "price",
    "цена",
    "стоимость",
    "total",
    "итого",
    "sale",
    "our price",
];
const PRICE_CONTEXT_NEGATIVE: &[&str] = &[
    "%",
    "cashback",
    "кэшбэк",
    "bonus",
    "бонус",
    "скидка",
    "discount",
    "save",
    "эконом",
];

pub const MAX_REALISTIC_PRICE: f64 = 5_000_000.0;

static DATE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"\d{4}[-/.]\d{2}[-/.]\d{2}").unwrap(),
        Regex::new(r"\d{2}[-/.]\d{2}[-/.]\d{4}").unwrap(),
    ]
});

static NUMBER_TOKEN_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\d{1,3}(?:[ \u{00a0}\u{2009}\u{202f}.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?")
        .unwrap()
});

static SEP_SPACING_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"\s*([,.])\s*").unwrap());

fn is_word_char(c: char) -> bool {
    // Python's \w with re.IGNORECASE on str: alphanumeric or underscore
    // (unicode-aware).
    c.is_alphanumeric() || c == '_'
}

/// Case-insensitive token search with Python-style `(?<!\w)tok(?!\w)`
/// boundaries. Returns true when `token` occurs in `haystack_lower` with
/// non-word (or absent) neighbours.
fn token_with_boundaries(haystack_lower: &str, token: &str) -> bool {
    let mut search_from = 0usize;
    while let Some(rel) = haystack_lower[search_from..].find(token) {
        let start = search_from + rel;
        let end = start + token.len();
        let before_ok = haystack_lower[..start]
            .chars()
            .next_back()
            .map_or(true, |c| !is_word_char(c));
        let after_ok = haystack_lower[end..]
            .chars()
            .next()
            .map_or(true, |c| !is_word_char(c));
        if before_ok && after_ok {
            return true;
        }
        // advance one char, not one byte
        search_from = start + haystack_lower[start..].chars().next().map_or(1, |c| c.len_utf8());
    }
    false
}

/// Detect currency ISO code from symbol characters in `text`.
pub fn parse_currency_symbol(text: &str) -> Option<&'static str> {
    let lowered = text.to_lowercase();
    for (symbol, code) in CURRENCY_SYMBOLS {
        if symbol.chars().count() == 1 {
            if text.contains(symbol) {
                return Some(code);
            }
            continue;
        }
        if token_with_boundaries(&lowered, symbol) {
            return Some(code);
        }
    }
    None
}

/// Detect currency ISO code from textual code / abbreviation near a price.
pub fn parse_currency_code(text: &str) -> Option<&'static str> {
    let lowered = text.to_lowercase();
    // Python sorts by -len(token); replicate (stable order for equal lengths
    // follows declaration order, matching CPython's stable sort).
    let mut tokens: Vec<&(&str, &str)> = CURRENCY_TEXT_CODES.iter().collect();
    tokens.sort_by_key(|(token, _)| std::cmp::Reverse(token.chars().count()));
    for (token, code) in tokens {
        if token_with_boundaries(&lowered, token) {
            return Some(code);
        }
    }
    None
}

pub fn detect_currency(text: &str) -> Option<&'static str> {
    parse_currency_symbol(text).or_else(|| parse_currency_code(text))
}

/// True when the raw currency evidence is one of the shared tokens.
pub fn currency_token_is_ambiguous(raw_text: Option<&str>) -> bool {
    match raw_text {
        None => false,
        Some(raw) => {
            let lowered = raw.trim().to_lowercase();
            if lowered.is_empty() {
                return false;
            }
            AMBIGUOUS_TOKENS.iter().any(|t| lowered.contains(t))
        }
    }
}

fn number_overlaps_date_region(raw: &str, start: usize, end: usize) -> bool {
    for pattern in DATE_PATTERNS.iter() {
        for m in pattern.find_iter(raw) {
            if start < m.end() && end > m.start() {
                return true;
            }
        }
    }
    false
}

fn is_bare_year_without_currency(token: &str, context: &str) -> bool {
    let stripped = token.trim();
    if stripped.len() != 4 || !stripped.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }
    let year: i64 = stripped.parse().unwrap_or(0);
    if !(1900..=2099).contains(&year) {
        return false;
    }
    detect_currency(context).is_none()
}

fn parse_number_token(token: &str) -> Option<f64> {
    let value = token.trim();
    if value.is_empty() {
        return None;
    }
    let value = SEP_SPACING_RE.replace_all(value, "$1").into_owned();
    let has_comma = value.contains(',');
    let has_dot = value.contains('.');
    let has_space = value.contains(' ');

    let normalized: String = if has_comma && has_dot {
        if value.rfind(',') > value.rfind('.') {
            value.replace(' ', "").replace('.', "").replace(',', ".")
        } else {
            value.replace(' ', "").replace(',', "")
        }
    } else if has_comma {
        let no_space = value.replace(' ', "");
        let parts: Vec<&str> = no_space.split(',').collect();
        if parts.len() == 2 && (parts[1].len() == 1 || parts[1].len() == 2) {
            no_space.replace(',', ".")
        } else if parts.len() >= 2 && parts[1..].iter().all(|p| p.len() == 3) {
            no_space.replace(',', "")
        } else {
            let last = parts[parts.len() - 1];
            if last.len() <= 2 {
                let head = parts[..parts.len() - 1].join("").replace(' ', "");
                format!("{head}.{last}")
            } else {
                no_space.replace(',', "")
            }
        }
    } else if has_dot {
        let no_space = value.replace(' ', "");
        let parts: Vec<&str> = no_space.split('.').collect();
        if parts.len() == 2 && (parts[1].len() == 1 || parts[1].len() == 2) {
            no_space
        } else if parts.len() >= 2 && parts[1..].iter().all(|p| p.len() == 3) {
            no_space.replace('.', "")
        } else {
            no_space
        }
    } else if has_space {
        value.replace(' ', "")
    } else {
        value
    };

    match normalized.parse::<f64>() {
        Ok(n) if n > 0.0 => Some(n),
        _ => None,
    }
}

/// Parse price from text containing EU / CIS / Anglo-Saxon number formats.
/// Semantic port of `html_parsing.parse_price_text`.
pub fn parse_price_text(text: &str) -> Option<f64> {
    if text.is_empty() {
        return None;
    }
    let raw: String = text
        .trim()
        .replace('\u{00a0}', " ")
        .replace('\u{2009}', " ")
        .replace('\u{202f}', " ");
    let lowered = raw.to_lowercase();

    let mut candidates: Vec<(f64, i64)> = Vec::new();
    for m in NUMBER_TOKEN_RE.find_iter(&raw) {
        let token = m.as_str();
        let parsed = match parse_number_token(token) {
            Some(p) => p,
            None => continue,
        };
        let (start, end) = (m.start(), m.end());
        if number_overlaps_date_region(&lowered, start, end) {
            continue;
        }
        // Python slices lowered by the same byte offsets it got from the
        // match on `raw`; str indices are chars there but raw/lowered only
        // differ in case, so byte offsets line up for our inputs. Guard to
        // char boundaries to stay panic-free on exotic case-folds.
        let ctx_start = floor_char_boundary(&lowered, start.saturating_sub(20));
        let ctx_end = ceil_char_boundary(&lowered, (end + 20).min(lowered.len()));
        let context = &lowered[ctx_start..ctx_end];

        if is_bare_year_without_currency(token, context) {
            continue;
        }
        let mut score: i64 = 0;
        let has_currency_context = detect_currency(context).is_some();
        if has_currency_context {
            score += 8;
        }
        if PRICE_CONTEXT_POSITIVE.iter().any(|mk| context.contains(mk)) {
            score += 4;
        }
        if PRICE_CONTEXT_NEGATIVE.iter().any(|mk| context.contains(mk)) {
            score -= 6;
        }
        if parsed < 1.0 {
            score -= 3;
        }
        if parsed > MAX_REALISTIC_PRICE && !has_currency_context {
            continue;
        }
        if parsed > MAX_REALISTIC_PRICE {
            score -= 20;
        }
        candidates.push((parsed, score));
    }

    if candidates.is_empty() {
        return None;
    }
    candidates.sort_by(|a, b| {
        b.1.cmp(&a.1)
            .then(b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal))
    });
    let best = candidates[0].0;
    if best > MAX_REALISTIC_PRICE {
        return None;
    }
    Some(best)
}

fn floor_char_boundary(s: &str, mut idx: usize) -> usize {
    if idx >= s.len() {
        return s.len();
    }
    while idx > 0 && !s.is_char_boundary(idx) {
        idx -= 1;
    }
    idx
}

fn ceil_char_boundary(s: &str, mut idx: usize) -> usize {
    if idx >= s.len() {
        return s.len();
    }
    while idx < s.len() && !s.is_char_boundary(idx) {
        idx += 1;
    }
    idx
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn docstring_formats() {
        assert_eq!(parse_price_text("1,234.56"), Some(1234.56));
        assert_eq!(parse_price_text("1.234,56"), Some(1234.56));
        assert_eq!(parse_price_text("1 234,56"), Some(1234.56));
        assert_eq!(parse_price_text("1 234.56"), Some(1234.56));
        assert_eq!(parse_price_text("1234,56"), Some(1234.56));
        assert_eq!(parse_price_text("1234.56"), Some(1234.56));
        assert_eq!(parse_price_text("1234"), Some(1234.0));
    }

    #[test]
    fn currency_detection() {
        assert_eq!(parse_currency_symbol("19,99 €"), Some("EUR"));
        assert_eq!(parse_currency_symbol("199 kr"), Some("SEK"));
        assert_eq!(parse_currency_symbol("digikr8"), None); // boundary
        assert_eq!(parse_currency_code("100 uah"), Some("UAH"));
        assert_eq!(parse_currency_code("55 лей"), Some("MDL"));
        assert_eq!(detect_currency("nothing here"), None);
    }

    #[test]
    fn ambiguity() {
        assert!(currency_token_is_ambiguous(Some("55 lei")));
        assert!(currency_token_is_ambiguous(Some("199 kr.")));
        assert!(!currency_token_is_ambiguous(Some("€")));
        assert!(!currency_token_is_ambiguous(None));
    }

    #[test]
    fn year_and_date_rejection() {
        assert_eq!(parse_price_text("copyright 2024"), None);
        assert_eq!(parse_price_text("2026-01-15"), None);
        assert_eq!(parse_price_text("2024 €"), Some(2024.0)); // currency context keeps it
    }
}
