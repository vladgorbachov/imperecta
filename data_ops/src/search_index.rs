//! In-memory product-name search index (R3).
//!
//! Rationale: the ILIKE phase over 2.17M names costs 1-9s on the shared
//! Postgres (cold trgm bitmap on a small instance). This index holds every
//! active product's lowercased name in one arena and answers substring
//! queries with a parallel memchr scan — tens of milliseconds, zero DB
//! load, and it keeps paying for itself when Supabase compute is upgraded.
//!
//! Freshness: a full snapshot on boot, then incremental pulls by
//! updated_at watermark every REFRESH_SECS. Rebuild-from-scratch happens
//! when the incremental layer grows past REBUILD_RATIO of the base.

use std::sync::Arc;
use std::time::Duration;

use arc_swap::ArcSwap;
use rayon::prelude::*;
use sqlx::{PgPool, Row};
use uuid::Uuid;

// 300s: the delta pull is correctness-uncritical (search lags new
// products by minutes at worst) and the shared instance is write-heavy —
// keep our background pressure minimal.
pub const REFRESH_SECS: u64 = 300;
const REBUILD_RATIO: f64 = 0.10;
/// Names are truncated for the arena: substring UX never needs more.
const MAX_NAME_BYTES: usize = 120;
const SHARDS: usize = 8;

struct Shard {
    /// Lowercased names, '\n'-separated (the separator can't occur in a
    /// tokenized name, so matches never cross entries).
    arena: String,
    /// (byte offset, byte len, product id) per entry, offset-sorted.
    entries: Vec<(u32, u32, Uuid)>,
}

pub struct Index {
    shards: Vec<Shard>,
    /// Products updated after the base snapshot (delta layer, small).
    delta: Vec<(String, Uuid)>,
    pub watermark: chrono::DateTime<chrono::Utc>,
    pub len: usize,
}

impl Index {
    fn search_into(&self, needle: &str, cap: usize) -> Vec<Uuid> {
        let needle = needle.to_lowercase();
        if needle.is_empty() {
            return Vec::new();
        }
        let mut out: Vec<Uuid> = self
            .shards
            .par_iter()
            .flat_map_iter(|shard| shard_hits(shard, &needle, cap))
            .collect();
        // Delta layer: linear scan (small by construction).
        for (name, id) in &self.delta {
            if name.contains(&needle) {
                out.push(*id);
            }
        }
        out.truncate(cap);
        out
    }
}

fn shard_hits(shard: &Shard, needle: &str, cap: usize) -> Vec<Uuid> {
    let mut hits = Vec::new();
    let hay = shard.arena.as_bytes();
    let pat = needle.as_bytes();
    let mut from = 0usize;
    while hits.len() < cap {
        let Some(rel) = find_sub(&hay[from..], pat) else { break };
        let pos = from + rel;
        // Entry lookup: offsets are sorted; find the entry containing pos.
        let idx = match shard
            .entries
            .binary_search_by(|(off, _len, _)| (*off as usize).cmp(&pos))
        {
            Ok(i) => i,
            Err(0) => 0,
            Err(i) => i - 1,
        };
        let (off, len, id) = shard.entries[idx];
        let end = off as usize + len as usize;
        if pos < end {
            hits.push(id);
            from = end + 1; // skip to the next entry — one hit per entry
        } else {
            from = pos + 1;
        }
    }
    hits
}

fn find_sub(hay: &[u8], pat: &[u8]) -> Option<usize> {
    if pat.is_empty() || hay.len() < pat.len() {
        return None;
    }
    let first = pat[0];
    let mut i = 0usize;
    while let Some(rel) = memchr::memchr(first, &hay[i..]) {
        let start = i + rel;
        if start + pat.len() > hay.len() {
            return None;
        }
        if &hay[start..start + pat.len()] == pat {
            return Some(start);
        }
        i = start + 1;
    }
    None
}

pub struct SearchIndex {
    current: ArcSwap<Option<Index>>,
}

impl SearchIndex {
    pub fn new() -> Self {
        Self {
            current: ArcSwap::from_pointee(None),
        }
    }

    pub fn ready(&self) -> bool {
        self.current.load().is_some()
    }

    pub fn len(&self) -> usize {
        self.current.load().as_ref().as_ref().map_or(0, |i| i.len)
    }

    /// Substring search over active product names; None until warmed.
    pub fn search(&self, needle: &str, cap: usize) -> Option<Vec<Uuid>> {
        let guard = self.current.load();
        guard.as_ref().as_ref().map(|i| i.search_into(needle, cap))
    }

    pub async fn build_full(&self, pool: &PgPool) -> Result<usize, sqlx::Error> {
        use futures_util::TryStreamExt as _;

        // One streamed pass (no ORDER BY — entry order is irrelevant to a
        // substring scan): a single sequential read instead of 20+ sorted
        // page queries hammering the shared instance.
        let mut names: Vec<(String, Uuid)> = Vec::with_capacity(2_200_000);
        let mut watermark = chrono::DateTime::<chrono::Utc>::MIN_UTC;
        let mut stream = sqlx::query(
            "SELECT id, name, updated_at FROM dim_product WHERE is_active",
        )
        .fetch(pool);
        while let Some(r) = stream.try_next().await? {
            let id: Uuid = r.get("id");
            let name: String = r.get("name");
            let ts: chrono::DateTime<chrono::Utc> = r.get("updated_at");
            if ts > watermark {
                watermark = ts;
            }
            names.push((clip_lower(&name), id));
        }
        drop(stream);
        let total = names.len();
        let index = assemble(names, watermark);
        self.current.store(Arc::new(Some(index)));
        Ok(total)
    }

