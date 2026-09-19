//! Sitemap enumeration primitives (2026-09-19, enumeration optimisation).
//!
//! The Python enumerator ran ElementTree over 50k-URL sitemap files and
//! then hashed / classified every URL in Python loops. Byte-for-byte
//! parity twins of those primitives live here: `parse_sitemap_xml`
//! (streaming quick-xml, namespace-agnostic), `url_hash` (the
//! FactListing.compute_url_hash contract), `product_like_path` (the
//! enumerator's `_url_is_product_like`) and `category_like_url` (the
//! sitemap_categories filter). Parity is pinned by
//! tests/test_rust_core_parity.py.

#[cfg(test)]
use std::collections::HashMap;

use once_cell::sync::Lazy;
use quick_xml::escape::unescape;
use quick_xml::events::Event;
use quick_xml::name::QName;
use quick_xml::Reader;
use regex::Regex;
use sha2::{Digest, Sha256};

#[derive(Debug, Default, PartialEq)]
pub struct UrlEntry {
    pub loc: String,
    pub lastmod: Option<String>,
    pub alternates: Vec<(String, String)>,
}

#[derive(Debug, Default, PartialEq)]
pub struct Sitemap {
    pub sitemaps: Vec<String>,
    pub entries: Vec<UrlEntry>,
}

fn local_name(name: QName<'_>) -> String {
    name.local_name().as_ref().to_string()
}

/// <xhtml:link rel="alternate" hreflang=".." href=".."> on the current <url>.
fn push_alternate(e: &quick_xml::events::BytesStart<'_>, current: Option<&mut UrlEntry>) {
    let Some(entry) = current else { return };
    let mut rel = String::new();
    let mut hreflang = String::new();
    let mut href = String::new();
    for attr in e.attributes().flatten() {
        let key = local_name(attr.key);
        let val = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).map(|v| v.to_string()).unwrap_or_default();
        match key.as_str() {
            "rel" => rel = val.trim().to_string(),
            "hreflang" => hreflang = val.trim().to_string(),
            "href" => href = val.trim().to_string(),
            _ => {}
        }
    }
    if rel == "alternate" && !hreflang.is_empty() && !href.is_empty() {
        entry.alternates.push((hreflang.to_lowercase(), href));
    }
}

/// Parse a sitemap index or urlset. Malformed XML yields what was parsed
/// up to the error (the Python twin returned an empty result on any parse
/// error; a truncated file is worth more than nothing — the caller dedupes).
pub fn parse_sitemap_xml(xml: &str) -> Sitemap {
    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(true);
    let mut out = Sitemap::default();
    let mut current: Option<UrlEntry> = None;
    let mut in_sitemap_elem = false;
    // Text of the open <loc>/<lastmod>: quick-xml splits text around entity
    // references ("?x=1" &amp; "y=2"), so chunks accumulate until End.
    let mut text_target: Option<&'static str> = None;
    let mut text_buf = String::new();
    loop {
        match reader.read_event() {
            Ok(Event::Start(e)) => {
                let name = local_name(e.name());
                match name.as_str() {
                    "url" => current = Some(UrlEntry::default()),
                    "sitemap" => in_sitemap_elem = true,
                    "loc" => {
                        text_target = Some("loc");
                        text_buf.clear();
                    }
                    "lastmod" => {
                        text_target = Some("lastmod");
                        text_buf.clear();
                    }
                    "link" => push_alternate(&e, current.as_mut()),
                    _ => {}
                }
            }
            Ok(Event::Empty(e)) => {
                // <xhtml:link .../> self-closing alternates
                if local_name(e.name()) == "link" {
                    push_alternate(&e, current.as_mut());
                }
            }
            Ok(Event::Text(t)) => {
                if text_target.is_some() {
                    let raw: &str = &t;
                    match unescape(raw) {
                        Ok(v) => text_buf.push_str(&v),
                        Err(_) => text_buf.push_str(raw),
                    }
                }
            }
            Ok(Event::CData(c)) => {
                if text_target.is_some() {
                    let raw: &str = &c;
                    text_buf.push_str(raw);
                }
            }
            Ok(Event::GeneralRef(r)) => {
                if text_target.is_some() {
                    let raw: &str = &r;
                    match r.resolve_char_ref() {
                        Ok(Some(ch)) => text_buf.push(ch),
                        _ => match unescape(&format!("&{raw};")) {
                            Ok(v) => text_buf.push_str(&v),
                            Err(_) => {
                                text_buf.push('&');
                                text_buf.push_str(raw);
                                text_buf.push(';');
                            }
                        },
                    }
                }
            }
            Ok(Event::End(e)) => {
                let name = local_name(e.name());
                match name.as_str() {
                    "url" => {
                        if let Some(entry) = current.take() {
                            if !entry.loc.is_empty() {
                                out.entries.push(entry);
                            }
                        }
                    }
                    "sitemap" => in_sitemap_elem = false,
                    "loc" | "lastmod" => {
                        let text = text_buf.trim().to_string();
                        if !text.is_empty() {
                            match (text_target, current.as_mut(), in_sitemap_elem) {
                                (Some("loc"), Some(entry), _) => {
                                    if entry.loc.is_empty() {
                                        entry.loc = text;
                                    }
                                }
                                (Some("lastmod"), Some(entry), _) => entry.lastmod = Some(text),
                                (Some("loc"), None, true) => out.sitemaps.push(text),
                                _ => {}
                            }
                        }
                        text_target = None;
                        text_buf.clear();
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
    }
    out
}

/// FactListing.compute_url_hash: sha256 of strip() + rstrip('/') + lower().
pub fn url_hash(url: &str) -> String {
    let normalized = url.trim().trim_end_matches('/').to_lowercase();
    let mut h = Sha256::new();
    h.update(normalized.as_bytes());
    format!("{:x}", h.finalize())
}

const PRODUCT_LINK_HINTS: [&str; 10] = [
    "/product/", "/products/", "/item/", "/p/", "/tovar/", "/dp/", "/catalog/product/",
    "/detail/", "/offer/", "/sku/",
];
static CATALOG_NUMERIC_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"/(?:catalog|detail)/\d{4,}|/(?:product|tovar|sku)/[\w-]{4,}|/p/\d+").unwrap());
static FOUR_DIGITS_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"/\d{4,}").unwrap());
static SLUG_SKU_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"-\d{3,}(?:[./]|$)").unwrap());

