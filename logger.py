import logging

logger = logging.getLogger("ai_sql_app")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("app.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
