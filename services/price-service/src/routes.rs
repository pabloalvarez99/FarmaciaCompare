use axum::{
    Router,
    extract::{Path, Query, State},
    http::StatusCode,
    response::Json,
    routing::get,
};
use serde::Deserialize;

use crate::{AppState, models::*};

pub fn price_routes() -> Router<AppState> {
    Router::new()
        .route("/health", get(health))
        .route("/api/v1/prices/medications/{id}", get(get_medication_prices))
        .route("/api/v1/prices/medications/{id}/history", get(get_price_history))
        .route("/api/v1/prices/medications/{id}/stats", get(get_price_stats))
}

async fn health() -> &'static str {
    "ok"
}

#[derive(Deserialize)]
pub struct PriceHistoryQuery {
    pub days: Option<i32>,
}

/// GET /api/v1/prices/medications/:id
/// Returns current prices for a medication across all pharmacies, cheapest first.
async fn get_medication_prices(
    State(state): State<AppState>,
    Path(medication_id): Path<String>,
) -> Result<Json<Vec<PriceComparison>>, StatusCode> {
    let rows = sqlx::query_as!(
        PriceComparison,
        r#"
        SELECT
            ph.id            AS pharmacy_id,
            ph.name          AS pharmacy_name,
            ph.chain         AS "pharmacy_chain?: String",
            ph.city          AS "pharmacy_city?: String",
            ph.region        AS "pharmacy_region?: String",
            pp.id            AS pharmacy_product_id,
            cp.price         AS "price!: i32",
            cp.original_price AS "original_price?: i32",
            cp.discount_pct  AS "discount_pct?: i16",
            cp.stock_status,
            cp.recorded_at   AS "recorded_at!: chrono::DateTime<chrono::Utc>"
        FROM pharmacy_products pp
        JOIN current_prices cp ON cp.pharmacy_product_id = pp.id
        JOIN pharmacies ph      ON ph.id = pp.pharmacy_id
        WHERE pp.medication_id = $1
          AND pp.is_active = true
          AND ph.is_active  = true
          AND (cp.stock_status IS NULL OR cp.stock_status != 'out_of_stock')
        ORDER BY cp.price ASC
        "#,
        medication_id
    )
    .fetch_all(&state.pool)
    .await
    .map_err(|e| {
        tracing::error!("DB error in get_medication_prices: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(rows))
}

/// GET /api/v1/prices/medications/:id/history?days=30
/// Returns daily min price per pharmacy for charting.
async fn get_price_history(
    State(state): State<AppState>,
    Path(medication_id): Path<String>,
    Query(q): Query<PriceHistoryQuery>,
) -> Result<Json<Vec<PriceHistoryPoint>>, StatusCode> {
    let days = q.days.unwrap_or(30);

    let rows = sqlx::query_as!(
        PriceHistoryPoint,
        r#"
        SELECT
            DATE_TRUNC('day', p.recorded_at)::timestamptz AS "recorded_at!: chrono::DateTime<chrono::Utc>",
            MIN(p.price)::int                             AS "price!: i32",
            ph.name                                       AS pharmacy_name
        FROM prices p
        JOIN pharmacy_products pp ON pp.id = p.pharmacy_product_id
        JOIN pharmacies ph         ON ph.id = pp.pharmacy_id
        WHERE pp.medication_id = $1
          AND p.recorded_at   >= NOW() - make_interval(days => $2)
        GROUP BY DATE_TRUNC('day', p.recorded_at), ph.id, ph.name
        ORDER BY DATE_TRUNC('day', p.recorded_at) ASC, MIN(p.price) ASC
        "#,
        medication_id,
        days
    )
    .fetch_all(&state.pool)
    .await
    .map_err(|e| {
        tracing::error!("DB error in get_price_history: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(rows))
}

/// GET /api/v1/prices/medications/:id/stats
/// Returns aggregate stats: min, max, avg price and pharmacy count.
async fn get_price_stats(
    State(state): State<AppState>,
    Path(medication_id): Path<String>,
) -> Result<Json<PriceStats>, StatusCode> {
    let row = sqlx::query_as!(
        PriceStats,
        r#"
        SELECT
            pp.medication_id                              AS "medication_id!",
            MIN(cp.price)                                AS "min_price?: i32",
            MAX(cp.price)                                AS "max_price?: i32",
            ROUND(AVG(cp.price)::numeric, 2)::float8     AS "avg_price?: f64",
            COUNT(DISTINCT pp.pharmacy_id)               AS "pharmacy_count?: i64"
        FROM pharmacy_products pp
        JOIN current_prices cp ON cp.pharmacy_product_id = pp.id
        WHERE pp.medication_id = $1
          AND pp.is_active = true
        GROUP BY pp.medication_id
        "#,
        medication_id
    )
    .fetch_optional(&state.pool)
    .await
    .map_err(|e| {
        tracing::error!("DB error in get_price_stats: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(row))
}
