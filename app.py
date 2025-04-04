import streamlit as st
from config import DB_CONFIG, GCP_PROJECT_ID, VERTEX_MODEL_NAME
from logger import logger
from sql_validator import validate_sql
from cache import get_cached_result, cache_result
from utils.query_utils import run_sql_query, display_query_result
from google.cloud import aiplatform
from langchain.llms import VertexAI
import os

st.set_page_config(page_title="AI SQL Insights", layout="wide")
st.title("Ask Questions on Your Data")

aiplatform.init(project=GCP_PROJECT_ID)
llm = VertexAI(model=VERTEX_MODEL_NAME)

user_query = st.text_input("Ask a question about the data:")
if st.button("Get Insights") and user_query:
    try:
        with st.spinner("Generating SQL..."):
            prompt = f"Generate SQL for the following user question:
{user_query}
Use PostgreSQL syntax."
            generated_sql = llm.predict(prompt)
            st.code(generated_sql, language='sql')

            if validate_sql(generated_sql):
                cache_key = hash(generated_sql)
                cached = get_cached_result(cache_key)
                if cached:
                    st.success("Loaded from cache")
                    display_query_result(cached)
                else:
                    result_df = run_sql_query(generated_sql)
                    cache_result(cache_key, result_df)
                    display_query_result(result_df)
            else:
                st.error("SQL failed validation.")
    except Exception as e:
        logger.exception("Error during processing")
        st.error(f"An error occurred: {str(e)}")
