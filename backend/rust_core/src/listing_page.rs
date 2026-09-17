//! List-page offer extraction — the economic backbone of price monitoring.
//!
//! SITEMAP_FIRST_PLAN slice 2. One category/list page carries prices for
//! 20-60 products; extracting (url, price) pairs from it replaces that many
//! card fetches. The card-detection algorithm is the semantic port of
//! `extractors.extract_links_from_repeated_structure`: elements whose
//! structural signature (tag + CSS class set) repeats >= MIN_CARD_COUNT
//! times form the product grid — fully language-agnostic. Per card we
//! additionally extract the dominant link (product URL), a title guess and
//! the card's price via the `pricing` module.

use std::collections::HashMap;

use scraper::{ElementRef, Html, Selector};
use serde::Serialize;

use crate::pricing::{detect_currency, parse_price_text};

pub const MIN_CARD_COUNT: usize = 6;
const MAX_TITLE_LEN: usize = 500;
const MAX_RAW_PRICE_LEN: usize = 200;

const EXCLUDED_PATH_PREFIXES: &[&str] = &[
    "/cart",
    "/checkout",
    "/login",
    "/auth",
    "/account",
    "/wishlist",
    "/compare",
    "/sitemap",
    "/robots",
];

#[derive(Debug, Serialize, PartialEq)]
pub struct ListOffer {
    pub url: String,
    pub title: Option<String>,
    pub price: Option<f64>,
    pub currency: Option<String>,
    pub price_raw_text: Option<String>,
}

/// Minimal absolute-URL resolution (enough for href joining; no dot-segment
/// normalization beyond what shops emit in practice).
fn join_url(base: &str, href: &str) -> Option<String> {
    let href = href.trim();
    if href.is_empty() {
        return None;
    }
    if href.starts_with("http://") || href.starts_with("https://") {
        return Some(href.to_string());
    }
    let (scheme, rest) = base.split_once("://")?;
    let (host, _path) = match rest.split_once('/') {
        Some((h, p)) => (h, p),
        None => (rest, ""),
    };
    if let Some(proto_rel) = href.strip_prefix("//") {
        return Some(format!("{scheme}://{proto_rel}"));
    }
    if href.starts_with('/') {
        return Some(format!("{scheme}://{host}{href}"));
    }
    if href.starts_with('#') || href.starts_with("javascript:")
        || href.starts_with("mailto:") || href.starts_with("tel:")
    {
        return None;
    }
    // Relative path: resolve against the base directory.
    let base_dir = base.rsplit_once('/').map(|(d, _)| d).unwrap_or(base);
    Some(format!("{base_dir}/{href}"))
}

fn host_of(url: &str) -> Option<&str> {
    let rest = url.split_once("://")?.1;
    Some(rest.split('/').next().unwrap_or(rest))
}

fn path_of(url: &str) -> &str {
    url.split_once("://")
        .and_then(|(_, rest)| rest.split_once('/').map(|(_, p)| p))
        .map(|p| &url[url.len() - p.len() - 1..])
        .unwrap_or("/")
}

fn strip_query_fragment(url: &str) -> String {
    let no_frag = url.split('#').next().unwrap_or(url);
    no_frag.split('?').next().unwrap_or(no_frag).to_string()
}

fn signature_of(el: &ElementRef) -> Option<(String, Vec<String>)> {
    let tag = el.value().name().to_lowercase();
    let mut classes: Vec<String> = el
        .value()
        .classes()
        .map(|c| c.to_string())
        .collect();
    if tag.is_empty() || classes.is_empty() {
        return None;
    }
    classes.sort();
    Some((tag, classes))
}

fn compact_text(el: &ElementRef, cap: usize) -> String {
    let mut out = String::new();
    for chunk in el.text() {
        let trimmed = chunk.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !out.is_empty() {
            out.push(' ');
        }
        out.push_str(trimmed);
        if out.chars().count() > cap {
            break;
        }
    }
    if out.chars().count() > cap {
        out = out.chars().take(cap).collect();
    }
    out
}