/// extractors._looks_like_product_url
pub fn looks_like_product_path(path: &str) -> bool {
    let lowered = path.to_lowercase();
    if PRODUCT_LINK_HINTS.iter().any(|h| lowered.contains(h)) {
        return true;
    }
    if CATALOG_NUMERIC_RE.is_match(&lowered) || FOUR_DIGITS_RE.is_match(&lowered) {
        return true;
    }
    if lowered.contains(".html") {
        return true;
    }
    lowered.split('/').filter(|s| !s.is_empty()).count() >= 3
}

/// sitemap_enumerator._url_is_product_like
pub fn product_like_path(path: &str) -> bool {
    looks_like_product_path(path) || SLUG_SKU_RE.is_match(&path.to_lowercase())
}

const CATEGORY_PATH_SEGMENTS: [&str; 17] = [
    "catalog", "c", "category", "shop", "categories", "katalog", "collection", "collections",
    "promo", "sale", "akcii", "rasprodazha", "new", "novinki", "top", "best", "popular",
];
static ANY_FOUR_DIGITS_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"\d{4,}").unwrap());
static SLUG_ID6_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"-\d{6,}(?:[-/_.]|$)").unwrap());
static DIGITS6_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\d{6,}$").unwrap());

/// extractors._looks_like_product_slug
fn looks_like_product_slug(segment: &str) -> bool {
    if segment.is_empty() {
        return false;
    }
    let lowered = segment.to_lowercase();
    lowered.ends_with(".html")
        || lowered.ends_with(".htm")
        || SLUG_ID6_RE.is_match(&lowered)
        || DIGITS6_RE.is_match(&lowered)
}

/// extractors._is_category_url
pub fn is_category_path(path: &str) -> bool {
    let lowered = path.to_lowercase();
    let segments: Vec<&str> = lowered.split('/').filter(|s| !s.is_empty()).collect();
    if segments.len() <= 1 {
        if let Some(single) = segments.first() {
            if single.len() >= 16 && (single.contains('-') || single.chars().any(|c| c.is_ascii_digit())) {
                return false;
            }
        }
        return true;
    }
    let last = segments[segments.len() - 1];
    if looks_like_product_slug(last) {
        return false;
    }
    if segments.iter().any(|s| CATEGORY_PATH_SEGMENTS.contains(s)) {
        return true;
    }
    if lowered.contains(".html") {
        return false;
    }
    if ANY_FOUR_DIGITS_RE.is_match(&lowered) {
        return false;
    }
    segments.len() == 3 && !last.is_empty() && last.len() < 15
}

const CHROME_HINTS: [&str; 27] = [
    "login", "signin", "signup", "register", "cart", "basket", "checkout", "wishlist", "account",
    "compare", "help", "faq", "about", "contact", "blog", "news", "privacy", "terms", "return",
    "delivery", "shipping", "search", "filter", "sort", "otzyvy", "/reviews", "sitemap",
];

