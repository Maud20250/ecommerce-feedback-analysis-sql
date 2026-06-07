"""
parse_data_v2.py
=================
Final Project Part 2 – Data Parsing & Integration (Enhanced Version)
- Full validation: missing fields, date formats, rating ranges
- Structured error logging (parse_errors.log)
- Import summary log (import_summary.log)
- Duplicate detection via SELECT DISTINCT
- Referential integrity checks before insertion
- Handles CSV, JSON, and XML
 
Usage:
    python parse_data_v2.py
 
Requirements:
    pip install mysql-connector-python
"""
 
import csv
import json
import xml.etree.ElementTree as ET
import mysql.connector
import logging
import os
import re
from datetime import date, datetime
 
# ── Logging configuration ────────────────────────────────────────────────────
LOG_DIR = "."
 
# Error log: records every rejected or malformed record
error_logger = logging.getLogger("parse_errors")
error_logger.setLevel(logging.WARNING)
error_handler = logging.FileHandler(os.path.join(LOG_DIR, "parse_errors.log"), mode="w")
error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
error_logger.addHandler(error_handler)
 
# Summary log: records counts after each import step
summary_logger = logging.getLogger("import_summary")
summary_logger.setLevel(logging.INFO)
summary_handler = logging.FileHandler(os.path.join(LOG_DIR, "import_summary.log"), mode="w")
summary_handler.setFormatter(logging.Formatter("%(asctime)s [INFO] %(message)s"))
summary_logger.addHandler(summary_handler)
 
# Console output
console = logging.getLogger("console")
console.setLevel(logging.INFO)
console.addHandler(logging.StreamHandler())
 
# ── Database configuration ────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "Pasto@2025",   
    "database": "ecommerce_feedback"
}
 
 
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)
 
 
# ── Validation helpers ───────────────────────────────────────────────────────
 
def is_valid_date(date_str: str) -> bool:
    """Check that a string matches YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except (ValueError, AttributeError):
        return False
 
 
def is_valid_rating(value) -> bool:
    """Check that rating is an integer between 1 and 5."""
    try:
        r = int(value)
        return 1 <= r <= 5
    except (ValueError, TypeError):
        return False
 
 
def is_valid_email(email: str) -> bool:
    """Basic email format check."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))
 
 
def validate_customer_id_exists(cursor, customer_id: int) -> bool:
    """Verify foreign key: customer must exist in customers table."""
    cursor.execute("SELECT COUNT(*) FROM customers WHERE customer_id = %s", (customer_id,))
    return cursor.fetchone()[0] > 0
 
 
# ── STEP 0: Create staging tables ────────────────────────────────────────────
 
def create_staging_tables() -> None:
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
    console.info("[SETUP] Staging tables verified / created.")
 
 
# ── 1. Parse & Load CSV (customer_survey.csv) ────────────────────────────────
 