/// Extract (product_url, price, title) offers from a category/list page.
pub fn extract_list_offers(html: &str, base_url: &str) -> Vec<ListOffer> {
    let document = Html::parse_document(html);
    let base_host = match host_of(base_url) {
        Some(h) => h.trim_start_matches("www.").to_string(),
        None => return Vec::new(),
    };

    // 1. Group elements by structural signature.
    let all_sel = Selector::parse("*").unwrap();
    let mut by_signature: HashMap<(String, Vec<String>), Vec<ElementRef>> = HashMap::new();
    for el in document.select(&all_sel) {
        if let Some(sig) = signature_of(&el) {
            by_signature.entry(sig).or_default().push(el);
        }
    }

    // 2. Primary signature = the most-repeated one above the grid threshold,
    //    preferring signatures whose cards contain links.
    let link_sel = Selector::parse("a[href]").unwrap();
    let mut best: Option<(usize, Vec<ElementRef>)> = None;
    for (_sig, elements) in by_signature.into_iter() {
        if elements.len() < MIN_CARD_COUNT {
            continue;
        }
        let with_links = elements
            .iter()
            .filter(|el| el.select(&link_sel).next().is_some())
            .count();
        if with_links < MIN_CARD_COUNT {
            continue;
        }
        let score = elements.len();
        if best.as_ref().map_or(true, |(s, _)| score > *s) {
            best = Some((score, elements));
        }
    }
    let cards = match best {
        Some((_, cards)) => cards,
        None => return Vec::new(),
    };

    // 3. Per card: dominant link + price from card text.
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut offers = Vec::new();
    for card in cards {
        let mut product_url: Option<String> = None;
        let mut title: Option<String> = None;
        for link in card.select(&link_sel) {
            let href = link.value().attr("href").unwrap_or("");
            let Some(full) = join_url(base_url, href) else {
                continue;
            };
            let Some(host) = host_of(&full) else { continue };
            if host.trim_start_matches("www.") != base_host {
                continue;
            }
            let clean = strip_query_fragment(&full);
            let path = path_of(&clean).to_lowercase();
            if EXCLUDED_PATH_PREFIXES.iter().any(|p| path.starts_with(p)) {
                continue;
            }
            if clean == base_url || path == "/" {
                continue;
            }
            let link_text = compact_text(&link, MAX_TITLE_LEN);
            if product_url.is_none() {
                product_url = Some(clean.clone());
            }
            // The longest link text inside the card is the best title guess.
            if !link_text.is_empty()
                && title.as_ref().map_or(true, |t: &String| {
                    link_text.chars().count() > t.chars().count()
                })
            {
                title = Some(link_text);
            }
        }
        let Some(url) = product_url else { continue };
        if !seen.insert(url.clone()) {
            continue;
        }

        let card_text = compact_text(&card, MAX_RAW_PRICE_LEN * 4);
        let price = parse_price_text(&card_text);
        let currency = price
            .and_then(|_| detect_currency(&card_text))
            .map(str::to_string);
        let price_raw_text = if price.is_some() {
            let mut raw = card_text;
            if raw.chars().count() > MAX_RAW_PRICE_LEN {
                raw = raw.chars().take(MAX_RAW_PRICE_LEN).collect();
            }
            Some(raw)
        } else {
            None
        };

        offers.push(ListOffer {
            url,
            title,
            price,
            currency,
            price_raw_text,
        });
    }
    offers
}

#[cfg(test)]
mod tests {
    use super::*;

    fn grid_html(cards: usize) -> String {
        let mut items = String::new();
        for i in 0..cards {
            items.push_str(&format!(
                r#"<div class="product-card">
                     <a href="/p/widget-{i}"><span>Widget model {i}</span></a>
                     <span class="price">1 299,{i:02} €</span>
                   </div>"#
            ));
        }
        format!(
            r#"<html><body>
                 <nav class="menu"><a href="/cart">Cart</a></nav>
                 <div class="grid">{items}</div>
               </body></html>"#
        )
    }

    #[test]
    fn extracts_offer_per_card_with_price_and_currency() {
        let offers = extract_list_offers(&grid_html(8), "https://shop.example/c/tools");
        assert_eq!(offers.len(), 8);
        let first = &offers[0];
        assert_eq!(first.url, "https://shop.example/p/widget-0");
        assert_eq!(first.price, Some(1299.00));
        assert_eq!(first.currency.as_deref(), Some("EUR"));
        assert_eq!(first.title.as_deref(), Some("Widget model 0"));
    }

    #[test]
    fn below_grid_threshold_yields_nothing() {
        let offers = extract_list_offers(&grid_html(4), "https://shop.example/c/tools");
        assert!(offers.is_empty());
    }

    #[test]
    fn excluded_and_foreign_links_ignored() {
        let mut html = grid_html(6);
        html = html.replace(
            r#"<a href="/p/widget-0">"#,
            r#"<a href="https://evil.example/p/x"></a><a href="/cart/add"></a><a href="/p/widget-0">"#,
        );
        let offers = extract_list_offers(&html, "https://shop.example/c/tools");
        assert_eq!(offers.len(), 6);
        assert!(offers.iter().all(|o| o.url.starts_with("https://shop.example/p/")));
    }

    #[test]
    fn card_without_price_still_yields_url() {
        let html = grid_html(6).replace(r#"<span class="price">1 299,00 €</span>"#, "");
        let offers = extract_list_offers(&html, "https://shop.example/c/tools");
        let first = &offers[0];
        assert_eq!(first.price, None);
        assert!(first.price_raw_text.is_none());
    }
}
