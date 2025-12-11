import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from openai import OpenAI

# --------------------------------------
# SETUP
# --------------------------------------
st.set_page_config(page_title="Patrika – SEO News Rewriter", layout="wide")
st.title("📰 Patrika SEO News Rewriter (Hindi) – FINAL VERSION")

# Insert your API Key here
OPENAI_API_KEY = "YOUR_OPENAI_KEY_HERE"
client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------------------------
# CLEAN HTML FUNCTION
# --------------------------------------
def clean_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")

    # REMOVE unwanted tags
    for tag in soup(["script", "style", "noscript", "footer", "header", "form", "nav"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    # REMOVE repeated whitespaces
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

        # Remove author/date/posted on/photo credits patterns
        patterns = [
            r"Published.*?\d{4}",
            r"Updated.*?\d{4}",
            r"By\s+[A-Za-z ]+",
            r"\(IANS\)", r"\(ANI\)", r"\(PTI\)",
            r"Photo.*?:", r"Image.*?:",
            r"posted\s+by.*",
        ]

        for p in patterns:
            clean_text = re.sub(p, "", clean_text, flags=re.IGNORECASE)

        return clean_text.strip()

    except Exception as e:
        return f"Error extracting content: {str(e)}"


# --------------------------------------
# REWRITE NEWS (PATRIAK SEO ENGINE)
# --------------------------------------
def rewrite_news_patrika_style(raw_text):
    system_prompt = """
    You are an expert senior news editor for Rajasthan Patrika.
    Rewrite any given news article in pure Hindi (Patrika newsroom tone)
    using SEO and Google News guidelines.

    STRICT RULES:
    ------------------------------------------------
    ❌ Do NOT include:
    - author name
    - date/time
    - photo credit
    - agency name (IANS, PTI, ANI)
    - phrases like "Published on", "Updated", "Photo"
    - social share lines
    - notes, bullets
    - JSON-LD, HTML code, schema
    - filler lines
    - Paragraph 8/9/10 if news ends earlier

    ✔ MUST include:
    ------------------------------------------------
    - 3 SEO friendly titles (Hindi)
    - Single 140–160 char meta description
    - Clean SEO slug (hindi-translit, no stopwords)
    - 6–10 keywords (topic based only)
    - 2–3 H2 subheadings (SEO friendly)
    - Full rewritten article (Hindi Patrika Style)
    - 5–7 paragraphs (2–3 lines each)
    - No single-line paragraph allowed
    - No agency/source/author anywhere

    OUTPUT FORMAT EXACTLY AS BELOW:
    ------------------------------------------------
    ### Suggested Titles (3 options)
    1.
    2.
    3.

    ### SEO Meta (140–160 chars)

    ### Suggested URL Slug

    ### Suggested Keywords

    ### Suggested Headings (H2 + 1-line intro)

    ### Rewritten Full Article
    Paragraph 1:
    Paragraph 2:
    Paragraph 3:
    Paragraph 4:
    Paragraph 5:
    Paragraph 6:
    Paragraph 7: (only if needed)
    """

    user_prompt = f"""
    Rewrite the following news article into Patrika Hindi style:

    {raw_text}
    """

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

if st.button("Rewrite News (Patrika Style)"):
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
st.caption("Rajasthan Patrika – SEO Hindi News Rewriter | Final Optimized Version")