/// sitemap_categories.category_like — structural listing-page test.
pub fn category_like_url(url: &str) -> bool {
    let (path, query) = match url.find("://") {
        Some(i) => {
            let rest = &url[i + 3..];
            let path_start = rest.find('/').map(|p| i + 3 + p).unwrap_or(url.len());
            let full = &url[path_start..];
            match full.find('?') {
                Some(q) => (&full[..q], Some(&full[q + 1..])),
                None => (full, None),
            }
        }
        None => (url, None),
    };
    let path = if path.is_empty() { "/" } else { path };
    if path == "/" || query.map(|q| !q.is_empty()).unwrap_or(false) {
        return false;
    }
    if path.split('/').any(|seg| seg.contains('=')) {
        return false;
    }
    let lowered = path.to_lowercase();
    if CHROME_HINTS.iter().any(|h| lowered.contains(h)) {
        return false;
    }
    is_category_path(path)
}

/// Path component of a URL ("/" when absent), query and fragment stripped.
fn url_path(url: &str) -> &str {
    let rest = match url.find("://") {
        Some(i) => &url[i + 3..],
        None => url,
    };
    let path = match rest.find('/') {
        Some(p) => &rest[p..],
        None => "/",
    };
    let end = path.find(['?', '#']).unwrap_or(path.len());
    &path[..end]
}

static LOCALE_SEGMENT_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^[a-z]{2}(?:[-_][a-z]{2})?$").unwrap());

/// First path segment when it reads as a locale code ("lt", "ru", "en-us"),
/// lowercased. Multi-language shops mount one catalog per locale under such
/// a prefix (pigu.lt: /lt/..., /ru/..., /en/...) and ship one sitemap tree
/// per locale — the same offer under every prefix.
pub fn url_locale_segment(url: &str) -> Option<String> {
    let first = url_path(url).trim_start_matches('/').split('/').next().unwrap_or("");
    let lowered = first.to_lowercase();
    if LOCALE_SEGMENT_RE.is_match(&lowered) {
        Some(lowered)
    } else {
        None
    }
}

/// Sitemap files that carry the image / video extension entries restate
/// product locs the product files already list (pigu.lt: 406
/// `sitemap-products-images-N.xml` beside 406 `sitemap-products-N.xml`).
const MEDIA_SITEMAP_TOKENS: [&str; 5] = ["image", "images", "img", "video", "videos"];

pub fn is_media_sitemap(url: &str) -> bool {
    let name = url_path(url).rsplit('/').next().unwrap_or("").to_lowercase();
    name.split(|c: char| !c.is_ascii_alphanumeric())
        .any(|token| MEDIA_SITEMAP_TOKENS.contains(&token))
}

#[derive(Debug, Default, PartialEq)]
pub struct SubfileSelection {
    pub kept: Vec<String>,
    pub skipped_media: usize,
    pub skipped_locale: usize,
    /// The locale the selection settled on (None = single-locale tree).
    pub locale: Option<String>,
}

/// Choose which sub-sitemaps of one shop to walk.
///
/// Media files are always dropped. Files without a locale prefix are always
/// kept. For the rest one locale wins and the other locales' files are
/// dropped:
/// - `whole_tree` (the caller sees the shop's full index): `canonical` (the
///   pool's own URL prefix — a tie-breaker only, it may live in another
///   space when hreflang alternates were followed at ingest) when the index
///   has it, else `country_hint`, else the first locale in index order — and
///   only when the index carries two or more locales; a single-locale index
///   is never touched.
/// - a shard (3 files seen in isolation): `canonical` is the locale the
///   coordinator elected on the whole index and is authoritative — a shard
///   whose files all sit under another locale is skipped whole; without one
///   nothing is dropped, so a shard never elects a locale from its own files.
pub fn select_sitemap_subfiles(
    urls: &[String],
    canonical: Option<&str>,
    country_hint: Option<&str>,
    whole_tree: bool,
) -> SubfileSelection {
    let mut out = SubfileSelection::default();
    let mut candidates: Vec<(&String, Option<String>)> = Vec::with_capacity(urls.len());
    let mut locales: Vec<String> = Vec::new();
    for url in urls {
        if is_media_sitemap(url) {
            out.skipped_media += 1;
            continue;
        }
        let locale = url_locale_segment(url);
        if let Some(l) = &locale {
            if !locales.contains(l) {
                locales.push(l.clone());
            }
        }
        candidates.push((url, locale));
    }
    let canonical = canonical.map(|c| c.to_lowercase()).filter(|c| !c.is_empty());
    let chosen: Option<String> = if whole_tree {
        if locales.len() < 2 {
            None
        } else {
            let hint = country_hint.map(|c| c.to_lowercase());
            canonical
                .filter(|c| locales.contains(c))
                .or_else(|| hint.filter(|h| locales.contains(h)))
                .or_else(|| locales.first().cloned())
        }
    } else {
        canonical.filter(|c| locales.iter().any(|l| l != c))
    };
    for (url, locale) in candidates {
        match (&chosen, locale) {
            (Some(want), Some(have)) if &have != want => out.skipped_locale += 1,
            _ => out.kept.push(url.clone()),
        }
    }
    out.locale = chosen;
    out
}

