//! Match-signature extraction — Rust twin of
//! `app/modules/matching/signature.py`. Both implementations MUST agree
//! byte-for-byte; the Python side is the blessed reference and
//! `tests/test_matching_signature.py` + the unit tests below pin the
//! shared contract (docs/MATCHING_PLAN.md, slice M1).

/// Extracted cross-shop match signature.
#[derive(Debug, Clone, PartialEq)]
pub struct MatchSignature {
    pub brand: String,
    pub code: String,
    pub codes: Vec<String>,
    pub attrs: Vec<String>,
    pub confidence: f64,
}

pub const CONFIDENCE_KNOWN_BRAND: f64 = 0.90;
pub const CONFIDENCE_HEURISTIC_BRAND: f64 = 0.75;

const STOPWORDS: [&str; 7] = ["html", "bhtml", "htm", "php", "aspx", "www", "com"];

const UNIT_SUFFIXES: [&str; 47] = [
    "gb", "tb", "mb", "kb", "mm", "cm", "km", "kg", "mg", "ml", "cl", "dl", "l",
    "g", "m", "w", "kw", "mw", "v", "kv", "mv", "a", "ah", "mah", "hz", "ghz",
    "mhz", "khz", "k", "p", "mp", "px", "dpi", "in", "inch", "cal", "kcal",
    "szt", "gab", "vnt", "tk", "pcs", "db", "bar", "rpm", "lm", "lux",
];
// Kept apart from the array above only because Rust const arrays are fixed
// size; the Python _UNIT_RE alternation is the union of both lists.
const UNIT_SUFFIXES_EXTRA: [&str; 12] = [
    "nm", "ns", "ms", "s", "min", "h", "x", "d", "fps", "bit", "mbps", "gbps",
];
const UNIT_SUFFIXES_TAIL: [&str; 2] = ["ppm", "denier"];

const PURE_DIGIT_MIN: usize = 5;
const PURE_DIGIT_MAX: usize = 9;
const MIXED_MIN_LEN: usize = 4;
const JOINED_MIN_LEN: usize = 5;

fn is_stopword(token: &str) -> bool {
    STOPWORDS.contains(&token)
}

fn is_alpha(token: &str) -> bool {
    !token.is_empty() && token.bytes().all(|b| b.is_ascii_lowercase())
}

fn is_digit(token: &str) -> bool {
    !token.is_empty() && token.bytes().all(|b| b.is_ascii_digit())
}

fn is_mixed(token: &str) -> bool {
    !is_alpha(token) && !is_digit(token)
}

fn is_unit_token(token: &str) -> bool {
    // ^\d+(unit)$
    let digits = token.bytes().take_while(|b| b.is_ascii_digit()).count();
    if digits > 0 {
        let suffix = &token[digits..];
        if suffix.is_empty() {
            // pure digits — not a unit token (handled by digit rules)
        } else if UNIT_SUFFIXES.contains(&suffix)
            || UNIT_SUFFIXES_EXTRA.contains(&suffix)
            || UNIT_SUFFIXES_TAIL.contains(&suffix)
        {
            return true;
        }
    }
    // ^\d+x\d+(x\d+)?[a-z]*$ (dimensions like 40x60, 1920x1080p)
    let parts: Vec<&str> = token.split('x').collect();
    if parts.len() == 2 || parts.len() == 3 {
        let last = parts[parts.len() - 1];
        let last_digits = last.bytes().take_while(|b| b.is_ascii_digit()).count();
        let body_ok = parts[..parts.len() - 1]
            .iter()
            .all(|p| !p.is_empty() && is_digit(p));
        if body_ok
            && last_digits > 0
            && last[last_digits..].bytes().all(|b| b.is_ascii_lowercase())
        {
            return true;
        }
    }
    false
}

