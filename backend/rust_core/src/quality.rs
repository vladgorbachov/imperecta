//! Data-quality assessment for scraped product records.
//!
//! New module (no Python predecessor): sits conceptually between extraction
//! and the data_firewall door. Pure and structural — every rule keys off the
//! record itself plus the marketplace's allowed-currency whitelist; no
//! per-shop branching, no network, no DB.
//!
//! Output: score 0..=100, letter grade, machine-readable flags. Flags marked
//! critical are the ones the caller should treat as reject-worthy; soft flags
//! only lower the score.

use serde::Serialize;

use crate::pricing::{currency_token_is_ambiguous, MAX_REALISTIC_PRICE};

#[derive(Debug, Clone, Serialize)]
pub struct QualityInput {
    pub title: Option<String>,
    pub price: Option<f64>,
    pub original_price: Option<f64>,
    pub currency: Option<String>,
    pub currency_raw: Option<String>,
    pub image_url: Option<String>,
    pub url: Option<String>,
    pub description: Option<String>,
    pub brand: Option<String>,
    pub category_path: Option<Vec<String>>,
    /// Marketplace whitelist (ISO codes). Empty slice = no whitelist known.
    pub allowed_currencies: Vec<String>,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct QualityReport {
    pub score: u8,
    pub grade: char,
    pub flags: Vec<String>,
    /// True when any critical flag fired (reject-worthy).
    pub critical: bool,
}

const CRITICAL_FLAGS: &[&str] = &[
    "missing_title",
    "invalid_price",
    "unrealistic_price",
    "currency_not_allowed",
];

fn looks_like_slug(title: &str) -> bool {
    // URL-tail artefacts: no spaces, several dash/underscore separators.
    if title.contains(' ') {
        return false;
    }
    let separators = title.chars().filter(|c| *c == '-' || *c == '_').count();
    separators >= 2
}

fn is_probable_url(value: &str) -> bool {
    value.starts_with("http://") || value.starts_with("https://")
}

pub fn assess(input: &QualityInput) -> QualityReport {
    let mut flags: Vec<String> = Vec::new();
    let mut penalty: i32 = 0;

    // --- title -----------------------------------------------------------
    match input.title.as_deref().map(str::trim) {
        None | Some("") => {
            flags.push("missing_title".into());
            penalty += 40;
        }
        Some(t) => {
            let char_count = t.chars().count();
            if char_count < 3 {
                flags.push("title_too_short".into());
                penalty += 15;
            }
            if char_count > 500 {
                flags.push("title_too_long".into());
                penalty += 5;
            }
            if t.chars().all(|c| c.is_ascii_digit()) {
                flags.push("title_numeric_only".into());
                penalty += 20;
            }
            if looks_like_slug(t) {
                flags.push("title_slug_like".into());
                penalty += 10;
            }
        }
    }

    // --- price -----------------------------------------------------------
    match input.price {
        None => {
            flags.push("missing_price".into());
            penalty += 25;
        }
        Some(p) if p <= 0.0 => {
            flags.push("invalid_price".into());
            penalty += 40;
        }
        Some(p) if p > MAX_REALISTIC_PRICE => {
            flags.push("unrealistic_price".into());
            penalty += 40;
        }
        Some(p) => {
            if p < 0.5 {
                flags.push("suspiciously_low_price".into());
                penalty += 10;
            }
            if let Some(orig) = input.original_price {
                if orig > 0.0 {
                    if orig < p {
                        flags.push("discount_inverted".into());
                        penalty += 10;
                    } else if orig > p && (orig - p) / orig > 0.90 {
                        flags.push("suspicious_discount".into());
                        penalty += 10;
                    }
                }
            }
        }
    }

    // --- currency ----------------------------------------------------------
    match input.currency.as_deref().map(str::trim) {
        None | Some("") => {
            if input.price.is_some() {
                flags.push("missing_currency".into());
                penalty += 15;
            }
        }
        Some(code) => {
            let upper = code.to_uppercase();
            if upper.len() != 3 || !upper.chars().all(|c| c.is_ascii_alphabetic()) {
                flags.push("currency_malformed".into());
                penalty += 20;
            } else if !input.allowed_currencies.is_empty()
                && !input
                    .allowed_currencies
                    .iter()
                    .any(|c| c.eq_ignore_ascii_case(&upper))
            {
                flags.push("currency_not_allowed".into());
                penalty += 40;
            }
            if currency_token_is_ambiguous(input.currency_raw.as_deref())
                && input.allowed_currencies.is_empty()
            {
                flags.push("currency_ambiguous_unresolved".into());
                penalty += 10;
            }
        }
    }

    // --- media / links -----------------------------------------------------
    match input.image_url.as_deref().map(str::trim) {
        None | Some("") => {
            flags.push("missing_image".into());
            penalty += 8;
        }
        Some(img) if !is_probable_url(img) && !img.starts_with("//") && !img.starts_with('/') => {
            flags.push("image_url_malformed".into());
            penalty += 8;
        }
        _ => {}
    }
    if let Some(url) = input.url.as_deref() {
        if !url.trim().is_empty() && !is_probable_url(url.trim()) {
            flags.push("url_malformed".into());
            penalty += 10;
        }
    }

    // --- enrichment (soft) --------------------------------------------------
    match input.description.as_deref().map(str::trim) {
        None | Some("") => {
            flags.push("missing_description".into());
            penalty += 4;
        }
        _ => {}
    }
    if input.brand.as_deref().map_or(true, |b| b.trim().is_empty()) {
        flags.push("missing_brand".into());
        penalty += 3;
    }
    if input
        .category_path
        .as_ref()
        .map_or(true, |p| p.is_empty())
    {
        flags.push("missing_category".into());
        penalty += 3;
    }

    let score = (100 - penalty).clamp(0, 100) as u8;
    let grade = match score {
        90..=100 => 'A',
        75..=89 => 'B',
        60..=74 => 'C',
        40..=59 => 'D',
        _ => 'F',
    };
    let critical = flags
        .iter()
        .any(|f| CRITICAL_FLAGS.contains(&f.as_str()));

    QualityReport {
        score,
        grade,
        flags,
        critical,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn full_record() -> QualityInput {
        QualityInput {
            title: Some("Bosch GSR 12V-30 cordless drill".into()),
            price: Some(129.99),
            original_price: Some(149.99),
            currency: Some("EUR".into()),
            currency_raw: Some("€".into()),
            image_url: Some("https://shop.example/img/drill.jpg".into()),
            url: Some("https://shop.example/p/drill".into()),
            description: Some("12V cordless drill".into()),
            brand: Some("Bosch".into()),
            category_path: Some(vec!["Tools".into(), "Drills".into()]),
            allowed_currencies: vec!["EUR".into()],
        }
    }

    #[test]
    fn perfect_record_is_a() {
        let report = assess(&full_record());
        assert_eq!(report.score, 100);
        assert_eq!(report.grade, 'A');
        assert!(report.flags.is_empty());
        assert!(!report.critical);
    }

    #[test]
    fn missing_title_is_critical() {
        let mut record = full_record();
        record.title = None;
        let report = assess(&record);
        assert!(report.critical);
        assert!(report.flags.contains(&"missing_title".to_string()));
    }

    #[test]
    fn currency_outside_whitelist_is_critical() {
        let mut record = full_record();
        record.currency = Some("XXX".into());
        let report = assess(&record);
        assert!(report.critical);
        assert!(report.flags.contains(&"currency_not_allowed".to_string()));
    }

    #[test]
    fn bare_record_grades_low_but_not_critical() {
        let record = QualityInput {
            title: Some("Widget".into()),
            price: Some(10.0),
            original_price: None,
            currency: None,
            currency_raw: None,
            image_url: None,
            url: None,
            description: None,
            brand: None,
            category_path: None,
            allowed_currencies: vec![],
        };
        let report = assess(&record);
        assert!(!report.critical);
        assert!(report.score < 90);
        assert!(report.flags.contains(&"missing_currency".to_string()));
    }

    #[test]
    fn zero_price_is_critical() {
        let mut record = full_record();
        record.price = Some(0.0);
        let report = assess(&record);
        assert!(report.critical);
        assert!(report.flags.contains(&"invalid_price".to_string()));
    }
}
