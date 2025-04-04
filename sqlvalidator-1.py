import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML
import psycopg2
import psycopg2.extras
from config import DB_CONFIG
from logger import log_info, log_error

# Allowed tables (Modify as per your schema)
ALLOWED_TABLES = ["orders", "customers", "sales", "transactions"]
READ_ONLY_KEYWORDS = {"SELECT", "WITH"}

def extract_table_names(query):
    """Extracts table names from SQL query"""
    try:
        parsed = sqlparse.parse(query)
        tables = set()

        for statement in parsed:
            for token in statement.tokens:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        tables.add(identifier.get_real_name())
                elif isinstance(token, Identifier):
                    tables.add(token.get_real_name())

        return tables
    except Exception as e:
        log_error("Error extracting tables from SQL")
        return set()

def estimate_query_cost(query):
    """Executes EXPLAIN ANALYZE to estimate query cost"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(f"EXPLAIN {query}")
        plan = cur.fetchall()
        conn.close()

        cost_line = [line[0] for line in plan if "cost=" in line[0]][0]
        cost = float(cost_line.split("cost=")[1].split("..")[1].split(" ")[0])
        return cost
    except Exception as e:
        log_error("Error estimating query cost")
        return None

def is_valid_sql(query):
    """Validates SQL for security, performance, and cost estimation"""
    try:
        parsed = sqlparse.parse(query)
        for statement in parsed:
            if not any(token.value.upper() in READ_ONLY_KEYWORDS for token in statement.tokens if token.ttype == Keyword):
                return False, "Only SELECT queries are allowed."

            # Check for full-table scans (SELECT * with no WHERE)
            if "SELECT *" in query.upper() and "WHERE" not in query.upper():
                return False, "Full table scan detected. Use WHERE clause."

            # Ensure at least one indexed column is in WHERE
            tables = extract_table_names(query)
            if not tables.issubset(set(ALLOWED_TABLES)):
                return False, f"Unauthorized table access: {tables - set(ALLOWED_TABLES)}"

            # Ensure LIMIT is present for large queries
            if "LIMIT" not in query.upper():
                return False, "LIMIT clause is required to avoid excessive data retrieval."

            # Estimate query cost
            cost = estimate_query_cost(query)
            if cost and cost > 10000:
                return False, f"Query execution cost too high: {cost}. Optimize query."

        return True, "Query is valid."
    
    except Exception as e:
        log_error("SQL validation error")
        return False, f"Validation error: {str(e)}"



-------
from rate_limiter import limiter
import psycopg2
import psycopg2.extras
from config import DB_CONFIG
from logger import log_info, log_error

COST_THRESHOLD = 10000  # Maximum allowed cost

def estimate_query_cost(query, user_ip):
    """Executes EXPLAIN ANALYZE to estimate query cost"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(f"EXPLAIN ANALYZE {query}")
        plan = cur.fetchall()
        conn.close()

        cost_line = [line[0] for line in plan if "cost=" in line[0]][0]
        cost = float(cost_line.split("cost=")[1].split("..")[1].split(" ")[0])

        # Apply rate-limiting if cost is too high
        if cost > COST_THRESHOLD:
            limiter.limit("1 per 5 minutes")(lambda: f"Too many expensive queries, try again later")()
            return False, f"Query execution cost too high: {cost}. Try optimizing it."

        return True, cost
    except Exception as e:
        log_error("Error estimating query cost")
        return False, f"Error in cost estimation: {str(e)}"
---------

import sqlparse
import psycopg2
import psycopg2.extras
from config import DB_CONFIG
from logger import log_info, log_error
from rate_limiter import limiter

ALLOWED_TABLES = ["orders", "customers", "sales", "transactions"]
COST_THRESHOLD = 10000

def extract_table_names(query):
    parsed = sqlparse.parse(query)
    tables = set()
    for statement in parsed:
        for token in statement.tokens:
            if isinstance(token, sqlparse.sql.IdentifierList) or isinstance(token, sqlparse.sql.Identifier):
                tables.add(token.get_real_name())
    return tables

def estimate_query_cost(query, user_ip):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(f"EXPLAIN ANALYZE {query}")
        plan = cur.fetchall()
        conn.close()

        cost_line = [line[0] for line in plan if "cost=" in line[0]][0]
        cost = float(cost_line.split("cost=")[1].split("..")[1].split(" ")[0])

        if cost > COST_THRESHOLD:
            limiter.limit("1 per 5 minutes")(lambda: f"Too many expensive queries, try again later")()
            return False, f"Query cost too high: {cost}. Try optimizing it."

        return True, cost
    except Exception as e:
        log_error("Query cost estimation failed")
        return False, str(e)

def is_valid_sql(query):
    parsed = sqlparse.parse(query)
    for statement in parsed:
        if not any(token.value.upper() in {"SELECT", "WITH"} for token in statement.tokens if token.ttype == sqlparse.tokens.Keyword):
            return False, "Only SELECT queries allowed."

        if "SELECT *" in query.upper() and "WHERE" not in query.upper():
            return False, "Full table scan detected. Use WHERE clause."

        tables = extract_table_names(query)
        if not tables.issubset(set(ALLOWED_TABLES)):
            return False, f"Unauthorized table access: {tables - set(ALLOWED_TABLES)}"

        if "LIMIT" not in query.upper():
            return False, "LIMIT clause is required."

    return True, "Query is valid."
-----------
import sqlparse
import re
import psycopg2
from config import DB_CONFIG
from logger import logger

FORBIDDEN_KEYWORDS = {"DROP", "DELETE", "TRUNCATE", "ALTER"}

def validate_sql(sql: str) -> bool:
    try:
        parsed = sqlparse.parse(sql)[0]
        tokens = [t.value.upper() for t in parsed.tokens if not t.is_whitespace]

        # Check for forbidden operations
        if any(kw in tokens for kw in FORBIDDEN_KEYWORDS):
            logger.warning("Dangerous SQL operation detected.")
            return False

        # Check for SELECT *
        if re.search(r"SELECT\\s+\\*", sql, re.IGNORECASE):
            logger.warning("Avoid using SELECT *")
            return False

        # Warn if missing WHERE
        if "WHERE" not in sql.upper():
            logger.warning("No WHERE clause found — might trigger full scan.")

        # Check for sequential scan via EXPLAIN
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS) {sql}")
                plan = cur.fetchall()
                logger.info("EXPLAIN ANALYZE plan:")
                for row in plan:
                    logger.info(row[0])

                # Basic scan detection
                if any("Seq Scan" in str(row) for row in plan):
                    logger.warning("Sequential scan detected.")
                    return False

                # Optional: Log cost estimation
                for row in plan:
                    match = re.search(r"cost=([0-9.]+)..([0-9.]+)", row[0])
                    if match:
                        start_cost, end_cost = map(float, match.groups())
                        logger.info(f"Query cost: start={start_cost}, end={end_cost}")
                        if end_cost > 10000:
                            logger.warning("Query cost is too high.")
                            return False
        return True

    except Exception as e:
        logger.exception("SQL validation failed")
        return False

