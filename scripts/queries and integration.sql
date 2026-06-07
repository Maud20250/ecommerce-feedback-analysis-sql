-- ============================================================
-- Final Project Part 1 - Data Insertion & SQL Queries
-- ============================================================
USE ecommerce_feedback;
 
-- ============================================================
-- PART A: Load CSV data (customer_survey.csv)
-- Method 1: LOAD DATA LOCAL INFILE (recommended for MySQL CLI)
-- ============================================================
-- Step 1: Load raw survey data into a staging table
CREATE TEMPORARY TABLE temp_survey (
    customer_id   INT,
    name          VARCHAR(100),
    email         VARCHAR(150),
    region        VARCHAR(50),
    rating        TINYINT,
    comments      TEXT,
    review_date   DATE
);
 
LOAD DATA LOCAL INFILE 'customer_survey.csv'
INTO TABLE temp_survey
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(customer_id, name, email, region, rating, comments, review_date);
 
-- Step 2: Insert customers (avoiding duplicates)
INSERT INTO customers (customer_id, name, email, region)
SELECT customer_id, name, email, region FROM temp_survey
ON DUPLICATE KEY UPDATE name=VALUES(name), region=VALUES(region);
 
-- Step 3: Insert reviews from survey
INSERT INTO reviews (customer_id, product_id, rating, comments, review_date, source)
SELECT customer_id, 1, rating, comments, review_date, 'survey'
FROM temp_survey;
 
-- ============================================================
-- PART B: Web Feedback (web_feedback.json) - via JSON functions
-- Run after Python script pre-inserts rows into raw_web_feedback
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_web_feedback (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    payload     JSON
);
 
-- Insert parsed JSON rows (executed by Python script, see parse_json.py)
-- Example of how MySQL reads them once loaded:
INSERT INTO reviews (customer_id, product_id, rating, comments, review_date, source)
SELECT
    payload->>'$.customer_id',
    2,
    payload->>'$.rating',
    payload->>'$.comments',
    CURDATE(),
    'web'
FROM raw_web_feedback
WHERE payload->>'$.customer_id' NOT IN (
    SELECT customer_id FROM reviews WHERE source='web'
);
 
-- ============================================================
-- PART C: External Reviews (external_reviews.xml)
-- XML data parsed by Python (parse_xml.py) into staging table
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_xml_reviews (
    customer_id   INT,
    rating        TINYINT,
    comments      TEXT
);
 
-- After Python populates raw_xml_reviews:
INSERT INTO reviews (customer_id, product_id, rating, comments, review_date, source)
SELECT customer_id, 3, rating, comments, CURDATE(), 'external'
FROM raw_xml_reviews;
 
-- ============================================================
-- PART D: Data Cleaning & Correction (UPDATE examples)
-- ============================================================
-- Fix NULL regions
UPDATE customers SET region = 'Unknown' WHERE region IS NULL OR region = '';
 
-- Clamp out-of-range ratings to valid range 1-5
UPDATE reviews SET rating = 1 WHERE rating < 1;
UPDATE reviews SET rating = 5 WHERE rating > 5;
 
-- Standardize comments: trim leading/trailing whitespace
UPDATE reviews SET comments = TRIM(comments) WHERE comments IS NOT NULL;
 
-- ============================================================
-- PART E: SELECT Queries — Filtering, Grouping, Sorting
-- ============================================================
 
-- Q1: All reviews with customer name, sorted by rating DESC
SELECT
    r.review_id,
    c.name          AS customer_name,
    c.region,
    r.rating,
    r.comments,
    r.review_date,
    r.source
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
ORDER BY r.rating DESC, r.review_date DESC;
 
-- Q2: Reviews with rating <= 2 (negative feedback flag)
SELECT
    c.name,
    c.email,
    r.rating,
    r.comments,
    r.source
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
WHERE r.rating <= 2
ORDER BY r.rating ASC;
 
-- Q3: Average rating per product
SELECT
    p.name          AS product_name,
    p.category,
    COUNT(r.review_id)          AS total_reviews,
    ROUND(AVG(r.rating), 2)     AS avg_rating,
    SUM(CASE WHEN r.rating >= 4 THEN 1 ELSE 0 END) AS positive_reviews,
    SUM(CASE WHEN r.rating <= 2 THEN 1 ELSE 0 END) AS negative_reviews
FROM products p
LEFT JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category
ORDER BY avg_rating DESC;
 
-- Q4: Customer engagement — reviews per region
SELECT
    c.region,
    COUNT(r.review_id)          AS total_reviews,
    ROUND(AVG(r.rating), 2)     AS avg_rating
