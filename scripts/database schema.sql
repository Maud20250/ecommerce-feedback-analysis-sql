-- ============================================================
-- Final Project Part 1 - Database Schema
-- E-Commerce Customer Feedback Analysis
-- ============================================================
 
-- Create and use database
CREATE DATABASE IF NOT EXISTS ecommerce_feedback;
USE ecommerce_feedback;
 
-- ============================================================
-- TABLE 1: customers
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    customer_id   INT           NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)  NOT NULL,
    email         VARCHAR(150)  NOT NULL UNIQUE,
    region        VARCHAR(50),
    PRIMARY KEY (customer_id)
);
 
-- ============================================================
-- TABLE 2: products
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    product_id    INT           NOT NULL AUTO_INCREMENT,
    name          VARCHAR(150)  NOT NULL,
    category      VARCHAR(100),
    price         DECIMAL(10,2),
    PRIMARY KEY (product_id)
);
 
-- ============================================================
-- TABLE 3: reviews
-- ============================================================
CREATE TABLE IF NOT EXISTS reviews (
    review_id     INT           NOT NULL AUTO_INCREMENT,
    customer_id   INT           NOT NULL,
    product_id    INT,
    rating        TINYINT       CHECK (rating BETWEEN 1 AND 5),
    comments      TEXT,
    review_date   DATE,
    source        VARCHAR(50)   DEFAULT 'survey',  -- 'survey','web','external'
    PRIMARY KEY (review_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
 
-- ============================================================
-- INDEXES for optimized query performance
-- ============================================================
CREATE INDEX idx_reviews_customer  ON reviews (customer_id);
CREATE INDEX idx_reviews_product   ON reviews (product_id);
CREATE INDEX idx_reviews_rating    ON reviews (rating);
CREATE INDEX idx_reviews_date      ON reviews (review_date);
CREATE INDEX idx_customers_region  ON customers (region);
 
-- ============================================================
-- Sample product catalogue (required for FK integrity)
-- ============================================================
INSERT INTO products (product_id, name, category, price) VALUES
(1, 'Wireless Headphones',  'Electronics',   79.99),
(2, 'Running Shoes',         'Footwear',      59.99),
(3, 'Kitchen Blender',       'Appliances',    49.99);