import redis
import pandas as pd
import pickle
from config import REDIS_HOST, REDIS_PORT, REDIS_DB
from logger import logger

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

def cache_result(key: str, df: pd.DataFrame):
    try:
        redis_client.set(key, pickle.dumps(df))
        logger.info("Result cached successfully")
    except Exception as e:
        logger.error("Caching failed: %s", e)

def get_cached_result(key: str):
    try:
        cached = redis_client.get(key)
        if cached:
            return pickle.loads(cached)
    except Exception as e:
        logger.error("Cache retrieval failed: %s", e)
    return None