FROM customers c
LEFT JOIN reviews r ON c.customer_id = r.customer_id
GROUP BY c.region
ORDER BY total_reviews DESC;
 
-- Q5: Keyword frequency — count reviews mentioning key terms
SELECT
    SUM(CASE WHEN LOWER(comments) LIKE '%delivery%' THEN 1 ELSE 0 END) AS delivery_mentions,
    SUM(CASE WHEN LOWER(comments) LIKE '%quality%'  THEN 1 ELSE 0 END) AS quality_mentions,
    SUM(CASE WHEN LOWER(comments) LIKE '%service%'  THEN 1 ELSE 0 END) AS service_mentions,
    SUM(CASE WHEN LOWER(comments) LIKE '%price%'    THEN 1 ELSE 0 END) AS price_mentions,
    SUM(CASE WHEN LOWER(comments) LIKE '%excellent%' OR
                  LOWER(comments) LIKE '%great%' OR
                  LOWER(comments) LIKE '%good%'  THEN 1 ELSE 0 END)    AS positive_keyword_mentions,
    SUM(CASE WHEN LOWER(comments) LIKE '%late%' OR
                  LOWER(comments) LIKE '%poor%' OR
                  LOWER(comments) LIKE '%average%' THEN 1 ELSE 0 END)  AS negative_keyword_mentions
FROM reviews;
 
-- Q6: Top-performing products (avg rating >= 4, min 1 review)
SELECT
    p.product_id,
    p.name,
    p.category,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(*) AS review_count
FROM products p
JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category
HAVING avg_rating >= 4
ORDER BY avg_rating DESC;
 
-- ============================================================
-- PART F: VIEW — Joined customer + product + review data
-- ============================================================
CREATE OR REPLACE VIEW v_full_feedback AS
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
    CASE
        WHEN r.rating >= 4 THEN 'Positive'
        WHEN r.rating = 3  THEN 'Neutral'
        ELSE 'Negative'
    END AS sentiment_label
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
LEFT JOIN products p ON r.product_id = p.product_id;
 
-- View: top-rated products
CREATE OR REPLACE VIEW v_top_rated_products AS
SELECT
    p.product_id,
    p.name,
    p.category,
    COUNT(r.review_id)          AS review_count,
    ROUND(AVG(r.rating), 2)     AS avg_rating
FROM products p
JOIN reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category
HAVING avg_rating >= 4
ORDER BY avg_rating DESC;
 
-- View: flagged (low-rating) reviews
CREATE OR REPLACE VIEW v_flagged_reviews AS
SELECT
    r.review_id,
    c.name AS customer_name,
    c.email,
    r.rating,
    r.comments,
    r.source,
    r.review_date
FROM reviews r
JOIN customers c ON r.customer_id = c.customer_id
WHERE r.rating <= 2
ORDER BY r.rating ASC;
 
-- ============================================================
-- PART G: Stored Procedure — Automate data integration
-- ============================================================
DELIMITER $$
 
CREATE PROCEDURE IF NOT EXISTS sp_integrate_all_sources()
BEGIN
    -- Move survey data from temp to permanent tables
    INSERT IGNORE INTO customers (customer_id, name, email, region)
    SELECT customer_id, name, email, region FROM temp_survey;
 
    -- Move web JSON data
    INSERT INTO reviews (customer_id, product_id, rating, comments, review_date, source)
    SELECT payload->>'$.customer_id', 2,
           payload->>'$.rating', payload->>'$.comments', CURDATE(), 'web'
    FROM raw_web_feedback;
 
    -- Move XML data
    INSERT INTO reviews (customer_id, product_id, rating, comments, review_date, source)
    SELECT customer_id, 3, rating, comments, CURDATE(), 'external'
    FROM raw_xml_reviews;
 
    SELECT 'Integration complete' AS status;
END$$
 
DELIMITER ;
 
-- ============================================================
-- PART H: Validation queries
-- ============================================================
 
-- Row counts
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL
SELECT 'products',  COUNT(*) FROM products
UNION ALL
SELECT 'reviews',   COUNT(*) FROM reviews;
 
-- Confirm no orphaned reviews (FK integrity check)
SELECT COUNT(*) AS orphaned_reviews
FROM reviews r
LEFT JOIN customers c ON r.customer_id = c.customer_id
WHERE c.customer_id IS NULL;
 
-- Rating distribution
SELECT rating, COUNT(*) AS count FROM reviews GROUP BY rating ORDER BY rating;