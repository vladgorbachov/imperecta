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
    /// Card thumbnail (src / data-src / first srcset URL), absolutized.
    /// Mass image fill for sitemap-onboarded products whose PDP was never
    /// scraped — 99.9% of the pool had no image before this.
    pub image_url: Option<String>,
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

/// A class token carrying a digit run is an instance id, not structure
/// ("product-block-267212686" on every pigu card, 2026-09-19): with it in
/// the signature no two cards ever match and the grid is never found.
fn is_instance_class(class: &str) -> bool {
    let mut run = 0;
    for ch in class.chars() {
        if ch.is_ascii_digit() {
            run += 1;
            if run >= 3 {
                return true;
            }
        } else {
            run = 0;
        }
    }
    false
}

fn signature_of(el: &ElementRef) -> Option<(String, Vec<String>)> {
    let tag = el.value().name().to_lowercase();
    let mut classes: Vec<String> = el
        .value()
        .classes()
        .filter(|c| !is_instance_class(c))
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

/// Card price = first currency-anchored text run that parses as a price.
///
/// Parsing the whole card text is unsafe: digit runs in product titles
/// ("E1504FA-BQ2942W") read as prices (live incident 2026-09-17, datacomp).
/// A price on a list card always sits next to a currency marker, so only
/// text nodes carrying one — alone or joined with the previous node, for
/// markup that splits amount and symbol — are price candidates.
/// Trailing (or leading) run of purely numeric tokens — "1 299,00" survives
/// as a whole, while a title's "…BQ2942W" contributes nothing.
fn numeric_edge_tokens(text: &str, from_end: bool) -> String {
    fn is_numeric(t: &str) -> bool {
        !t.is_empty() && t.chars().all(|c| c.is_ascii_digit() || c == '.' || c == ',')
    }
    let tokens: Vec<&str> = text.split_whitespace().collect();
    let run: Vec<&str> = if from_end {
        let mut r: Vec<&str> = tokens
            .iter()
            .rev()
            .take_while(|t| is_numeric(t))
            .take(4)
            .copied()
            .collect();
        r.reverse();
        r
    } else {
        tokens
            .iter()
            .take_while(|t| is_numeric(t))
            .take(4)
            .copied()
            .collect()
    };
    run.join(" ")
}

/// Class-token hints for prices that are NOT the offer: struck-through
/// previous prices and member-only (loyalty club) prices. Structural in
/// spirit — they name price roles, never shops.
const OLD_PRICE_HINTS: [&str; 7] = ["old", "before", "strike", "cross", "was", "previous", "prev"];
const MEMBER_PRICE_HINTS: [&str; 3] = ["loyal", "member", "club"];

fn class_has_hint(el: &ElementRef, hints: &[&str]) -> bool {
    el.value()
        .attr("class")
        .map(|c| {
            let lower = c.to_ascii_lowercase();
            hints.iter().any(|h| lower.contains(h))
        })
        .unwrap_or(false)
}

/// True when the element or an ancestor inside the card is struck through
/// (<s>/<del>/<strike>) or carries an old-price class hint.
fn is_old_price(el: &ElementRef, card: &ElementRef) -> bool {
    let mut node = Some(*el);
    while let Some(cur) = node {
        if cur.id() == card.id() {
            break;
        }
        let name = cur.value().name();
        if name == "s" || name == "del" || name == "strike" || class_has_hint(&cur, &OLD_PRICE_HINTS) {
            return true;
        }
        node = cur.parent().and_then(ElementRef::wrap);
    }
    false
}

/// Attribute-carried prices: aria-label="299,99 €", data-price, or
/// itemprop=price content paired with priceCurrency. Markup like
/// `299<sup>99</sup> €` (pigu group, 2026-09-19) defeats text-node
/// parsing — the text nodes read "299" "99" "€" — while the attribute
/// carries the exact amount. The first non-old, non-member candidate in
/// DOM order wins; a member-only price is the fallback.
fn attribute_price(card: &ElementRef) -> Option<(f64, &'static str, String)> {
    let sel = Selector::parse("[aria-label], [data-price], [itemprop=\"price\"]").ok()?;
    let cur_sel = Selector::parse("[itemprop=\"priceCurrency\"]").ok()?;
    let card_currency: Option<&str> = card
        .select(&cur_sel)
        .find_map(|el| el.value().attr("content"))
        .map(str::trim)
        .filter(|c| !c.is_empty());
    let mut member_fallback: Option<(f64, &'static str, String)> = None;
    for el in card.select(&sel) {
        let attrs = el.value();
        let mut text: Option<String> = None;
        if let Some(label) = attrs.attr("aria-label") {
            if detect_currency(label).is_some() {
                text = Some(label.to_string());
            }
        }
        if text.is_none() {
            if let Some(dp) = attrs.attr("data-price") {
                if detect_currency(dp).is_some() {
                    text = Some(dp.to_string());
                } else if let Some(cur) = card_currency {
                    text = Some(format!("{dp} {cur}"));
                }
            }
        }
        if text.is_none() {
            if attrs.attr("itemprop") == Some("price") {
                if let (Some(content), Some(cur)) = (attrs.attr("content"), card_currency) {
                    text = Some(format!("{content} {cur}"));
                }
            }
        }
        let Some(text) = text else { continue };
        if is_old_price(&el, card) {
            continue;
        }
        let parsed = match (parse_price_text(&text), detect_currency(&text)) {
            (Some(price), Some(currency)) => {
                let mut raw = text.clone();
                if raw.chars().count() > MAX_RAW_PRICE_LEN {
                    raw = raw.chars().take(MAX_RAW_PRICE_LEN).collect();
                }
                (price, currency, raw)
            }
            _ => continue,
        };
        if class_has_hint(&el, &MEMBER_PRICE_HINTS) {
            member_fallback.get_or_insert(parsed);
            continue;
        }
        return Some(parsed);
    }
    member_fallback
}

fn card_price(card: &ElementRef) -> Option<(f64, &'static str, String)> {
    if let Some(found) = attribute_price(card) {
        return Some(found);
    }
    const MAX_PRICE_NODES: usize = 200;
    let nodes: Vec<&str> = card
        .text()
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .take(MAX_PRICE_NODES)
        .collect();
    for (idx, node) in nodes.iter().enumerate() {
        if detect_currency(node).is_none() {
            continue;
        }
        // Amount and marker in one node, or split across the neighbour
        // node on either side ("355,00" + "€", "€" + "355,00"). Only the
        // adjacent TOKEN of the neighbour joins — a full neighbour node can
        // be a title whose SKU digits would parse as a price.
        let mut candidates: Vec<String> = vec![(*node).to_string()];
        // Superscript cents: "299" "99" "€" — the two-digit node right
        // before the marker is the fraction of the node before it.
        if idx > 1 {
            let cents = nodes[idx - 1];
            let whole = numeric_edge_tokens(nodes[idx - 2], true);
            if cents.len() == 2
                && cents.chars().all(|c| c.is_ascii_digit())
                && !whole.is_empty()
                && !whole.contains(',')
                && !whole.contains('.')
            {
                candidates.push(format!("{whole},{cents} {node}"));
            }
        }
        if idx > 0 {
            let tail = numeric_edge_tokens(nodes[idx - 1], true);
            if !tail.is_empty() {
                candidates.push(format!("{tail} {node}"));
            }
        }
        if idx + 1 < nodes.len() {
            let head = numeric_edge_tokens(nodes[idx + 1], false);
            if !head.is_empty() {
                candidates.push(format!("{node} {head}"));
            }
        }
        for candidate in candidates {
            if let (Some(price), Some(currency)) =
                (parse_price_text(&candidate), detect_currency(&candidate))
            {
                let mut raw = candidate;
                if raw.chars().count() > MAX_RAW_PRICE_LEN {
                    raw = raw.chars().take(MAX_RAW_PRICE_LEN).collect();
                }
                return Some((price, currency, raw));
            }
        }
    }
    None
}

/// Card thumbnail: first <img> with a usable source. Lazy-loaded grids put
/// the real URL in data-src/data-lazy-src/data-original or srcset while src
/// holds a placeholder — prefer the data-* attributes.
fn card_image(card: &ElementRef, base_url: &str) -> Option<String> {
    let img_sel = Selector::parse("img").unwrap();
    for img in card.select(&img_sel) {
        let v = img.value();
        let mut candidate: Option<&str> = None;
        for attr in ["data-src", "data-lazy-src", "data-original", "src"] {
            if let Some(raw) = v.attr(attr) {
                let raw = raw.trim();
                if !raw.is_empty() && !raw.starts_with("data:") {
                    candidate = Some(raw);
                    break;
                }
            }
        }
        if candidate.is_none() {
            if let Some(srcset) = v.attr("srcset") {
                let first = srcset
                    .split(',')
                    .next()
                    .map(|e| e.trim().split_whitespace().next().unwrap_or(""))
                    .unwrap_or("");
                if !first.is_empty() && !first.starts_with("data:") {
                    candidate = Some(first);
                }
            }
        }
        if let Some(raw) = candidate {
            if let Some(full) = join_url(base_url, raw) {
                return Some(full);
            }
        }
    }
    None
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

    // 2. Primary signature: among repeated link-bearing signatures, prefer
    //    the one whose cards carry currency-anchored prices — a product grid
    //    has prices, a mega-menu (often the most-repeated structure on the
    //    page, e.g. techmart.bg's ~245 nav links) does not. Fall back to the
    //    most-repeated link signature when nothing on the page is priced.
    let link_sel = Selector::parse("a[href]").unwrap();
    let mut best_priced: Option<(usize, Vec<ElementRef>)> = None;
    let mut best_any: Option<(usize, Vec<ElementRef>)> = None;
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
        let priced = elements
            .iter()
            .filter(|el| card_price(el).is_some())
            .count();
        if priced >= MIN_CARD_COUNT
            && best_priced.as_ref().map_or(true, |(s, _)| priced > *s)
        {
            best_priced = Some((priced, elements.clone()));
        }
        let score = elements.len();
        if best_any.as_ref().map_or(true, |(s, _)| score > *s) {
            best_any = Some((score, elements));
        }
    }
    let cards = match best_priced.or(best_any) {
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

        let (price, currency, price_raw_text) = match card_price(&card) {
            Some((p, cur, raw)) => (Some(p), Some(cur.to_string()), Some(raw)),
            None => (None, None, None),
        };

        offers.push(ListOffer {
            url,
            title,
            price,
            currency,
            price_raw_text,
            image_url: card_image(&card, base_url),
        });
    }
    offers
}

#[cfg(test)]
mod image_tests {
    use super::*;

    #[test]
    fn card_image_prefers_lazy_data_src_and_absolutizes() {
        let mut items = String::new();
        for i in 0..6 {
            items.push_str(&format!(
                r#"<div class="card">
                     <a href="/p/w-{i}"><span>Widget model {i}</span></a>
                     <img src="data:image/gif;base64,R0lGOD" data-src="/img/w-{i}.jpg"/>
                     <span class="price">19,99 €</span>
                   </div>"#
            ));
        }
        let html = format!("<html><body><div id=g>{items}</div></body></html>");
        let offers = extract_list_offers(&html, "https://shop.example/cat");
        assert!(!offers.is_empty());
        assert_eq!(
            offers[0].image_url.as_deref(),
            Some("https://shop.example/img/w-0.jpg")
        );
    }

    #[test]
    fn card_image_srcset_fallback() {
        let mut items = String::new();
        for i in 0..6 {
            items.push_str(&format!(
                r#"<div class="card">
                     <a href="/p/w-{i}"><span>Widget model {i}</span></a>
                     <img srcset="https://cdn.example/w-{i}-small.jpg 1x, https://cdn.example/w-{i}.jpg 2x"/>
                     <span class="price">19,99 €</span>
                   </div>"#
            ));
        }
        let html = format!("<html><body><div id=g>{items}</div></body></html>");
        let offers = extract_list_offers(&html, "https://shop.example/cat");
        assert_eq!(
            offers[0].image_url.as_deref(),
            Some("https://cdn.example/w-0-small.jpg")
        );
    }
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

    /// pigu-group markup (2026-09-19): superscript cents, a member-only
    /// loyalty price first, the public price second, both aria-labelled.
    fn pigu_grid(cards: usize) -> String {
        let mut items = String::new();
        for i in 0..cards {
            items.push_str(&format!(
                r#"<div class="c-product-card product-block-26721268{i}">
                     <a href="/lt/kompiuteriai/nesiojamas-{i}?id=24224{i}"><span>Nešiojamas kompiuteris {i}</span></a>
                     <div class="c-product-card__prices">
                       <span class="c-price h-price--loyalty" aria-label="299,99 €"><i class="c-icon--loyalty"></i> 299<sup>99</sup> <small>€</small></span>
                       <span class="c-price h-price--medium" aria-label="329,99 €">329<sup>99</sup> <small>€</small></span>
                       <span class="c-price c-price--old" aria-label="399,99 €"><s>399<sup>99</sup> €</s></span>
                     </div>
                   </div>"#
            ));
        }
        format!(r#"<html><body><div class="grid">{items}</div></body></html>"#)
    }

    #[test]
    fn attribute_price_prefers_public_over_member_and_old() {
        let offers = extract_list_offers(&pigu_grid(8), "https://pigu.lt/lt/kompiuteriai");
        assert_eq!(offers.len(), 8);
        assert_eq!(offers[0].price, Some(329.99));
        assert_eq!(offers[0].currency.as_deref(), Some("EUR"));
    }

    #[test]
    fn instance_id_classes_do_not_break_the_grid_signature() {
        assert!(is_instance_class("product-block-267212686"));
        assert!(is_instance_class("item-123"));
        assert!(!is_instance_class("c-product-card"));
        assert!(!is_instance_class("col-12")); // two digits: a grid span, kept
    }

    #[test]
    fn superscript_cents_join_in_text_path() {
        let html = r#"<html><body><div class="grid">
          <div class="card"><a href="/p/a1">A1 model</a><span>299<sup>99</sup> <small>€</small></span></div>
          <div class="card"><a href="/p/a2">A2 model</a><span>19<sup>50</sup> <small>€</small></span></div>
          <div class="card"><a href="/p/a3">A3 model</a><span>1 299<sup>00</sup> <small>€</small></span></div>
          <div class="card"><a href="/p/a4">A4 model</a><span>5<sup>00</sup> <small>€</small></span></div>
          <div class="card"><a href="/p/a5">A5 model</a><span>7<sup>25</sup> <small>€</small></span></div>
          <div class="card"><a href="/p/a6">A6 model</a><span>8<sup>10</sup> <small>€</small></span></div>
        </div></body></html>"#;
        let offers = extract_list_offers(html, "https://shop.example/c");
        assert_eq!(offers.len(), 6);
        assert_eq!(offers[0].price, Some(299.99));
        assert_eq!(offers[1].price, Some(19.50));
        assert_eq!(offers[2].price, Some(1299.00));
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
    fn priced_grid_beats_bigger_unpriced_menu() {
        // Live incident 2026-09-17 (techmart.bg): a ~245-link mega-menu
        // out-repeated the 24-card product grid, so every "offer" was a
        // category link and none matched the pool.
        let mut menu = String::new();
        for i in 0..40 {
            menu.push_str(&format!(
                r#"<li class="nav-item"><a href="/category-{i}">Category {i}</a></li>"#
            ));
        }
        let mut grid = String::new();
        for i in 0..8 {
            grid.push_str(&format!(
                r#"<div class="product-card">
                     <a href="/p/tv-{i}">TV Model {i}</a>
                     <span class="price">499,00 €</span>
                   </div>"#
            ));
        }
        let html = format!(
            r#"<html><body><ul class="menu">{menu}</ul><div class="grid">{grid}</div></body></html>"#
        );
        let offers = extract_list_offers(&html, "https://shop.example/c/tv");
        assert_eq!(offers.len(), 8);
        assert!(offers.iter().all(|o| o.url.contains("/p/tv-")));
        assert!(offers.iter().all(|o| o.price == Some(499.00)));
    }

    #[test]
    fn sku_digits_in_title_never_become_the_price() {
        // Live incident 2026-09-17: datacomp card "ASUS … E1504FA-BQ2942W"
        // ingested price 2942.00 EUR (real price 355,00 €).
        let mut items = String::new();
        for i in 0..6 {
            items.push_str(&format!(
                r#"<div class="product-card">
                     <a href="/p/laptop-{i}">ASUS Vivobook Go 15 E1504FA-BQ2942W čierny</a>
                     <span class="price">355,00 €</span>
                   </div>"#
            ));
        }
        let html = format!(r#"<html><body><div class="grid">{items}</div></body></html>"#);
        let offers = extract_list_offers(&html, "https://shop.example/c/laptops");
        assert_eq!(offers.len(), 6);
        assert_eq!(offers[0].price, Some(355.00));
        assert_eq!(offers[0].currency.as_deref(), Some("EUR"));
    }

    #[test]
    fn split_amount_and_symbol_nodes_join() {
        let mut items = String::new();
        for i in 0..6 {
            items.push_str(&format!(
                r#"<div class="product-card">
                     <a href="/p/tv-{i}">TV Model X{i}000</a>
                     <span class="amount">1 299,00</span><span class="cur">€</span>
                   </div>"#
            ));
        }
        let html = format!(r#"<html><body><div class="grid">{items}</div></body></html>"#);
        let offers = extract_list_offers(&html, "https://shop.example/c/tv");
        assert_eq!(offers[0].price, Some(1299.00));
        assert_eq!(offers[0].currency.as_deref(), Some("EUR"));
    }

    #[test]
    fn no_currency_marker_means_no_price() {
        // Facet/filter cards ("17,3\" a viac") must not fabricate prices.
        let mut items = String::new();
        for i in 0..6 {
            items.push_str(&format!(
                r#"<div class="product-card">
                     <a href="/f/size-{i}">17,{i}" a viac</a>
                   </div>"#
            ));
        }
        let html = format!(r#"<html><body><div class="grid">{items}</div></body></html>"#);
        let offers = extract_list_offers(&html, "https://shop.example/c/x");
        assert!(offers.iter().all(|o| o.price.is_none() && o.currency.is_none()));
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

