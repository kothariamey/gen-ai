import pandas as pd
import psycopg2
from config import DB_CONFIG
from logger import logger
import streamlit as st
import plotly.express as px

def run_sql_query(sql: str) -> pd.DataFrame:
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            df = pd.read_sql(sql, conn)
            return df
    except Exception as e:
        logger.error("Query execution failed: %s", e)
        raise

def display_query_result(df: pd.DataFrame):
    st.dataframe(df)
    if df.shape[1] >= 2:
        st.plotly_chart(px.line(df, x=df.columns[0], y=df.columns[1]), use_container_width=True)
