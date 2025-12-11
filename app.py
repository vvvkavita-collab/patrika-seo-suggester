import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from openai import OpenAI

# --------------------------------------
# SETUP
# --------------------------------------
st.set_page_config(page_title="Patrika – AI SEO Rewriter", layout="wide")
st.title("📰 Patrika AI SEO News Rewriter (Hindi) – AI-assisted Version")

# Insert your OpenAI API Key
OPENAI_API_KEY = "YOUR_OPENAI_KEY_HERE"
client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------------------------
# CLEAN HTML FUNCTION
# --------------------------------------
def clean_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "footer", "header", "form", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# --------------------------------------
# EXTRACT TEXT FROM URL
# --------------------------------------
def extract_news_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        html = response.text
        clean_text = clean_html(html)
        patterns = [
            r"Published.*?\d{4}", r"Updated.*?\d{4}", r"By\s+[A-Za-z ]+",
            r"\(IANS\)|\(ANI\)|\(PTI\)", r"Photo.*?:", r"Image.*?:",
            r"posted\s+by.*", r"2 min read", r"\d{1,2} [A-Za-z]+ \d{4}",
            r"•\s+\w+", r"पत्रिका|स्पेशल|ई-पेपर|मेरी खबर|शॉर्ट्स|वीडियोज़"
        ]
        for p in patterns:
            clean_text = re.sub(p, "", clean_text, flags=re.IGNORECASE)
        return clean_text.strip()
    except Exception as e:
        return f"Error extracting content: {str(e)}"

# --------------------------------------
# AI Rewrite Function
# --------------------------------------
def rewrite_news_patrika_style(raw_text):
    system_prompt = """
    You are a senior news editor for Rajasthan Patrika.
    Rewrite any given news article in pure Hindi (Patrika newsroom tone)
    using SEO and Google News guidelines.

    STRICT RULES:
    - No author, date, agency, photo credit, social share lines
    - Must include:
      * 3 SEO-friendly titles
      * 140–160 char meta description
      * Clean URL slug (Hindi transliteration)
      * 6–10 topic-based keywords
      * 2–3 H2 subheadings with 1-line intro
      * Full rewritten article (5–7 paragraphs, 2–3 lines each)
    - No single-line paragraphs, no filler
    """

    user_prompt = f"Rewrite the following news article:\n\n{raw_text}"

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    return completion.choices[0].message["content"]

# --------------------------------------
# UI INPUT
# --------------------------------------
url = st.text_input("Paste News URL:")
manual_text = st.text_area("OR Paste Raw News Text Below:")

if st.button("Rewrite News (Patrika AI Style)"):
    if url:
        st.info("Extracting news from URL...")
        extracted = extract_news_from_url(url)
        st.success("News extracted successfully. Rewriting now...")
        final_output = rewrite_news_patrika_style(extracted)
        st.markdown(final_output)

    elif manual_text:
        st.success("Rewriting news...")
        final_output = rewrite_news_patrika_style(manual_text)
        st.markdown(final_output)

    else:
        st.error("Please provide a URL or paste text.")

# FOOTER
st.markdown("---")
st.caption("Rajasthan Patrika – AI-assisted SEO Hindi News Rewriter")
