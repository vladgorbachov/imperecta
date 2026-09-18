//! JSON-LD product extraction.
//!
//! Semantic port of the JSON-LD strategy in
//! `backend/app/modules/scraper/extractors.py` (`extract_from_jsonld` and its
//! helper closure). Input is the raw text of every
//! `<script type="application/ld+json">` on the page (DOM handling stays in
//! Python); output mirrors `ExtractedProduct` fields this strategy fills.
//! Title fallback from the DOM (`_ensure_title`) remains on the Python side.

use serde::Serialize;
use serde_json::Value;

use crate::pricing::parse_price_text;

pub const MAX_TAXONOMY_SEGMENT_LEN: usize = 200;
pub const MAX_CATEGORY_DEPTH: usize = 6;
const MAX_RAW_PRICE_LEN: usize = 500;
const MAX_DESCRIPTION_LEN: usize = 2000;

#[derive(Debug, Default, Serialize, PartialEq)]
pub struct JsonLdProduct {
    pub title: Option<String>,
    pub price: Option<f64>,
    pub original_price: Option<f64>,
    pub currency: Option<String>,
    pub image_url: Option<String>,
    pub description: Option<String>,
    pub price_raw_text: Option<String>,
    pub currency_raw: Option<String>,
    pub brand: Option<String>,
    pub category_path: Option<Vec<String>>,
    /// Cross-shop identity (matching method 'gtin'): first valid gtin* key
    /// (8-14 digits after separator strip); mpn as manufacturer part number.
    pub gtin: Option<String>,
    pub mpn: Option<String>,
    /// True when at least one schema.org Product node was found.
    pub found: bool,
}

const GTIN_KEYS: [&str; 5] = ["gtin13", "gtin", "gtin14", "gtin12", "gtin8"];

fn gtin_from_product_node(product: &Value) -> Option<String> {
    for key in GTIN_KEYS {
        let raw = match product.get(key) {
            Some(Value::String(s)) => s.clone(),
            Some(Value::Number(n)) => n.to_string(),
            _ => continue,
        };
        let digits: String = raw
            .trim()
            .chars()
            .filter(|c| *c != ' ' && *c != '-')
            .collect();
        if !digits.is_empty()
            && digits.bytes().all(|b| b.is_ascii_digit())
            && (8..=14).contains(&digits.len())
        {
            return Some(digits);
        }
    }
    None
}

fn mpn_from_product_node(product: &Value) -> Option<String> {
    let raw = match product.get("mpn") {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Number(n)) => n.to_string(),
        _ => return None,
    };
    let value = raw.trim();
    if value.is_empty() {
        None
    } else {
        Some(truncate_chars(value, 100))
    }
}

fn truncate_chars(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        s.chars().take(max).collect()
    }
}

fn type_matches(node: &Value, wanted_lower: &str) -> bool {
    match node.get("@type") {
        Some(Value::Array(types)) => types
            .iter()
            .any(|t| value_as_display(t).to_lowercase() == wanted_lower),
        Some(other) => value_as_display(other).to_lowercase() == wanted_lower,
        None => false,
    }
}