def parse_and_load_csv(filepath: str) -> dict:
    """
    Reads customer_survey.csv, validates each row, and inserts into
    customers and reviews tables.
 
    Validation checks:
      - Required fields present (customer_id, name, email, region, rating, comments, review_date)
      - Email format
      - Rating in range 1–5
      - Date format YYYY-MM-DD
    Duplicate detection:
      - customers  : INSERT IGNORE on customer_id
      - reviews    : SELECT DISTINCT check on (customer_id, source, comments)
    """
    stats = {"total": 0, "customers_inserted": 0, "reviews_inserted": 0,
             "skipped_validation": 0, "skipped_duplicate": 0}
 
    conn   = get_connection()
    cursor = conn.cursor()
 
    REQUIRED_FIELDS = {"customer_id", "name", "email", "region",
                        "rating", "comments", "review_date"}
 
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
 
        # Check that all required columns exist in the header
        if not REQUIRED_FIELDS.issubset(set(reader.fieldnames or [])):
            missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
            error_logger.error(f"[CSV] Missing columns in header: {missing}. Aborting CSV import.")
            return stats
 
        for row_num, row in enumerate(reader, start=2):   # row 1 = header
            stats["total"] += 1
            errors = []
 
            # ── Field presence check ────────────────────────────────────────
            for field in REQUIRED_FIELDS:
                if not row.get(field, "").strip():
                    errors.append(f"empty field '{field}'")
 
            # ── Email validation ────────────────────────────────────────────
            if row.get("email") and not is_valid_email(row["email"]):
                errors.append(f"invalid email '{row['email']}'")
 
            # ── Rating range check ──────────────────────────────────────────
            if row.get("rating") and not is_valid_rating(row["rating"]):
                errors.append(f"rating out of range '{row['rating']}'")
 
            # ── Date format check ───────────────────────────────────────────
            if row.get("review_date") and not is_valid_date(row["review_date"]):
                errors.append(f"invalid date '{row['review_date']}'")
 
            if errors:
                error_logger.warning(
                    f"[CSV] Row {row_num} rejected — {'; '.join(errors)} | "
                    f"customer_id={row.get('customer_id', 'N/A')}"
                )
                stats["skipped_validation"] += 1
                continue
 
            # ── INSERT customer (duplicate-safe) ────────────────────────────
            cursor.execute(
                """
                INSERT IGNORE INTO customers (customer_id, name, email, region)
                VALUES (%s, %s, %s, %s)
                """,
                (int(row["customer_id"]), row["name"].strip(),
                 row["email"].strip(), row["region"].strip())
            )
            stats["customers_inserted"] += cursor.rowcount
 
            # ── Duplicate review check (SELECT DISTINCT) ────────────────────
            cursor.execute(
                """
                SELECT COUNT(DISTINCT review_id) FROM reviews
                WHERE customer_id = %s AND source = 'survey' AND comments = %s
                """,
                (int(row["customer_id"]), row["comments"].strip())
            )
            if cursor.fetchone()[0] > 0:
                stats["skipped_duplicate"] += 1
                continue
 
            # ── INSERT review ───────────────────────────────────────────────
            cursor.execute(
                """
                INSERT INTO reviews
                    (customer_id, product_id, rating, comments, review_date, source)
                VALUES (%s, %s, %s, %s, %s, 'survey')
                """,
                (int(row["customer_id"]), 1, int(row["rating"]),
                 row["comments"].strip(), row["review_date"].strip())
            )
            stats["reviews_inserted"] += 1
 
    conn.commit()
    cursor.close()
    conn.close()
 
    msg = (f"[CSV] Total rows={stats['total']} | "
           f"customers_inserted={stats['customers_inserted']} | "
           f"reviews_inserted={stats['reviews_inserted']} | "
           f"skipped_validation={stats['skipped_validation']} | "
           f"skipped_duplicate={stats['skipped_duplicate']}")
    console.info(msg)
    summary_logger.info(msg)
    return stats
 
 
# ── 2. Parse & Load JSON (web_feedback.json) ─────────────────────────────────
 
