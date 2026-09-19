//! `imperecta_core` — Python extension module (PyO3).
//!
//! Exposes the Rust extraction core to the backend:
//!   * pricing:  parse_price_text / parse_currency_symbol / parse_currency_code
//!               / detect_currency / currency_token_is_ambiguous
//!   * jsonld:   extract_jsonld(scripts, page_url) -> dict
//!   * quality:  assess_quality(record: dict) -> dict
//!
//! The Python facade (`app.common.rust_core`) selects the engine via the
//! EXTRACTOR_ENGINE env var and falls back to the pure-Python reference
//! implementation when this module is not built.

mod jsonld;
mod listing_page;
mod matching;
mod pricing;
mod quality;
mod sitemap;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

#[pyfunction]
fn parse_price_text(text: &str) -> Option<f64> {
    pricing::parse_price_text(text)
}

#[pyfunction]
fn parse_currency_symbol(text: &str) -> Option<&'static str> {
    pricing::parse_currency_symbol(text)
}

#[pyfunction]
fn parse_currency_code(text: &str) -> Option<&'static str> {
    pricing::parse_currency_code(text)
}

#[pyfunction]
fn detect_currency(text: &str) -> Option<&'static str> {
    pricing::detect_currency(text)
}

#[pyfunction]
#[pyo3(signature = (raw_text=None))]
fn currency_token_is_ambiguous(raw_text: Option<&str>) -> bool {
    pricing::currency_token_is_ambiguous(raw_text)
}

#[pyfunction]
#[pyo3(signature = (scripts, page_url=""))]
fn extract_jsonld<'py>(
    py: Python<'py>,
    scripts: Vec<String>,
    page_url: &str,
) -> PyResult<Bound<'py, PyDict>> {
    let product = jsonld::extract_from_jsonld_scripts(&scripts, page_url);
    let out = PyDict::new(py);
    out.set_item("title", product.title)?;
    out.set_item("price", product.price)?;
    out.set_item("original_price", product.original_price)?;
    out.set_item("currency", product.currency)?;
    out.set_item("image_url", product.image_url)?;
    out.set_item("description", product.description)?;
    out.set_item("price_raw_text", product.price_raw_text)?;
    out.set_item("currency_raw", product.currency_raw)?;
    out.set_item("brand", product.brand)?;
    out.set_item("category_path", product.category_path)?;
    out.set_item("gtin", product.gtin)?;
    out.set_item("mpn", product.mpn)?;
    out.set_item("found", product.found)?;
    Ok(out)
}

fn get_opt_string(record: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    match record.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<String>()?)),
        _ => Ok(None),
    }
}

fn get_opt_f64(record: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f64>> {
    match record.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<f64>()?)),
        _ => Ok(None),
    }
}

/// Assess the quality of one scraped product record.
///
/// `record` keys (all optional): title, price, original_price, currency,
/// currency_raw, image_url, url, description, brand,
/// category_path (list[str]), allowed_currencies (list[str]).
#[pyfunction]
fn assess_quality<'py>(
    py: Python<'py>,
    record: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyDict>> {
    let category_path: Option<Vec<String>> = match record.get_item("category_path")? {
        Some(v) if !v.is_none() => Some(v.extract()?),
        _ => None,
    };
    let allowed_currencies: Vec<String> = match record.get_item("allowed_currencies")? {
        Some(v) if !v.is_none() => v.extract()?,
        _ => Vec::new(),
    };
    let input = quality::QualityInput {
        title: get_opt_string(record, "title")?,
        price: get_opt_f64(record, "price")?,
        original_price: get_opt_f64(record, "original_price")?,
        currency: get_opt_string(record, "currency")?,
        currency_raw: get_opt_string(record, "currency_raw")?,
        image_url: get_opt_string(record, "image_url")?,
        url: get_opt_string(record, "url")?,
        description: get_opt_string(record, "description")?,
        brand: get_opt_string(record, "brand")?,
        category_path,
        allowed_currencies,
    };
    let report = quality::assess(&input);
    let out = PyDict::new(py);
    out.set_item("score", report.score)?;
    out.set_item("grade", report.grade.to_string())?;
    out.set_item("flags", PyList::new(py, &report.flags)?)?;
    out.set_item("critical", report.critical)?;
    Ok(out)
}

/// Extract (product_url, price, currency, title) offers from one
/// category/list page. Returns a list of dicts; economic backbone of the
/// list-page price harvesting path.
#[pyfunction]
#[pyo3(signature = (html, base_url))]
fn extract_list_offers<'py>(
    py: Python<'py>,
    html: &str,
    base_url: &str,
) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let offers = listing_page::extract_list_offers(html, base_url);
    let mut out = Vec::with_capacity(offers.len());
    for offer in offers {
        let d = PyDict::new(py);
        d.set_item("url", offer.url)?;
        d.set_item("title", offer.title)?;
        d.set_item("price", offer.price)?;
        d.set_item("currency", offer.currency)?;
        d.set_item("price_raw_text", offer.price_raw_text)?;
        d.set_item("image_url", offer.image_url)?;
        out.push(d);
    }
    Ok(out)
}


/// Extract a cross-shop match signature from a normalized product name.
/// Returns None when the name is unmatchable (no brand token or no model
/// code); see docs/MATCHING_PLAN.md slice M1.
#[pyfunction]
#[pyo3(signature = (name_normalized, known_brands))]
fn extract_match_signature<'py>(
    py: Python<'py>,
    name_normalized: Option<&str>,
    known_brands: Vec<String>,
) -> PyResult<Option<Bound<'py, PyDict>>> {
    let Some(name) = name_normalized else {
        return Ok(None);
    };
    match matching::extract_match_signature(name, &known_brands) {
        None => Ok(None),
        Some(sig) => {
            let out = PyDict::new(py);
            out.set_item("brand", sig.brand)?;
            out.set_item("code", sig.code)?;
            out.set_item("codes", PyList::new(py, &sig.codes)?)?;
            out.set_item("attrs", PyList::new(py, &sig.attrs)?)?;
            out.set_item("confidence", sig.confidence)?;
            Ok(Some(out))
        }
    }
}