/// Python's `str(x)` for the @type comparison tolerated non-strings.
fn value_as_display(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

fn find_product_nodes(item: &Value) -> Vec<&Value> {
    let mut nodes = Vec::new();
    if type_matches(item, "product") {
        nodes.push(item);
    }
    if let Some(Value::Array(graph)) = item.get("@graph") {
        for node in graph {
            if node.is_object() && type_matches(node, "product") {
                nodes.push(node);
            }
        }
    }
    nodes
}

fn brand_name_from_node(raw: Option<&Value>) -> Option<String> {
    let mut current = raw?;
    if let Value::Array(list) = current {
        current = list.first()?;
    }
    let current = if let Value::Object(obj) = current {
        obj.get("name")?
    } else {
        current
    };
    if let Value::String(s) = current {
        let name = s.trim();
        if !name.is_empty() {
            return Some(truncate_chars(name, MAX_TAXONOMY_SEGMENT_LEN));
        }
    }
    None
}

fn category_path_from_string(raw: Option<&Value>) -> Option<Vec<String>> {
    let text = match raw {
        Some(Value::String(s)) if !s.trim().is_empty() => s.trim().to_string(),
        _ => return None,
    };
    for sep in [">", "/", "»"] {
        if text.contains(sep) {
            let path: Vec<String> = text
                .split(sep)
                .map(|p| truncate_chars(p.trim(), MAX_TAXONOMY_SEGMENT_LEN))
                .filter(|p| !p.is_empty())
                .take(MAX_CATEGORY_DEPTH)
                .collect();
            return if path.is_empty() { None } else { Some(path) };
        }
    }
    Some(vec![truncate_chars(&text, MAX_TAXONOMY_SEGMENT_LEN)])
}

fn breadcrumb_nodes(item: &Value) -> Vec<&Value> {
    let mut nodes = Vec::new();
    if type_matches(item, "breadcrumblist") {
        nodes.push(item);
    }
    if let Some(Value::Array(graph)) = item.get("@graph") {
        nodes.extend(
            graph
                .iter()
                .filter(|n| n.is_object() && type_matches(n, "breadcrumblist")),
        );
    }
    nodes
}

fn crumb_name_and_url(elem: &Value) -> (Option<String>, Option<String>) {
    let mut name = elem.get("name").and_then(Value::as_str).map(str::to_string);
    let mut url: Option<String> = None;
    match elem.get("item") {
        Some(Value::Object(item)) => {
            if name.is_none() {
                name = item.get("name").and_then(Value::as_str).map(str::to_string);
            }
            url = item
                .get("@id")
                .or_else(|| item.get("url"))
                .and_then(Value::as_str)
                .map(str::to_string);
        }
        Some(Value::String(s)) => url = Some(s.clone()),
        _ => {}
    }
    match name {
        Some(n) if !n.trim().is_empty() => {
            (Some(truncate_chars(n.trim(), MAX_TAXONOMY_SEGMENT_LEN)), url)
        }
        _ => (None, url),
    }
}

/// Path component of a URL is "" or "/" with no query -> site root (Home crumb).
fn url_is_site_root(url: &str) -> bool {
    // Minimal urlparse: scheme://host[/path][?query]
    let after_scheme = match url.find("://") {
        Some(idx) => &url[idx + 3..],
        None => url,
    };
    let (path_and_query, _) = match after_scheme.find('#') {
        Some(idx) => after_scheme.split_at(idx),
        None => (after_scheme, ""),
    };
    let (path_part, query) = match path_and_query.find('?') {
        Some(idx) => {
            let (p, q) = path_and_query.split_at(idx);
            (p, &q[1..])
        }
        None => (path_and_query, ""),
    };
    let path = match path_part.find('/') {
        Some(idx) => &path_part[idx..],
        None => "",
    };
    (path.is_empty() || path == "/") && query.is_empty()
}

fn category_path_from_breadcrumbs(
    breadcrumb: &Value,
    page_url: &str,
    product_title: Option<&str>,
) -> Option<Vec<String>> {
    let elements = match breadcrumb.get("itemListElement") {
        Some(Value::Array(list)) if !list.is_empty() => list,
        _ => return None,
    };
    let mut ordered: Vec<&Value> = elements.iter().filter(|e| e.is_object()).collect();
    ordered.sort_by_key(|e| {
        e.get("position")
            .map(|p| match p {
                Value::Number(n) => n.as_i64().unwrap_or(0),
                Value::String(s) => s.trim().parse::<i64>().unwrap_or(0),
                _ => 0,
            })
            .unwrap_or(0)
    });

    let page_norm = if page_url.is_empty() {
        None
    } else {
        Some(page_url.trim_end_matches('/'))
    };
    let title_norm = product_title.map(|t| t.trim().to_lowercase());

    let mut path: Vec<String> = Vec::new();
    let last_index = ordered.len().saturating_sub(1);
    for (index, elem) in ordered.iter().enumerate() {
        let (name, url) = crumb_name_and_url(elem);
        let name = match name {
            Some(n) => n,
            None => continue,
        };
        if let Some(u) = url.as_deref() {
            if url_is_site_root(u) {
                continue;
            }
            if let Some(pn) = page_norm {
                if u.trim_end_matches('/') == pn {
                    continue;
                }
            }
        }
        let is_last = index == last_index;
        if is_last {
            if let Some(tn) = &title_norm {
                if name.trim().to_lowercase() == *tn {
                    continue;
                }
            }
        }
        path.push(name);
    }
    path.truncate(MAX_CATEGORY_DEPTH);
    if path.is_empty() {
        None
    } else {
        Some(path)
    }
}

/// Python's `str(offers.get("price"))` — numbers render plainly, strings as-is.
fn price_value_to_raw(v: &Value) -> String {
    let rendered = match v {
        Value::String(s) => s.clone(),
        Value::Number(n) => n.to_string(),
        Value::Null => "None".to_string(),
        Value::Bool(b) => if *b { "True" } else { "False" }.to_string(),
        other => other.to_string(),
    };
    truncate_chars(&rendered, MAX_RAW_PRICE_LEN)
}

/// Extract the first schema.org Product from the given JSON-LD script bodies.
pub fn extract_from_jsonld_scripts(scripts: &[String], page_url: &str) -> JsonLdProduct {
    let mut parsed_docs: Vec<Value> = Vec::new();
    for script in scripts {
        let body = if script.trim().is_empty() { "{}" } else { script };
        let parsed: Value = match serde_json::from_str(body) {
            Ok(v) => v,
            Err(_) => continue,
        };
        match parsed {
            Value::Array(items) => {
                parsed_docs.extend(items.into_iter().filter(|i| i.is_object()))
            }
            item if item.is_object() => parsed_docs.push(item),
            _ => {}
        }
    }

    for item in &parsed_docs {
        for product in find_product_nodes(item) {
            let offers_value = product.get("offers");
            let offers: &Value = match offers_value {
                Some(Value::Array(list)) => list.first().unwrap_or(&Value::Null),
                Some(v) => v,
                None => &Value::Null,
            };
            let offers = if offers.is_object() { offers } else { &Value::Null };

            let mut price = None;
            let mut original_price = None;
            let mut raw_price: Option<String> = None;
            if let Some(obj) = offers.as_object() {
                if let Some(p) = obj.get("price") {
                    let raw = price_value_to_raw(p);
                    price = parse_price_text(&raw);
                    raw_price = Some(raw);
                } else if let Some(p) = obj.get("lowPrice") {
                    let raw = price_value_to_raw(p);
                    price = parse_price_text(&raw);
                    raw_price = Some(raw);
                    if let Some(hp) = obj.get("highPrice") {
                        original_price = parse_price_text(&price_value_to_raw(hp));
                    }
                } else if let Some(p) = obj.get("highPrice") {
                    let raw = price_value_to_raw(p);
                    price = parse_price_text(&raw);
                    raw_price = Some(raw);
                }
            }

            let image = match product.get("image") {
                Some(Value::Array(list)) => list.first().cloned(),
                Some(Value::Object(map)) => map.get("url").cloned(),
                Some(v) => Some(v.clone()),
                None => None,
            };
            let image_url = match image {
                Some(Value::String(s)) => Some(s),
                _ => None,
            };

            let description = match product.get("description") {
                Some(Value::String(s)) => Some(truncate_chars(s, MAX_DESCRIPTION_LEN)),
                _ => None,
            };

            let (currency, currency_raw) = match offers
                .as_object()
                .and_then(|o| o.get("priceCurrency"))
            {
                Some(Value::String(s)) if !s.trim().is_empty() => {
                    let trimmed = s.trim();
                    (
                        Some(truncate_chars(&trimmed.to_uppercase(), 3)),
                        Some(truncate_chars(trimmed, 20)),
                    )
                }
                _ => (None, None),
            };

            let title = product
                .get("name")
                .and_then(Value::as_str)
                .map(str::to_string);

            let mut category_path = category_path_from_string(product.get("category"));
            if category_path.is_none() {
                'outer: for doc in &parsed_docs {
                    for breadcrumb in breadcrumb_nodes(doc) {
                        if let Some(path) = category_path_from_breadcrumbs(
                            breadcrumb,
                            page_url,
                            title.as_deref(),
                        ) {
                            category_path = Some(path);
                            break 'outer;
                        }
                    }
                }
            }

            return JsonLdProduct {
                title,
                price,
                original_price,
                currency,
                image_url,
                description,
                price_raw_text: raw_price,
                currency_raw,
                brand: brand_name_from_node(product.get("brand")),
                category_path,
                gtin: gtin_from_product_node(product),
                mpn: mpn_from_product_node(product),
                found: true,
            };
        }
    }
    JsonLdProduct::default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn product_with_offers_and_breadcrumbs() {
        let scripts = vec![
            r#"{"@context":"https://schema.org","@graph":[
                {"@type":"Product","name":"Widget X","brand":{"@type":"Brand","name":"Acme"},
                 "image":["https://shop.example/img/1.jpg"],
                 "offers":{"@type":"Offer","price":"1 299,50","priceCurrency":"eur"}},
                {"@type":"BreadcrumbList","itemListElement":[
                    {"@type":"ListItem","position":1,"name":"Home","item":"https://shop.example/"},
                    {"@type":"ListItem","position":2,"name":"Tools","item":"https://shop.example/tools"},
                    {"@type":"ListItem","position":3,"name":"Widget X","item":"https://shop.example/tools/widget-x"}
                ]}
            ]}"#
                .to_string(),
        ];
        let out = extract_from_jsonld_scripts(&scripts, "https://shop.example/tools/widget-x");
        assert!(out.found);
        assert_eq!(out.title.as_deref(), Some("Widget X"));
        assert_eq!(out.price, Some(1299.50));
        assert_eq!(out.currency.as_deref(), Some("EUR"));
        assert_eq!(out.currency_raw.as_deref(), Some("eur"));
        assert_eq!(out.brand.as_deref(), Some("Acme"));
        assert_eq!(out.category_path, Some(vec!["Tools".to_string()]));
        assert_eq!(out.image_url.as_deref(), Some("https://shop.example/img/1.jpg"));
    }

    #[test]
    fn no_product_yields_default() {
        let out = extract_from_jsonld_scripts(
            &[r#"{"@type":"WebSite","name":"x"}"#.to_string()],
            "",
        );
        assert!(!out.found);
        assert!(out.title.is_none());
    }

    #[test]
    fn aggregate_offer_low_high() {
        let scripts = vec![
            r#"{"@type":"Product","name":"Y","offers":{"@type":"AggregateOffer","lowPrice":100,"highPrice":150,"priceCurrency":"USD"}}"#.to_string(),
        ];
        let out = extract_from_jsonld_scripts(&scripts, "");
        assert_eq!(out.price, Some(100.0));
        assert_eq!(out.original_price, Some(150.0));
    }
}

