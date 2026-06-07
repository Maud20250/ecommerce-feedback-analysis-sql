"""
parse_data.py  (corrected version)
====================================
Final Project Part 1 – Data Parsing & Integration
- Automatically creates staging tables if they do not exist
- Duplicate protection on every run
- Parses CSV, JSON, and XML then loads into MySQL
 
Usage:
    python parse_data.py
 
Requirements:
    pip install mysql-connector-python
"""
 
import csv
import json
import xml.etree.ElementTree as ET
import mysql.connector
from datetime import date
 
# ── Database configuration ───────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "Pasto@2025",   # <-- update with your MySQL password
    "database": "ecommerce_feedback"
}
 
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)
 
 
# ── STEP 0: Create staging tables if they do not exist ──────────────────────
def create_staging_tables() -> None:
    """
    Creates raw_web_feedback and raw_xml_reviews if they do not already exist.
    Safe to run multiple times — will never overwrite existing data.
    """
    conn   = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_web_feedback (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            payload JSON
        )
    """)
 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_xml_reviews (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT,
            rating      INT,
            comments    TEXT
        )
    """)
 
    conn.commit()
    cursor.close()
    conn.close()
    print("[SETUP] Staging tables verified / created.")
 
 
# ── 1. Parse CSV (customer_survey.csv) ──────────────────────────────────────
def parse_and_load_csv(filepath: str) -> None:
    """
    Reads customer_survey.csv and inserts data into customers and reviews.
    Duplicate protection:
      - customers : INSERT IGNORE (based on customer_id)
      - reviews   : checks that no identical review (customer_id + source
                    + comments) already exists before inserting
    """
    conn   = get_connection()
    cursor = conn.cursor()
 
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        customers_inserted = 0
        reviews_inserted   = 0
        reviews_skipped    = 0
 
        for row in reader:
            # --- Customer: INSERT IGNORE prevents duplicates on customer_id ---
            cursor.execute(
                """
                INSERT IGNORE INTO customers (customer_id, name, email, region)
                VALUES (%s, %s, %s, %s)
                """,
                (row["customer_id"], row["name"], row["email"], row["region"])
            )
            customers_inserted += cursor.rowcount
 
            # --- Review: check if this review already exists ---
            cursor.execute(
                """
                SELECT COUNT(*) FROM reviews
                WHERE customer_id = %s AND source = 'survey'
                AND comments = %s
                """,
                (row["customer_id"], row["comments"].strip())
            )
            already_exists = cursor.fetchone()[0]
 
            if already_exists == 0:
                cursor.execute(
                    """
                    INSERT INTO reviews
                        (customer_id, product_id, rating, comments, review_date, source)
                    VALUES (%s, %s, %s, %s, %s, 'survey')
                    """,
                    (row["customer_id"], 1, int(row["rating"]),
                     row["comments"].strip(), row["review_date"])
                )
                reviews_inserted += 1
            else:
                reviews_skipped += 1
 
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[CSV]  {customers_inserted} customers inserted, "
          f"{reviews_inserted} reviews inserted, "
          f"{reviews_skipped} duplicates skipped.")
 
 
# ── 2. Parse JSON (web_feedback.json) ────────────────────────────────────────
def parse_and_load_json(filepath: str) -> None:
    """
    Reads web_feedback.json and inserts into raw_web_feedback + reviews.
    Duplicate protection: checks that the customer_id does not already
    have a review with source='web' and the same comments before inserting.
    """
    conn   = get_connection()
    cursor = conn.cursor()
 
    with open(filepath, encoding="utf-8") as f:
        records = json.load(f)
 
    reviews_inserted = 0
    reviews_skipped  = 0
 
    for record in records:
        # Validate required fields
        if not all(k in record for k in ("customer_id", "rating", "comments")):
            print(f"  [WARN] Incomplete record skipped: {record}")
            continue
 
        # Duplicate check
        cursor.execute(
            """
            SELECT COUNT(*) FROM reviews
            WHERE customer_id = %s AND source = 'web'
            AND comments = %s
            """,
            (record["customer_id"], record["comments"].strip())
        )
        already_exists = cursor.fetchone()[0]
 
        if already_exists == 0:
            # Store raw payload for audit trail
            cursor.execute(
                "INSERT INTO raw_web_feedback (payload) VALUES (%s)",
                (json.dumps(record),)
            )
            # Insert into reviews
            cursor.execute(
                """
                INSERT INTO reviews
                    (customer_id, product_id, rating, comments, review_date, source)
                VALUES (%s, %s, %s, %s, %s, 'web')
                """,
                (record["customer_id"], 2, int(record["rating"]),
                 record["comments"].strip(), date.today().isoformat())
            )
            reviews_inserted += 1
        else:
            reviews_skipped += 1
 
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[JSON] {reviews_inserted} reviews inserted, "
          f"{reviews_skipped} duplicates skipped.")
 
 