def parse_and_load_json(filepath: str) -> dict:
    """
    Reads web_feedback.json, validates each record, and inserts into
    raw_web_feedback + reviews.
 
    Validation checks:
      - Required keys: customer_id, rating, comments
      - Rating in range 1–5
      - customer_id must exist in customers (referential integrity)
    """
    stats = {"total": 0, "reviews_inserted": 0,
             "skipped_validation": 0, "skipped_duplicate": 0}
 
    conn   = get_connection()
    cursor = conn.cursor()
 
    with open(filepath, encoding="utf-8") as f:
        try:
            records = json.load(f)
        except json.JSONDecodeError as e:
            error_logger.error(f"[JSON] JSON parse error: {e}. Aborting JSON import.")
            return stats
 
    if not isinstance(records, list):
        error_logger.error("[JSON] Expected a JSON array at root level. Aborting.")
        return stats
 
    for idx, record in enumerate(records):
        stats["total"] += 1
        errors = []
 
        # ── Required key check ──────────────────────────────────────────────
        for key in ("customer_id", "rating", "comments"):
            if key not in record or str(record.get(key, "")).strip() == "":
                errors.append(f"missing/empty key '{key}'")
 
        # ── Rating range check ──────────────────────────────────────────────
        if "rating" in record and not is_valid_rating(record["rating"]):
            errors.append(f"rating out of range '{record['rating']}'")
 
        # ── Referential integrity: customer must exist ──────────────────────
        if "customer_id" in record:
            if not validate_customer_id_exists(cursor, int(record["customer_id"])):
                errors.append(f"customer_id {record['customer_id']} not in customers table")
 
        if errors:
            error_logger.warning(
                f"[JSON] Record #{idx+1} rejected — {'; '.join(errors)} | "
                f"record={record}"
            )
            stats["skipped_validation"] += 1
            continue
 
        # ── Duplicate check (SELECT DISTINCT) ───────────────────────────────
        cursor.execute(
            """
            SELECT COUNT(DISTINCT review_id) FROM reviews
            WHERE customer_id = %s AND source = 'web' AND comments = %s
            """,
            (int(record["customer_id"]), record["comments"].strip())
        )
        if cursor.fetchone()[0] > 0:
            stats["skipped_duplicate"] += 1
            continue
 
        # ── INSERT raw payload ───────────────────────────────────────────────
        cursor.execute(
            "INSERT INTO raw_web_feedback (payload) VALUES (%s)",
            (json.dumps(record),)
        )
 
        # ── INSERT review ────────────────────────────────────────────────────
        cursor.execute(
            """
            INSERT INTO reviews
                (customer_id, product_id, rating, comments, review_date, source)
            VALUES (%s, %s, %s, %s, %s, 'web')
            """,
            (int(record["customer_id"]), 2, int(record["rating"]),
             record["comments"].strip(), date.today().isoformat())
        )
        stats["reviews_inserted"] += 1
 
    conn.commit()
    cursor.close()
    conn.close()
 
    msg = (f"[JSON] Total records={stats['total']} | "
           f"reviews_inserted={stats['reviews_inserted']} | "
           f"skipped_validation={stats['skipped_validation']} | "
           f"skipped_duplicate={stats['skipped_duplicate']}")
    console.info(msg)
    summary_logger.info(msg)
    return stats
 
 
# ── 3. Parse & Load XML (external_reviews.xml) ───────────────────────────────
 
def parse_and_load_xml(filepath: str) -> dict:
    """
    Reads external_reviews.xml, validates each <review> element, and inserts
    into raw_xml_reviews + reviews.
 
    Validation checks:
      - Required elements: customer_id, rating, comments
      - Rating in range 1–5
      - customer_id must exist in customers (referential integrity)
    """
    stats = {"total": 0, "reviews_inserted": 0,
             "skipped_validation": 0, "skipped_duplicate": 0}
 
    conn   = get_connection()
    cursor = conn.cursor()
 
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        error_logger.error(f"[XML] XML parse error: {e}. Aborting XML import.")
        return stats
 
    for elem_num, review_elem in enumerate(root.findall("review"), start=1):
        stats["total"] += 1
        errors = []
 
        customer_id_str = review_elem.findtext("customer_id", default="").strip()
        rating_str      = review_elem.findtext("rating",      default="").strip()
        comments        = review_elem.findtext("comments",    default="").strip()
 
        # ── Required field presence ─────────────────────────────────────────
        if not customer_id_str:
            errors.append("missing <customer_id>")
        if not rating_str:
            errors.append("missing <rating>")
 
        # ── Rating range check ──────────────────────────────────────────────
        if rating_str and not is_valid_rating(rating_str):
            errors.append(f"rating out of range '{rating_str}'")
 
        # ── customer_id must be numeric ─────────────────────────────────────
        try:
            customer_id = int(customer_id_str) if customer_id_str else None
        except ValueError:
            errors.append(f"non-integer customer_id '{customer_id_str}'")
            customer_id = None
 
        # ── Referential integrity ───────────────────────────────────────────
        if customer_id and not validate_customer_id_exists(cursor, customer_id):
            errors.append(f"customer_id {customer_id} not in customers table")
 
        if errors:
            error_logger.warning(
                f"[XML] Element #{elem_num} rejected — {'; '.join(errors)}"
            )
            stats["skipped_validation"] += 1
            continue
 
        # ── Duplicate check (SELECT DISTINCT) ───────────────────────────────
        cursor.execute(
            """
            SELECT COUNT(DISTINCT review_id) FROM reviews
            WHERE customer_id = %s AND source = 'external' AND comments = %s
            """,
            (customer_id, comments)
        )
        if cursor.fetchone()[0] > 0:
            stats["skipped_duplicate"] += 1
            continue
 
        # ── INSERT staging ───────────────────────────────────────────────────
        cursor.execute(
            "INSERT INTO raw_xml_reviews (customer_id, rating, comments) VALUES (%s, %s, %s)",
            (customer_id, int(rating_str), comments)
        )
 
        # ── INSERT review ────────────────────────────────────────────────────
        cursor.execute(
            """
            INSERT INTO reviews
                (customer_id, product_id, rating, comments, review_date, source)
            VALUES (%s, %s, %s, %s, %s, 'external')
            """,
            (customer_id, 3, int(rating_str), comments, date.today().isoformat())
        )
        stats["reviews_inserted"] += 1
 
    conn.commit()
    cursor.close()
    conn.close()
 
    msg = (f"[XML]  Total elements={stats['total']} | "
           f"reviews_inserted={stats['reviews_inserted']} | "
           f"skipped_validation={stats['skipped_validation']} | "
           f"skipped_duplicate={stats['skipped_duplicate']}")
    console.info(msg)
    summary_logger.info(msg)
    return stats
 
 
