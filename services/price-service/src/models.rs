use chrono::{DateTime, Utc};
use serde::Serialize;

// NOTE: Prisma stores all IDs as TEXT (String), not native PostgreSQL UUID.
// So IDs are represented as String here, not uuid::Uuid.

/// Current price for a pharmacy product (from current_prices view)
#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct CurrentPrice {
    pub pharmacy_product_id: String,
    pub price: i32,
    pub original_price: Option<i32>,
    pub discount_pct: Option<i16>,
    pub stock_status: Option<String>,
    pub recorded_at: DateTime<Utc>,
}

/// Price comparison result across pharmacies for a medication
#[derive(Debug, Serialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct PriceComparison {
    pub pharmacy_id: String,
    pub pharmacy_name: String,
    pub pharmacy_chain: Option<String>,
    pub pharmacy_city: Option<String>,
    pub pharmacy_region: Option<String>,
    pub pharmacy_product_id: String,
    pub price: i32,
    pub original_price: Option<i32>,
    pub discount_pct: Option<i16>,
    pub stock_status: Option<String>,
    pub recorded_at: DateTime<Utc>,
}

/// Single price history data point for charting
#[derive(Debug, Serialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct PriceHistoryPoint {
    pub recorded_at: DateTime<Utc>,
    pub price: i32,
    pub pharmacy_name: String,
}

/// Statistics summary for a medication's prices
// MIN/MAX on integer column returns i32; COUNT returns i64
#[derive(Debug, Serialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct PriceStats {
    pub medication_id: String,
    pub min_price: Option<i32>,
    pub max_price: Option<i32>,
    pub avg_price: Option<f64>,
    pub pharmacy_count: Option<i64>,
}