/// The locale prefix shared by at least `min_share` of `urls` (a sample of
/// the shop's own pool) — the canonical locale for `select_sitemap_subfiles`.
pub fn dominant_locale(urls: &[String], min_share: f64) -> Option<String> {
    if urls.is_empty() {
        return None;
    }
    let mut counts: Vec<(String, usize)> = Vec::new();
    for url in urls {
        if let Some(locale) = url_locale_segment(url) {
            match counts.iter_mut().find(|(l, _)| *l == locale) {
                Some(entry) => entry.1 += 1,
                None => counts.push((locale, 1)),
            }
        }
    }
    counts
        .into_iter()
        .max_by_key(|(_, n)| *n)
        .filter(|(_, n)| (*n as f64) >= min_share * (urls.len() as f64))
        .map(|(l, _)| l)
}

#[cfg(test)]
pub fn alternates_map(entry: &UrlEntry) -> HashMap<String, String> {
    entry.alternates.iter().cloned().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_index_and_urlset_with_lastmod_and_alternates() {
        let idx = r#"<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://s.example/sitemap-1.xml</loc><lastmod>2026-09-01</lastmod></sitemap>
            <sitemap><loc>https://s.example/sitemap-2.xml</loc></sitemap></sitemapindex>"#;
        let parsed = parse_sitemap_xml(idx);
        assert_eq!(parsed.sitemaps, vec!["https://s.example/sitemap-1.xml", "https://s.example/sitemap-2.xml"]);
        assert!(parsed.entries.is_empty());

        let set = r#"<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
            <url><loc>https://s.example/p/1</loc><lastmod>2026-09-18T10:20:30+02:00</lastmod>
                 <xhtml:link rel="alternate" hreflang="LT" href="https://s.example/lt/p/1"/>
                 <xhtml:link rel="alternate" hreflang="x-default" href="https://s.example/p/1"></xhtml:link></url>
            <url><loc><![CDATA[https://s.example/p/2]]></loc></url>
            <url><lastmod>2026-01-01</lastmod></url></urlset>"#;
        let parsed = parse_sitemap_xml(set);
        assert_eq!(parsed.entries.len(), 2);
        assert_eq!(parsed.entries[0].loc, "https://s.example/p/1");
        assert_eq!(parsed.entries[0].lastmod.as_deref(), Some("2026-09-18T10:20:30+02:00"));
        assert_eq!(alternates_map(&parsed.entries[0]).get("lt").map(String::as_str), Some("https://s.example/lt/p/1"));
        assert_eq!(parsed.entries[1].loc, "https://s.example/p/2");
        assert!(parsed.entries[1].lastmod.is_none());
    }

    #[test]
    fn url_hash_matches_python_contract() {
        // sha256("https://s.example/p/1")
        assert_eq!(url_hash("  HTTPS://S.example/p/1/ "), url_hash("https://s.example/p/1"));
        assert_eq!(url_hash("https://s.example/p/1").len(), 64);
    }

    #[test]
    fn product_and_category_heuristics() {
        assert!(product_like_path("/baterii-ansmann-cr2016-1b-5020082"));
        assert!(product_like_path("/catalog/tv/samsung-qe55.html"));
        assert!(product_like_path("/p/12345"));
        assert!(!product_like_path("/catalog/tv"));
        assert!(category_like_url("https://shop.example/catalog/laptops"));
        assert!(category_like_url("https://shop.example/c/tv-audio/televizory"));
        assert!(!category_like_url("https://shop.example/catalog/laptops/lenovo-ideapad-3-1234567"));
        assert!(!category_like_url("https://shop.example/product/12345"));
        assert!(!category_like_url("https://shop.example/login"));
        assert!(!category_like_url("https://shop.example/c80196/strana-90098=675621/"));
        assert!(!category_like_url("https://shop.example/"));
        assert!(!category_like_url("https://shop.example/catalog/laptops?page=2"));
    }

    fn v(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn locale_segment_and_media_detection() {
        assert_eq!(url_locale_segment("https://pigu.lt/lt/sitemap-products-5.xml").as_deref(), Some("lt"));
        assert_eq!(url_locale_segment("https://pigu.lt/RU/x?y=1").as_deref(), Some("ru"));
        assert_eq!(url_locale_segment("https://s.example/en-US/p/1").as_deref(), Some("en-us"));
        assert_eq!(url_locale_segment("https://s.example/p/1"), None);
        assert_eq!(url_locale_segment("https://s.example/sitemap.xml"), None);
        assert_eq!(url_locale_segment("https://s.example"), None);
        assert!(is_media_sitemap("https://pigu.lt/ru/sitemap-products-images-405.xml"));
        assert!(is_media_sitemap("https://s.example/image_sitemap.xml"));
        assert!(is_media_sitemap("https://s.example/sitemaps/video-1.xml"));
        assert!(!is_media_sitemap("https://pigu.lt/lt/sitemap-products-5.xml"));
        assert!(!is_media_sitemap("https://s.example/sitemap-imagery.xml"));
    }

    #[test]
    fn subfile_selection_prefers_canonical_then_hint_then_first() {
        let files = v(&[
            "https://pigu.lt/lt/sitemap-products-1.xml",
            "https://pigu.lt/lt/sitemap-products-images-1.xml",
            "https://pigu.lt/ru/sitemap-products-1.xml",
            "https://pigu.lt/ru/sitemap-products-images-1.xml",
            "https://pigu.lt/sitemap-categories.xml",
        ]);
        let sel = select_sitemap_subfiles(&files, Some("lt"), None, true);
        assert_eq!(sel.kept, v(&["https://pigu.lt/lt/sitemap-products-1.xml", "https://pigu.lt/sitemap-categories.xml"]));
        assert_eq!((sel.skipped_media, sel.skipped_locale), (2, 1));
        assert_eq!(sel.locale.as_deref(), Some("lt"));

        // Whole tree, no pool yet: the country hint decides; else the first locale in index order.
        let sel = select_sitemap_subfiles(&files, None, Some("RU"), true);
        assert_eq!(sel.locale.as_deref(), Some("ru"));
        assert_eq!(sel.skipped_locale, 1);
        let sel = select_sitemap_subfiles(&files, None, Some("et"), true);
        assert_eq!(sel.locale.as_deref(), Some("lt"));
        // Whole tree: a canonical the index lacks falls through to the hint.
        let sel = select_sitemap_subfiles(&files, Some("en"), Some("ru"), true);
        assert_eq!(sel.locale.as_deref(), Some("ru"));
        // Single-locale whole trees are never touched, whatever the pool says.
        let single = v(&["https://s.example/lt/a.xml", "https://s.example/lt/b.xml"]);
        let sel = select_sitemap_subfiles(&single, Some("ru"), None, true);
        assert_eq!(sel.kept.len(), 2);
        assert_eq!(sel.locale, None);

        // A shard: the canonical is authoritative even against a single foreign locale...
        let ru_only = v(&["https://pigu.lt/ru/sitemap-products-7.xml", "https://pigu.lt/ru/sitemap-products-8.xml"]);
        let sel = select_sitemap_subfiles(&ru_only, Some("lt"), Some("lt"), false);
        assert!(sel.kept.is_empty());
        assert_eq!((sel.skipped_locale, sel.locale.as_deref()), (2, Some("lt")));
        // ...and its own locale passes untouched.
        let sel = select_sitemap_subfiles(&single, Some("lt"), None, false);
        assert_eq!(sel.kept.len(), 2);
        assert_eq!(sel.locale, None);
        // A shard with nothing to go on drops nothing for locale (hint alone is not enough).
        let sel = select_sitemap_subfiles(&files, None, Some("ru"), false);
        assert_eq!(sel.locale, None);
        assert_eq!(sel.kept.len(), 3);
    }

    #[test]
    fn dominant_locale_threshold() {
        let pool = v(&[
            "https://pigu.lt/lt/p/1", "https://pigu.lt/lt/p/2", "https://pigu.lt/lt/p/3",
            "https://pigu.lt/lt/p/4", "https://pigu.lt/ru/p/1",
        ]);
        assert_eq!(dominant_locale(&pool, 0.8).as_deref(), Some("lt"));
        assert_eq!(dominant_locale(&pool, 0.9), None);
        assert_eq!(dominant_locale(&v(&["https://s.example/p/1", "https://s.example/p/2"]), 0.8), None);
        assert_eq!(dominant_locale(&[], 0.8), None);
    }
}