# ── 4. Final validation & summary ────────────────────────────────────────────
 
def validate_and_summarize() -> None:
    """Prints and logs row counts, orphan checks, and rating distribution."""
    conn   = get_connection()
    cursor = conn.cursor()
 
    lines = ["\n" + "="*45, "IMPORT VALIDATION SUMMARY", "="*45]
 
    # Row counts
    for table in ("customers", "products", "reviews"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        cnt = cursor.fetchone()[0]
        lines.append(f"  {table:<20} {cnt:>6} rows")
 
    # Orphaned reviews (FK integrity)
    cursor.execute("""
        SELECT COUNT(*) FROM reviews r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """)
    orphans = cursor.fetchone()[0]
    lines.append(f"\n  Orphaned reviews (no matching customer): {orphans}")
 
    # Duplicate check via SELECT DISTINCT
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT customer_id, source, comments FROM reviews) d"
    )
    distinct = cursor.fetchone()[0]
    lines.append(f"  Total reviews: {total} | Distinct (customer+source+comment): {distinct}")
    if total != distinct:
        lines.append(f"  ⚠ Possible duplicates detected: {total - distinct}")
 
    # Rating distribution
    cursor.execute("SELECT rating, COUNT(*) FROM reviews GROUP BY rating ORDER BY rating")
    labels = {1: "Very Bad", 2: "Bad", 3: "Average", 4: "Good", 5: "Excellent"}
    lines.append("\n  Rating distribution:")
    for rating, cnt in cursor.fetchall():
        bar = "█" * cnt
        lines.append(f"    {rating} ({labels.get(rating,'?'):<10}) {bar} ({cnt})")
 
    lines.append("="*45)
 
    for line in lines:
        console.info(line)
        summary_logger.info(line)
 
    cursor.close()
    conn.close()
 
 
# ── Main ─────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    CSV_FILE  = "customer_survey.csv"
    JSON_FILE = "web_feedback.json"
    XML_FILE  = "external_reviews.xml"
 
    console.info("=" * 45)
    console.info("  Final Project Part 2 – Data Integration")
    console.info("=" * 45)
 
    create_staging_tables()
 
    all_stats = {}
    all_stats["csv"]  = parse_and_load_csv(CSV_FILE)
    all_stats["json"] = parse_and_load_json(JSON_FILE)
    all_stats["xml"]  = parse_and_load_xml(XML_FILE)
 
    validate_and_summarize()
 
    console.info("\nParsing complete.")
    console.info("  → parse_errors.log  : validation and referential integrity failures")
    console.info("  → import_summary.log: row counts and import statistics")