    pub async fn refresh_delta(&self, pool: &PgPool) -> Result<usize, sqlx::Error> {
        let loaded = self.current.load_full();
        let Some(cur) = loaded.as_ref() else {
            return Ok(0);
        };
        let rows = sqlx::query(
            r#"SELECT id, name, updated_at FROM dim_product
               WHERE is_active AND updated_at > $1
               ORDER BY updated_at LIMIT 20000"#,
        )
        .bind(cur.watermark)
        .fetch_all(pool)
        .await?;
        if rows.is_empty() {
            return Ok(0);
        }
        let mut delta = cur.delta.clone();
        let mut watermark = cur.watermark;
        for r in &rows {
            let id: Uuid = r.get("id");
            let name: String = r.get("name");
            let ts: chrono::DateTime<chrono::Utc> = r.get("updated_at");
            if ts > watermark {
                watermark = ts;
            }
            delta.push((clip_lower(&name), id));
        }
        let grew = rows.len();
        let base_len: usize = cur.shards.iter().map(|s| s.entries.len()).sum();
        if (delta.len() as f64) > (base_len as f64) * REBUILD_RATIO {
            // Fold the delta in with a full rebuild (background caller loop).
            drop(delta);
            let n = self.build_full(pool).await?;
            return Ok(n);
        }
        let next = Index {
            shards: cur
                .shards
                .iter()
                .map(|s| Shard {
                    arena: s.arena.clone(),
                    entries: s.entries.clone(),
                })
                .collect(),
            delta,
            watermark,
            len: cur.len + grew,
        };
        self.current.store(Arc::new(Some(next)));
        Ok(grew)
    }
}

fn clip_lower(name: &str) -> String {
    let lower = name
        .to_lowercase()
        .replace(['\n', '\u{0}'], " ");
    if lower.len() <= MAX_NAME_BYTES {
        lower
    } else {
        let mut end = MAX_NAME_BYTES;
        while !lower.is_char_boundary(end) {
            end -= 1;
        }
        lower[..end].to_string()
    }
}

fn assemble(names: Vec<(String, Uuid)>, watermark: chrono::DateTime<chrono::Utc>) -> Index {
    let len = names.len();
    let per_shard = len.div_ceil(SHARDS.max(1)).max(1);
    let mut shards = Vec::with_capacity(SHARDS);
    for chunk in names.chunks(per_shard) {
        let mut arena = String::with_capacity(chunk.len() * 48);
        let mut entries = Vec::with_capacity(chunk.len());
        for (name, id) in chunk {
            let off = arena.len() as u32;
            arena.push_str(name);
            entries.push((off, name.len() as u32, *id));
            arena.push('\n');
        }
        shards.push(Shard { arena, entries });
    }
    Index {
        shards,
        delta: Vec::new(),
        watermark,
        len,
    }
}

/// Background warm + refresh loop.
pub fn spawn_refresher(index: Arc<SearchIndex>, pool: PgPool) {
    tokio::spawn(async move {
        loop {
            let result = if index.ready() {
                index.refresh_delta(&pool).await
            } else {
                index.build_full(&pool).await
            };
            match result {
                Ok(n) if n > 0 => {
                    tracing::info!(rows = n, total = index.len(), "search index refreshed")
                }
                Ok(_) => {}
                Err(e) => tracing::warn!(error = %e, "search index refresh failed"),
            }
            tokio::time::sleep(Duration::from_secs(REFRESH_SECS)).await;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build(names: &[(&str, u128)]) -> Index {
        assemble(
            names
                .iter()
                .map(|(n, i)| (clip_lower(n), Uuid::from_u128(*i)))
                .collect(),
            chrono::Utc::now(),
        )
    }

    #[test]
    fn finds_substring_case_insensitive() {
        let idx = build(&[
            ("Lenovo IdeaPad 5", 1),
            ("Samsung Galaxy S24", 2),
            ("Laptop LENOVO Legion", 3),
        ]);
        let hits = idx.search_into("lenovo", 10);
        let ids: Vec<u128> = hits.iter().map(|u| u.as_u128()).collect();
        assert!(ids.contains(&1) && ids.contains(&3) && !ids.contains(&2));
    }

    #[test]
    fn one_hit_per_entry_and_cap() {
        let idx = build(&[("aaa aaa aaa", 1), ("aaa", 2), ("bbb", 3)]);
        let hits = idx.search_into("aaa", 10);
        assert_eq!(hits.len(), 2);
        let capped = idx.search_into("aaa", 1);
        assert_eq!(capped.len(), 1);
    }

    #[test]
    fn no_cross_entry_match() {
        // "ab" at the end of one name + "cd" at the start of the next must
        // not match "b\nc" style needles thanks to the separator.
        let idx = build(&[("widget ab", 1), ("cd gadget", 2)]);
        assert!(idx.search_into("ab cd", 10).is_empty());
    }

    #[test]
    fn delta_layer_is_searched() {
        let mut idx = build(&[("old name", 1)]);
        idx.delta.push((clip_lower("Fresh Kettle"), Uuid::from_u128(9)));
        let hits = idx.search_into("kettle", 10);
        assert_eq!(hits.len(), 1);
    }
}