#[cfg(test)]
mod gtin_tests {
    use super::*;

    #[test]
    fn gtin13_preferred_and_separators_stripped() {
        let scripts = vec![r#"{"@type":"Product","name":"Widget",
            "gtin13":"590-1234 123457","gtin8":"12345670",
            "offers":{"price":"9.99","priceCurrency":"EUR"}}"#
            .to_string()];
        let p = extract_from_jsonld_scripts(&scripts, "");
        assert_eq!(p.gtin.as_deref(), Some("5901234123457"));
    }

    #[test]
    fn invalid_gtin_rejected_mpn_kept() {
        let scripts = vec![r#"{"@type":"Product","name":"Widget",
            "gtin":"not-a-number","mpn":"BQ2942W",
            "offers":{"price":"9.99","priceCurrency":"EUR"}}"#
            .to_string()];
        let p = extract_from_jsonld_scripts(&scripts, "");
        assert_eq!(p.gtin, None);
        assert_eq!(p.mpn.as_deref(), Some("BQ2942W"));
    }

    #[test]
    fn numeric_gtin_value_accepted() {
        let scripts = vec![r#"{"@type":"Product","name":"Widget",
            "gtin":4006381333931,
            "offers":{"price":"9.99","priceCurrency":"EUR"}}"#
            .to_string()];
        let p = extract_from_jsonld_scripts(&scripts, "");
        assert_eq!(p.gtin.as_deref(), Some("4006381333931"));
    }
}