fn tokenize(name: &str) -> Vec<String> {
    let lower = name.to_lowercase();
    let mut tokens = Vec::new();
    let mut current = String::new();
    for ch in lower.chars() {
        if ch.is_ascii_lowercase() || ch.is_ascii_digit() {
            current.push(ch);
        } else if !current.is_empty() {
            tokens.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

/// Extract the match signature, or None when the name is unmatchable
/// (junk slug names fail the brand-AND-code requirement by design).
pub fn extract_match_signature(
    name_normalized: &str,
    known_brands: &[String],
) -> Option<MatchSignature> {
    let tokens = tokenize(name_normalized);
    if tokens.is_empty() {
        return None;
    }

    // Brand FIRST: the brand token must never act as a model code — mixed
    // alnum brands (a4tech, mi5) otherwise mint brand-wide mega-groups.
    let mut brand: Option<&str> = None;
    let mut confidence = CONFIDENCE_HEURISTIC_BRAND;
    for token in &tokens {
        if known_brands.iter().any(|b| b == token) {
            brand = Some(token);
            confidence = CONFIDENCE_KNOWN_BRAND;
            break;
        }
    }
    if brand.is_none() {
        for token in &tokens {
            if is_alpha(token) && token.len() >= 3 && !is_stopword(token) {
                brand = Some(token);
                break;
            }
        }
    }
    let brand = brand?;

    let mut attrs: Vec<String> = Vec::new();
    let mut codes: Vec<String> = Vec::new();
    let mut add_code = |codes: &mut Vec<String>, code: String| {
        if !codes.contains(&code) {
            codes.push(code);
        }
    };

    for token in &tokens {
        if is_stopword(token) || token == brand {
            continue;
        }
        if is_unit_token(token) {
            attrs.push(token.clone());
            continue;
        }
        if is_mixed(token) && token.len() >= MIXED_MIN_LEN {
            add_code(&mut codes, token.clone());
        } else if is_digit(token)
            && (PURE_DIGIT_MIN..=PURE_DIGIT_MAX).contains(&token.len())
        {
            add_code(&mut codes, token.clone());
        }
    }

    // Neighbor joins: "galaxy s24" -> "galaxys24" (shops disagree on the
    // space inside a model name; the joined form does not). Never join
    // across the brand token (either side): the group keys would diverge
    // with word order otherwise.
    for pair in tokens.windows(2) {
        let (left, right) = (&pair[0], &pair[1]);
        if !(is_alpha(left) && left.len() >= 2 && !is_stopword(left)) {
            continue;
        }
        if left == brand || right == brand {
            continue;
        }
        if is_unit_token(right) || is_stopword(right) {
            continue;
        }
        let starts_digit = right.bytes().next().is_some_and(|b| b.is_ascii_digit());
        if !(starts_digit || is_mixed(right)) {
            continue;
        }
        let joined = format!("{left}{right}");
        if joined.len() >= JOINED_MIN_LEN && !is_unit_token(&joined) {
            add_code(&mut codes, joined);
        }
    }

    if codes.is_empty() {
        return None;
    }

    // Strongest code: mixed beats pure-digit, then longest, then
    // lexicographic — identical ordering to the Python reference sort key
    // (not is_mixed, -len, code).
    let mut ranked: Vec<&String> = codes.iter().collect();
    ranked.sort_by(|a, b| {
        (!is_mixed(a), std::cmp::Reverse(a.len()), a.as_str())
            .cmp(&(!is_mixed(b), std::cmp::Reverse(b.len()), b.as_str()))
    });
    let strongest = ranked[0].clone();

    Some(MatchSignature {
        brand: brand.to_string(),
        code: strongest,
        codes,
        attrs,
        confidence,
    })
}

// --- M2b: title_en normalization + similarity (docs/MATCHING_PLAN.md) ------

/// Glue-units: a pure number followed by one of these becomes one token
/// ("1.7" + "l" -> "1.7l"); also the suffixes checked for attribute
/// conflicts. Deterministic constant — mirror of the Python reference.
const GLUE_UNITS: [&str; 40] = [
    "gb", "tb", "mb", "kb", "mm", "cm", "m", "km", "kg", "g", "mg", "l",
    "ml", "cl", "dl", "w", "kw", "mw", "v", "mv", "kv", "a", "ah", "mah",
    "hz", "khz", "mhz", "ghz", "k", "p", "mp", "px", "in", "inch", "lm",
    "nm", "bar", "rpm", "pcs", "szt",
];

/// English glue-words dropped from title keys (marketing/noise-neutral).
const TITLE_STOPWORDS: [&str; 12] = [
    "the", "a", "an", "and", "or", "with", "for", "of", "in", "to", "on",
    "by",
];

fn is_number_token(t: &str) -> bool {
    !t.is_empty()
        && t.bytes().all(|b| b.is_ascii_digit() || b == b'.')
        && t.bytes().any(|b| b.is_ascii_digit())
        && !t.starts_with('.')
        && !t.ends_with('.')
}

/// Normalize an EN title into a sorted, deduped token set.
pub fn normalize_title_tokens(title: &str) -> Vec<String> {
    let lower = title.to_lowercase();
    let mut raw: Vec<String> = Vec::new();
    let mut current = String::new();
    for ch in lower.chars() {
        if ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == '.' {
            current.push(ch);
        } else if !current.is_empty() {
            raw.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        raw.push(current);
    }
    // strip stray dots, drop empties
    let raw: Vec<String> = raw
        .into_iter()
        .map(|t| t.trim_matches('.').to_string())
        .filter(|t| !t.is_empty())
        .collect();

    // glue "1.7" + "l" -> "1.7l"
    let mut glued: Vec<String> = Vec::with_capacity(raw.len());
    let mut i = 0;
    while i < raw.len() {
        if i + 1 < raw.len()
            && is_number_token(&raw[i])
            && GLUE_UNITS.contains(&raw[i + 1].as_str())
        {
            glued.push(format!("{}{}", raw[i], raw[i + 1]));
            i += 2;
        } else {
            glued.push(raw[i].clone());
            i += 1;
        }
    }

    let mut out: Vec<String> = glued
        .into_iter()
        .filter(|t| !TITLE_STOPWORDS.contains(&t.as_str()))
        .collect();
    out.sort_unstable();
    out.dedup();
    out
}

fn unit_attr(token: &str) -> Option<(&str, &str)> {
    let digits_dot = token
        .bytes()
        .take_while(|b| b.is_ascii_digit() || *b == b'.')
        .count();
    if digits_dot == 0 || digits_dot == token.len() {
        return None;
    }
    let (value, suffix) = token.split_at(digits_dot);
    if GLUE_UNITS.contains(&suffix) && value.bytes().any(|b| b.is_ascii_digit()) {
        Some((value, suffix))
    } else {
        None
    }
}

/// Jaccard similarity over normalized token sets, forced to 0.0 when the
/// two titles carry CONFLICTING unit attributes (same unit, different
/// value: 256gb vs 512gb are different products, however similar).
pub fn title_similarity(a: &[String], b: &[String]) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    for ta in a {
        if let Some((va, sa)) = unit_attr(ta) {
            for tb in b {
                if let Some((vb, sb)) = unit_attr(tb) {
                    if sa == sb && va != vb {
                        return 0.0;
                    }
                }
            }
        }
    }
    let mut inter = 0usize;
    for t in a {
        if b.binary_search(t).is_ok() {
            inter += 1;
        }
    }
    let union = a.len() + b.len() - inter;
    if union == 0 {
        0.0
    } else {
        inter as f64 / union as f64
    }
}

#[cfg(test)]
mod title_tests {
    use super::*;

    fn toks(s: &str) -> Vec<String> {
        normalize_title_tokens(s)
    }

    #[test]
    fn normalization_glues_units_drops_stopwords_and_sorts() {
        assert_eq!(
            toks("Sencor Electric Kettle 1.7 l, White"),
            vec!["1.7l", "electric", "kettle", "sencor", "white"]
        );
        assert_eq!(toks("Kettle with the Lid"), vec!["kettle", "lid"]);
        assert_eq!(toks("1.7L kettle"), toks("Kettle 1.7 l"));
    }

    #[test]
    fn similarity_near_identical_titles_high() {
        let a = toks("Sencor Electric Kettle 1.7 l White");
        let b = toks("Sencor Kettle 1.7l white");
        assert!(title_similarity(&a, &b) >= 0.8, "{:?} {:?}", a, b);
    }

    #[test]
    fn conflicting_unit_attrs_force_zero() {
        let a = toks("Samsung Galaxy S24 256gb Black");
        let b = toks("Samsung Galaxy S24 512gb Black");
        assert_eq!(title_similarity(&a, &b), 0.0);
    }

    #[test]
    fn unrelated_titles_low() {
        let a = toks("Green plastic ashtray");
        let b = toks("Sencor kettle 1.7l");
        assert!(title_similarity(&a, &b) < 0.2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sig(name: &str, brands: &[&str]) -> Option<MatchSignature> {
        let brands: Vec<String> = brands.iter().map(|s| s.to_string()).collect();
        extract_match_signature(name, &brands)
    }

    #[test]
    fn junk_slug_names_are_unmatchable() {
        // Live-pool examples: slug-derived ids must never form groups.
        assert_eq!(sig("pb00613262.html", &[]), None);
        assert_eq!(sig("9000863112", &[]), None);
        assert_eq!(sig("1180243", &[]), None);
        assert_eq!(sig("", &[]), None);
    }

    #[test]
    fn model_code_with_known_brand() {
        let s = sig("sencor sfd 950ss", &["sencor"]).unwrap();
        assert_eq!(s.brand, "sencor");
        assert_eq!(s.code, "sfd950ss"); // neighbor join wins on length
        assert_eq!(s.confidence, CONFIDENCE_KNOWN_BRAND);
    }

    #[test]
    fn heuristic_brand_from_first_alpha_token() {
        // "492w" reads as a wattage unit -> attr, so the shop-internal
        // "d552211" carries the code role here (weak but harmless: it can
        // only miss cross-shop matches, never fabricate them).
        let s = sig("trust gxt 492w carus white d552211", &[]).unwrap();
        assert_eq!(s.brand, "trust");
        assert!(s.attrs.contains(&"492w".to_string()));
        assert!(s.codes.contains(&"d552211".to_string()));
        assert_eq!(s.confidence, CONFIDENCE_HEURISTIC_BRAND);
    }

    #[test]
    fn units_are_attrs_not_codes() {
        let s = sig("samsung galaxy s24 ultra 256gb", &["samsung"]).unwrap();
        assert_eq!(s.brand, "samsung");
        assert_eq!(s.code, "galaxys24");
        assert!(s.attrs.contains(&"256gb".to_string()));
        assert!(!s.codes.contains(&"256gb".to_string()));
    }

    #[test]
    fn short_mixed_token_captured_via_join() {
        let s = sig("xiaomi oclean f1 dark blue", &["xiaomi"]).unwrap();
        assert_eq!(s.code, "ocleanf1");
    }

    #[test]
    fn same_product_different_spacing_same_code() {
        let a = sig("sencor sfd 950ss blender", &["sencor"]).unwrap();
        let b = sig("blender sencor sfd950ss", &["sencor"]).unwrap();
        assert_eq!(a.code, b.code);
        assert_eq!(a.brand, b.brand);
    }

    #[test]
    fn style_number_is_weak_code() {
        let s = sig("tricou under armour ua big logo ss 1109226", &[]).unwrap();
        assert!(s.codes.contains(&"1109226".to_string()));
    }

    #[test]
    fn mixed_brand_token_never_becomes_the_code() {
        // Incident: "a4tech" (mixed alnum brand) minted brand-wide
        // mega-groups keyed "a4tech|a4tech".
        let s = sig("a4tech bloody r73 ultra duo", &["a4tech"]).unwrap();
        assert_eq!(s.brand, "a4tech");
        assert_eq!(s.code, "bloodyr73");
        assert!(!s.codes.contains(&"a4tech".to_string()));
        // No model code beyond the brand token -> honest unmatched.
        assert_eq!(sig("klaviatura a4tech kr 92", &["a4tech"]), None);
    }

    #[test]
    fn no_code_means_unmatchable_even_with_brand() {
        assert_eq!(sig("rohelisest plastikust tuhatoos", &[]), None);
    }
}