/// Normalize an EN title into the sorted token key used by title matching.
#[pyfunction]
fn normalize_title_tokens(title: &str) -> Vec<String> {
    matching::normalize_title_tokens(title)
}

/// Jaccard similarity of two normalized token sets (0.0 on unit conflict).
#[pyfunction]
fn title_similarity(a: Vec<String>, b: Vec<String>) -> f64 {
    matching::title_similarity(&a, &b)
}

/// Parse a sitemap index / urlset: {"sitemaps": [...], "urls": [...],
/// "url_entries": [{"loc", "lastmod", "alternates": {hreflang: href}}]}.
#[pyfunction]
fn parse_sitemap_xml<'py>(py: Python<'py>, xml: &str) -> PyResult<Bound<'py, PyDict>> {
    let parsed = sitemap::parse_sitemap_xml(xml);
    let out = PyDict::new(py);
    out.set_item("sitemaps", PyList::new(py, &parsed.sitemaps)?)?;
    let urls: Vec<&str> = parsed.entries.iter().map(|e| e.loc.as_str()).collect();
    out.set_item("urls", PyList::new(py, &urls)?)?;
    let entries = PyList::empty(py);
    for entry in &parsed.entries {
        let d = PyDict::new(py);
        d.set_item("loc", &entry.loc)?;
        d.set_item("lastmod", entry.lastmod.as_deref())?;
        let alts = PyDict::new(py);
        for (lang, href) in &entry.alternates {
            alts.set_item(lang, href)?;
        }
        d.set_item("alternates", alts)?;
        entries.append(d)?;
    }
    out.set_item("url_entries", entries)?;
    Ok(out)
}

/// FactListing.compute_url_hash twin.
#[pyfunction]
fn url_hash(url: &str) -> String {
    sitemap::url_hash(url)
}

/// url_hash for many URLs in one call (the 150k-URL shard loop).
#[pyfunction]
fn url_hashes(urls: Vec<String>) -> Vec<String> {
    urls.iter().map(|u| sitemap::url_hash(u)).collect()
}

/// sitemap_enumerator._url_is_product_like twin (path only).
#[pyfunction]
fn product_like_path(path: &str) -> bool {
    sitemap::product_like_path(path)
}

/// sitemap_categories.category_like twin (full URL).
#[pyfunction]
fn category_like_url(url: &str) -> bool {
    sitemap::category_like_url(url)
}

/// sitemap_locale.url_locale_segment twin.
#[pyfunction]
fn url_locale_segment(url: &str) -> Option<String> {
    sitemap::url_locale_segment(url)
}

/// sitemap_locale.is_noise_sitemap twin.
#[pyfunction]
fn is_noise_sitemap(url: &str) -> bool {
    sitemap::is_noise_sitemap(url)
}

/// sitemap_locale.select_sitemap_subfiles twin:
/// {"kept": [...], "skipped_noise": n, "skipped_locale": n, "locale": str|None}.
#[pyfunction]
#[pyo3(signature = (urls, canonical=None, country_hint=None, whole_tree=false))]
fn select_sitemap_subfiles<'py>(
    py: Python<'py>,
    urls: Vec<String>,
    canonical: Option<&str>,
    country_hint: Option<&str>,
    whole_tree: bool,
) -> PyResult<Bound<'py, PyDict>> {
    let sel = sitemap::select_sitemap_subfiles(&urls, canonical, country_hint, whole_tree);
    let out = PyDict::new(py);
    out.set_item("kept", PyList::new(py, &sel.kept)?)?;
    out.set_item("skipped_noise", sel.skipped_noise)?;
    out.set_item("skipped_locale", sel.skipped_locale)?;
    out.set_item("locale", sel.locale)?;
    Ok(out)
}

/// sitemap_locale.dominant_locale twin.
#[pyfunction]
fn dominant_locale(urls: Vec<String>, min_share: f64) -> Option<String> {
    sitemap::dominant_locale(&urls, min_share)
}

#[pymodule]
fn imperecta_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_sitemap_xml, m)?)?;
    m.add_function(wrap_pyfunction!(url_hash, m)?)?;
    m.add_function(wrap_pyfunction!(url_hashes, m)?)?;
    m.add_function(wrap_pyfunction!(product_like_path, m)?)?;
    m.add_function(wrap_pyfunction!(category_like_url, m)?)?;
    m.add_function(wrap_pyfunction!(url_locale_segment, m)?)?;
    m.add_function(wrap_pyfunction!(is_noise_sitemap, m)?)?;
    m.add_function(wrap_pyfunction!(select_sitemap_subfiles, m)?)?;
    m.add_function(wrap_pyfunction!(dominant_locale, m)?)?;
    m.add_function(wrap_pyfunction!(parse_price_text, m)?)?;
    m.add_function(wrap_pyfunction!(parse_currency_symbol, m)?)?;
    m.add_function(wrap_pyfunction!(parse_currency_code, m)?)?;
    m.add_function(wrap_pyfunction!(detect_currency, m)?)?;
    m.add_function(wrap_pyfunction!(currency_token_is_ambiguous, m)?)?;
    m.add_function(wrap_pyfunction!(extract_jsonld, m)?)?;
    m.add_function(wrap_pyfunction!(extract_list_offers, m)?)?;
    m.add_function(wrap_pyfunction!(extract_match_signature, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_title_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(title_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(assess_quality, m)?)?;
    m.add("__core_version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