# ── 3. Parse XML (external_reviews.xml) ─────────────────────────────────────
def parse_and_load_xml(filepath: str) -> None:
    """
    Reads external_reviews.xml and inserts into raw_xml_reviews + reviews.
    Duplicate protection: same logic as JSON.
    """
    conn   = get_connection()
    cursor = conn.cursor()
 
    tree = ET.parse(filepath)
    root = tree.getroot()
 
    reviews_inserted = 0
    reviews_skipped  = 0
 
    for review_elem in root.findall("review"):
        customer_id = review_elem.findtext("customer_id")
        rating      = review_elem.findtext("rating")
        comments    = review_elem.findtext("comments", default="").strip()
 
        if not customer_id or not rating:
            print(f"  [WARN] Incomplete XML element skipped.")
            continue
 
        # Duplicate check
        cursor.execute(
            """
            SELECT COUNT(*) FROM reviews
            WHERE customer_id = %s AND source = 'external'
            AND comments = %s
            """,
            (int(customer_id), comments)
        )
        already_exists = cursor.fetchone()[0]
 
        if already_exists == 0:
            # Staging
            cursor.execute(
                """
                INSERT INTO raw_xml_reviews (customer_id, rating, comments)
                VALUES (%s, %s, %s)
                """,
                (int(customer_id), int(rating), comments)
            )
            # Reviews
            cursor.execute(
                """
                INSERT INTO reviews
                    (customer_id, product_id, rating, comments, review_date, source)
                VALUES (%s, %s, %s, %s, %s, 'external')
                """,
                (int(customer_id), 3, int(rating), comments,
                 date.today().isoformat())
            )
            reviews_inserted += 1
        else:
            reviews_skipped += 1
 
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[XML]  {reviews_inserted} reviews inserted, "
          f"{reviews_skipped} duplicates skipped.")
 
 
# ── 4. Final validation ──────────────────────────────────────────────────────
def validate_load() -> None:
    """Prints row counts and rating distribution after loading."""
    conn   = get_connection()
    cursor = conn.cursor()
 
    tables = ["customers", "products", "reviews"]
    print("\n── Row counts ──────────────────────────")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:<15} {cursor.fetchone()[0]:>6} rows")
 
    # Orphan check
    cursor.execute("""
        SELECT COUNT(*) FROM reviews r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """)
    orphans = cursor.fetchone()[0]
    print(f"\n  Reviews with no matching customer: {orphans}")
 
    # Rating distribution
    cursor.execute(
        "SELECT rating, COUNT(*) FROM reviews GROUP BY rating ORDER BY rating"
    )
    print("\n── Rating distribution ──────────────────")
    labels = {1: "Very Bad", 2: "Bad", 3: "Average", 4: "Good", 5: "Excellent"}
    for rating, cnt in cursor.fetchall():
        bar   = "█" * cnt
        label = labels.get(rating, "?")
        print(f"  {rating} ({label:<10}) {bar} ({cnt})")
 
    cursor.close()
    conn.close()
 
 
# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    CSV_FILE  = "customer_survey.csv"
    JSON_FILE = "web_feedback.json"
    XML_FILE  = "external_reviews.xml"
 
    print("Starting data integration...\n")
 
    create_staging_tables()        # Step 0: create tables if needed
    parse_and_load_csv(CSV_FILE)   # Step 1: CSV
    parse_and_load_json(JSON_FILE) # Step 2: JSON
    parse_and_load_xml(XML_FILE)   # Step 3: XML
    validate_load()                # Step 4: validation
 
    print("\nData integration complete.")