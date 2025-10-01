import os
import re
import pandas as pd
from sqlalchemy import create_engine, inspect, text
import google.generativeai as genai

from dotenv import load_dotenv

load_dotenv()


DB_URL      = os.getenv("DB_URL", "sqlite:///./agents.db")
CSV_PATH  = "./news.csv"
TABLE       = "news"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL       = 'gemini-2.0-flash-001'


engine = create_engine(DB_URL, echo=False)
insp   = inspect(engine)

def table_has_data(name: str) -> bool:
    if not insp.has_table(name):
        return False
    with engine.connect() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(1) FROM \"{name}\"")
        ).scalar_one()
    return count > 0

def standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    df_clean = df.copy()
    

    timestamp_cols = ['timestamp', 'original_timestamp']
    for col in timestamp_cols:
        if col in df_clean.columns:
          
            df_clean[col] = pd.to_datetime(
                df_clean[col],
                format='%d-%m-%y %H:%M',
                errors='coerce'
            )
    
            df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M')
            print(df_clean[col])

    if 'created_at' in df_clean.columns:
        df_clean['created_at'] = df_clean['created_at'].astype(str).str.strip()
    
    if 'sentiment' in df_clean.columns:
        df_clean['sentiment'] = (df_clean['sentiment']
                                 .astype(str)
                                 .str.lower()
                                 .str.strip()
                                 .replace('nan', None))
    
    numeric_cols = ['total_engagement', 'id', 'news_id']
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    

    if 'source_country' in df_clean.columns:
        df_clean['source_country'] = (df_clean['source_country']
                                      .astype(str)
                                      .str.lower()
                                      .str.strip())
    
    if 'article_language' in df_clean.columns:
        df_clean['article_language'] = (df_clean['article_language']
                                        .astype(str)
                                        .str.lower()
                                        .str.strip())
    
    url_cols = ['url', 'image_url']
    for col in url_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
            df_clean[col] = df_clean[col].replace('nan', None)
    
    text_cols = ['title', 'article_content', 'summary', 'author', 'authors'
                 ]
    for col in text_cols:
        if col in df_clean.columns:
            df_clean[col] = (df_clean[col]
                            .astype(str)
                            .str.lower()
                            .str.strip()
                            .replace('nan', None))
    
    id_cols = ['search_id']
    for col in id_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
    
    return df_clean


if not table_has_data(TABLE):

    df = pd.read_csv(CSV_PATH)
    df = standardize_dataframe(df)
    df.to_sql(TABLE, engine, if_exists="replace", index=False)


with engine.connect() as conn:
    info = conn.execute(text(f"PRAGMA table_info(\"{TABLE}\");")).all()
columns = [col[1] for col in info]


def ask_gemini(messages: list[dict]) -> str:

    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(messages[0]["content"])
    return response.text


def clean_sql(raw: str) -> str:

    raw = re.sub(r'^```(?:sql)?\s*\n?', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\n?```\s*$', '', raw)
    return raw.strip()

def quote_identifiers_and_aliases(sql: str) -> str:
    sql = re.sub(rf"\b{re.escape(TABLE)}\b", f'"{TABLE}"', sql)
    for col in sorted(columns, key=len, reverse=True):
        sql = re.sub(rf"\b{re.escape(col)}\b", f'"{col}"', sql)
    sql = re.sub(r"\bAS\s+([A-Za-z0-9_]+)", r'AS "\1"', sql, flags=re.IGNORECASE)
    return sql

def generate_sql(user_q: str) -> str:
    prompt = f"""
You have a SQL table called "{TABLE}" with these columns exactly as named:
{', '.join(columns)}

User's request: "{user_q}"

IMPORTANT: All text data in the database is stored in LOWERCASE. When filtering by text values:
- Always use LOWERCASE in WHERE clauses (e.g., WHERE sentiment = 'positive', not 'Positive')
- For text comparisons, the values should be lowercase

When writing your query:
- Use *exactly* those column names.
- If a name contains spaces or special characters, *wrap it in double quotes*.
- When filtering or aggregating by year (e.g. user asks for 2024), use the appropriate full-year.
- Use standard SQL aggregations (SUM, AVG, GROUP BY, etc.) as needed.
- ALL text values in WHERE clauses must be lowercase.

*Output only the SQL query*, with no markdown fences or extra text.
""".strip()

    raw_sql = ask_gemini([{"role": "user", "content": prompt}])
    return clean_sql(raw_sql)


def summarize_paragraph(df: pd.DataFrame, user_q: str) -> str:
    records = df.to_dict(orient="records")
    prompt = f"""
You are a data‐driven assistant.  
User's question:
"{user_q}"

Query results (as JSON):
{records}

Write exactly one concise but detailed paragraph that:
1. Answers the user's question directly using only the fields provided.  
2. Never mention raw JSON keys.  
3. Use full sentences and proper grammar.  
4. *If the user asked for a specific year*, use only data from that year.
5. *If the user asked for a comparison*, compare only the fields provided.
6. *If the user asked for a trend*, describe only the trend in the data provided.
7. *Do not introduce or reference any data, years, or context* not present in the JSON.
8. If the data is insufficient to answer the question, say so clearly.
9. If number then return as digits not words.
10. Provide a well-structured, comprehensive response.

Output only the final paragraph. Be as detailed as possible.

""".strip()
    return ask_gemini([{"role": "user", "content": prompt}])


if __name__ == "__main__":
    user_q = input("What would you like to know? ").strip()

    sql = generate_sql(user_q)
    if not sql.upper().startswith("SELECT"):
        raise RuntimeError(f"Invalid SQL generated:\n{sql}")

    df = pd.read_sql(text(sql), engine)
    print(f"[RESULTS] Returned {len(df)} row(s)\n")

    print("[SUMMARY]\n", summarize_paragraph(df, user_q))