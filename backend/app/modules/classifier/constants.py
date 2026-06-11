"""Schema.org / OG / JSON-LD / Microdata constant sets used by the classifier.

Moved verbatim from ``app.modules.scraper.extractors`` in CLS1. Kept inside
the classifier (NOT in Tier-0 common) because they are classification
vocabulary — only the gate logic in this module reads them.
"""

# Open Graph og:type values that indicate a single product detail page.
# Reference: https://ogp.me/ + product-specific extensions used by Shopify,
# WooCommerce, Magento, Facebook Catalog.
_OG_TYPES_PRODUCT = frozenset({"product", "product.group", "product.item"})
# Open Graph og:type values that indicate a non-product content page.
# 'website' maps to 'hub' downstream; the rest map to 'listing'.
# Rare/ambiguous og:types (profile, book, music, video) are intentionally
# excluded here — they fall through to JSON-LD layer and then to the
# structural fallback rather than being force-classified.
_OG_TYPES_LISTING = frozenset({"article", "blog", "news"})
_OG_TYPES_HUB = frozenset({"website"})

# JSON-LD @type values from schema.org that indicate a single product detail page.
_JSONLD_TYPES_PRODUCT = frozenset({"Product", "IndividualProduct", "ProductModel"})
# JSON-LD @type values that indicate a listing/results page.
_JSONLD_TYPES_LISTING = frozenset({
    "CollectionPage", "ItemList", "SearchResultsPage",
    "Article", "NewsArticle", "BlogPosting",
})
# JSON-LD @type values that indicate a navigational/informational page (hub).
_JSONLD_TYPES_HUB = frozenset({"WebPage", "AboutPage", "ContactPage", "FAQPage"})

# HTML5 Microdata itemtype values (schema.org). Both http:// and https://
# prefixes are valid per schema.org docs and appear in the wild.
_MICRODATA_TYPES_PRODUCT = frozenset({
    "http://schema.org/Product",
    "https://schema.org/Product",
})
_MICRODATA_TYPES_LISTING = frozenset({
    "http://schema.org/ItemList",
    "https://schema.org/ItemList",
    "http://schema.org/OfferCatalog",
    "https://schema.org/OfferCatalog",
    "http://schema.org/CollectionPage",
    "https://schema.org/CollectionPage",
})


__all__ = [
    "_OG_TYPES_PRODUCT",
    "_OG_TYPES_LISTING",
    "_OG_TYPES_HUB",
    "_JSONLD_TYPES_PRODUCT",
    "_JSONLD_TYPES_LISTING",
    "_JSONLD_TYPES_HUB",
    "_MICRODATA_TYPES_PRODUCT",
    "_MICRODATA_TYPES_LISTING",
]
