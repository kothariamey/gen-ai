import sqlparse
import re
import psycopg2
from config import DB_CONFIG
from logger import logger

def validate_sql(sql: str) -> bool:
    parsed = sqlparse.parse(sql)
    tokens = [token for token in parsed[0].flatten()]
    for token in tokens:
        if token.ttype is None and re.match(r".*\*", str(token)):
            logger.warning("Wildcard (*) found in query.")
            return False
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(f"EXPLAIN {sql}")
                plan = cur.fetchall()
                logger.info("EXPLAIN plan: %s", plan)
                if any("Seq Scan" in str(row) for row in plan):
                    logger.warning("Sequential scan detected.")
                    return False
        return True
    except Exception as e:
        logger.error("SQL validation failed: %s", e)
        return False
