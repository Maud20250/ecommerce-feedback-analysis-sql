-- ============================================================
-- Final Project Part 2 – Analysis Queries
-- E-Commerce Customer Feedback Analysis
-- ============================================================
USE ecommerce_feedback;
 
-- ============================================================
-- SECTION 1: TOP-RATED PRODUCTS
-- Average rating per product, top 10 by rating
-- ============================================================
 
-- Q1: Top 10 products by average rating (min 1 review)
SELECT
    p.product_id,
    p.name                              AS product_name,
    p.category,
    p.price,
    COUNT(r.review_id)                  AS total_reviews,
    ROUND(AVG(r.rating), 2)             AS avg_rating,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN r.rating <= 2 THEN 1 ELSE 0 END) AS negative_count
FROM products p
JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category, p.price
ORDER BY avg_rating DESC, total_reviews DESC
LIMIT 10;
 
-- ============================================================
-- SECTION 2: COMMON COMPLAINTS (KEYWORD SEARCH)
-- Count reviews mentioning complaint keywords, grouped by category
-- ============================================================
 
-- Q2a: Keyword frequency across all reviews
SELECT
    SUM(CASE WHEN LOWER(r.comments) LIKE '%damaged%'   THEN 1 ELSE 0 END) AS damaged,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%late%'      THEN 1 ELSE 0 END) AS late,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%defective%' THEN 1 ELSE 0 END) AS defective,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%broken%'    THEN 1 ELSE 0 END) AS broken,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%poor%'      THEN 1 ELSE 0 END) AS poor,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%slow%'      THEN 1 ELSE 0 END) AS slow,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%average%'   THEN 1 ELSE 0 END) AS average_mentions,
    COUNT(r.review_id)                                                     AS total_reviews
FROM reviews r;
 
-- Q2b: Complaint keyword occurrences grouped by product category
SELECT
    p.category,
    COUNT(r.review_id)                                                     AS total_reviews,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%damaged%'   THEN 1 ELSE 0 END) AS damaged,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%late%'      THEN 1 ELSE 0 END) AS late,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%defective%' THEN 1 ELSE 0 END) AS defective,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%broken%'    THEN 1 ELSE 0 END) AS broken,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%poor%'      THEN 1 ELSE 0 END) AS poor,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%slow%'      THEN 1 ELSE 0 END) AS slow,
    SUM(CASE WHEN LOWER(r.comments) LIKE '%damaged%'
           + LOWER(r.comments) LIKE '%late%'
           + LOWER(r.comments) LIKE '%defective%'
           + LOWER(r.comments) LIKE '%broken%'
           + LOWER(r.comments) LIKE '%poor%'
           + LOWER(r.comments) LIKE '%slow%'   THEN 1 ELSE 0 END)        AS total_complaint_mentions
FROM reviews r
JOIN products p ON r.product_id = p.product_id
GROUP BY p.category
ORDER BY total_complaint_mentions DESC;
 
-- Q2c: Individual flagged reviews containing any complaint keyword
SELECT
    r.review_id,
    c.name          AS customer_name,
    c.region,
    p.name          AS product_name,
    p.category,
    r.rating,
    r.comments,
    r.source,
    r.review_date,
    CASE
        WHEN LOWER(r.comments) LIKE '%damaged%'   THEN 'damaged'
        WHEN LOWER(r.comments) LIKE '%late%'      THEN 'late'
        WHEN LOWER(r.comments) LIKE '%defective%' THEN 'defective'
        WHEN LOWER(r.comments) LIKE '%broken%'    THEN 'broken'
        WHEN LOWER(r.comments) LIKE '%poor%'      THEN 'poor'
        WHEN LOWER(r.comments) LIKE '%slow%'      THEN 'slow'
        WHEN LOWER(r.comments) LIKE '%average%'   THEN 'average quality'
        ELSE 'other'
    END             AS complaint_type
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
LEFT JOIN products p ON r.product_id = p.product_id
WHERE
    LOWER(r.comments) LIKE '%damaged%'   OR
    LOWER(r.comments) LIKE '%late%'      OR
    LOWER(r.comments) LIKE '%defective%' OR
    LOWER(r.comments) LIKE '%broken%'    OR
    LOWER(r.comments) LIKE '%poor%'      OR
    LOWER(r.comments) LIKE '%slow%'      OR
    LOWER(r.comments) LIKE '%average%'
ORDER BY r.rating ASC, r.review_date DESC;
 
-- ============================================================
-- SECTION 3: CUSTOMER SENTIMENT CLASSIFICATION
-- Classify reviews as Positive / Neutral / Negative using CASE
-- ============================================================
 
-- Q3a: Sentiment label on individual reviews
SELECT
    r.review_id,
    c.name          AS customer_name,
    c.region,
    p.name          AS product_name,
    r.rating,
    r.comments,
    r.source,
    CASE
        WHEN r.rating >= 4 THEN 'Positive'
        WHEN r.rating = 3  THEN 'Neutral'
        ELSE                    'Negative'
    END             AS sentiment
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
LEFT JOIN products p ON r.product_id = p.product_id
ORDER BY r.rating DESC;
 
-- Q3b: Sentiment summary count
SELECT
    CASE
        WHEN rating >= 4 THEN 'Positive'
        WHEN rating = 3  THEN 'Neutral'
        ELSE                  'Negative'
    END                             AS sentiment,
    COUNT(*)                        AS review_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM reviews), 1) AS percentage
FROM reviews
GROUP BY sentiment
ORDER BY review_count DESC;
 
-- Q3c: Sentiment breakdown by product
SELECT
    p.name                              AS product_name,
    p.category,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS positive,
    SUM(CASE WHEN r.rating  = 3 THEN 1 ELSE 0 END) AS neutral,
    SUM(CASE WHEN r.rating <= 2 THEN 1 ELSE 0 END) AS negative,
    COUNT(r.review_id)                              AS total_reviews,
    ROUND(AVG(r.rating), 2)                         AS avg_rating
