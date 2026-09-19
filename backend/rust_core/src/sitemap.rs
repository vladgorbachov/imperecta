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
}