FROM products p
LEFT JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category
ORDER BY avg_rating DESC;
 
-- ============================================================
-- SECTION 4: TRENDS OVER TIME
-- Monthly and quarterly rating trends
-- ============================================================
 
-- Q4a: Monthly trend – average rating and review volume
SELECT
    DATE_FORMAT(r.review_date, '%Y-%m')             AS month,
    COUNT(r.review_id)                              AS review_count,
    ROUND(AVG(r.rating), 2)                         AS avg_rating,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS positive_reviews,
    SUM(CASE WHEN r.rating <= 2 THEN 1 ELSE 0 END) AS negative_reviews
FROM reviews r
WHERE r.review_date IS NOT NULL
GROUP BY DATE_FORMAT(r.review_date, '%Y-%m')
ORDER BY month ASC;
 
-- Q4b: Quarterly trend
SELECT
    YEAR(r.review_date)                             AS year,
    QUARTER(r.review_date)                          AS quarter,
    CONCAT('Q', QUARTER(r.review_date), '-', YEAR(r.review_date)) AS period,
    COUNT(r.review_id)                              AS review_count,
    ROUND(AVG(r.rating), 2)                         AS avg_rating
FROM reviews r
WHERE r.review_date IS NOT NULL
GROUP BY YEAR(r.review_date), QUARTER(r.review_date)
ORDER BY year, quarter;
 
-- Q4c: Reviews per data source over time
SELECT
    DATE_FORMAT(r.review_date, '%Y-%m')             AS month,
    r.source,
    COUNT(r.review_id)                              AS review_count,
    ROUND(AVG(r.rating), 2)                         AS avg_rating
FROM reviews r
WHERE r.review_date IS NOT NULL
GROUP BY DATE_FORMAT(r.review_date, '%Y-%m'), r.source
ORDER BY month, r.source;
 
-- ============================================================
-- SECTION 5: PRODUCT CATEGORIES WITH HIGHEST SATISFACTION
-- ============================================================
 
-- Q5a: Average rating by category
SELECT
    p.category,
    COUNT(r.review_id)              AS total_reviews,
    ROUND(AVG(r.rating), 2)         AS avg_rating,
    MAX(r.rating)                   AS max_rating,
    MIN(r.rating)                   AS min_rating,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS satisfied_customers,
    ROUND(SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS satisfaction_rate_pct
FROM products p
JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.category
ORDER BY avg_rating DESC;
 
-- Q5b: Customer engagement by region
SELECT
    c.region,
    COUNT(DISTINCT c.customer_id)   AS unique_customers,
    COUNT(r.review_id)              AS total_reviews,
    ROUND(AVG(r.rating), 2)         AS avg_rating,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS positive_reviews
FROM customers c
LEFT JOIN reviews r ON c.customer_id = r.customer_id
GROUP BY c.region
ORDER BY avg_rating DESC;
 
-- ============================================================
-- SECTION 6: COMPLETE ANALYSIS VIEW (reusable)
-- ============================================================
 
CREATE OR REPLACE VIEW v_analysis_full AS
SELECT
    r.review_id,
    c.customer_id,
    c.name          AS customer_name,
    c.email,
    c.region,
    p.product_id,
    p.name          AS product_name,
    p.category,
    p.price,
    r.rating,
    r.comments,
    r.review_date,
    r.source,
    DATE_FORMAT(r.review_date, '%Y-%m')     AS review_month,
    QUARTER(r.review_date)                  AS review_quarter,
    YEAR(r.review_date)                     AS review_year,
    CASE
        WHEN r.rating >= 4 THEN 'Positive'
        WHEN r.rating = 3  THEN 'Neutral'
        ELSE                    'Negative'
    END             AS sentiment,
    CASE
        WHEN LOWER(r.comments) LIKE '%damaged%'   THEN 'damaged'
        WHEN LOWER(r.comments) LIKE '%late%'      THEN 'late'
        WHEN LOWER(r.comments) LIKE '%defective%' THEN 'defective'
        WHEN LOWER(r.comments) LIKE '%broken%'    THEN 'broken'
        WHEN LOWER(r.comments) LIKE '%poor%'      THEN 'poor'
        WHEN LOWER(r.comments) LIKE '%slow%'      THEN 'slow'
        WHEN LOWER(r.comments) LIKE '%average%'   THEN 'average quality'
        ELSE NULL
    END             AS complaint_type
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
LEFT JOIN products p ON r.product_id = p.product_id;
 
-- ============================================================
-- SECTION 7: VALIDATION QUERIES
-- Confirm data integrity after full integration
-- ============================================================
 
-- Row counts per table
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL
SELECT 'products',  COUNT(*) FROM products
UNION ALL
SELECT 'reviews',   COUNT(*) FROM reviews;
 
-- Duplicate detection using SELECT DISTINCT
SELECT
    'Duplicate reviews' AS check_name,
    COUNT(*) - COUNT(DISTINCT CONCAT(customer_id, '|', source, '|', comments)) AS duplicates_found
FROM reviews;
 
-- Orphaned reviews (no matching customer)
SELECT COUNT(*) AS orphaned_reviews
FROM reviews r
LEFT JOIN customers c ON r.customer_id = c.customer_id
WHERE c.customer_id IS NULL;
 
-- Ratings outside valid range
SELECT COUNT(*) AS invalid_ratings
FROM reviews
WHERE rating NOT BETWEEN 1 AND 5;
 
-- NULL review dates
SELECT COUNT(*) AS null_dates
FROM reviews
WHERE review_date IS NULL;