import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter

# ------------------- TRANSLITERATION SAFE -------------------
try:
    from indic_transliteration import sanscript, transliterate
    transliteration_available = True
except ImportError:
    transliteration_available = False

# --------------------------------------
# SETUP
# --------------------------------------
st.set_page_config(page_title="Patrika – SEO News Rewriter", layout="wide")
st.title("📰 Patrika SEO News Rewriter (Hindi) – NO-AI VERSION")

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
# MANUAL REWRITE FUNCTION (NO-AI)
# --------------------------------------
def rewrite_news_manual(raw_text):
    # 1. Split into sentences
    sentences = re.split(r'[।!?]', raw_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # 2. Group into paragraphs (2 sentences per paragraph)
    paragraphs = []
    i = 0
    while i < len(sentences):
        para = '। '.join(sentences[i:i+2]) + '।'
        paragraphs.append(para)
        i += 2
        if len(paragraphs) >= 7:
            break

    # 3. SEO Titles (first 3 main sentences)
    titles = [s[:60] for s in sentences[:3]]

    # 4. Meta description (140–160 chars)
    meta = ' '.join(sentences[:3])[:160]

    # 5. URL Slug (Hindi translit + remove stopwords)
    stopwords = ['का','की','के','और','से','है','हैं','में','पर','कि']
    words = re.findall(r'\w+', raw_text)
    slug_words = [w for w in words[:10] if w not in stopwords]

    if transliteration_available:
        slug = '-'.join([transliterate(w, sanscript.DEVANAGARI, sanscript.ITRANS) for w in slug_words])
    else:
        slug = '-'.join(slug_words)  # fallback

    # 6. Keywords (top 6–10 frequent words)
    freq = Counter(words)
    keywords = [w for w,_ in freq.most_common(10)]

    # 7. Format output
    output = "### Suggested Titles (3 options)\n"
    for idx, t in enumerate(titles,1):
        output += f"{idx}. {t}\n"

    output += f"\n### SEO Meta (140–160 chars)\n{meta}\n"
    output += f"\n### Suggested URL Slug\n{slug}\n"
    output += f"\n### Suggested Keywords\n{', '.join(keywords)}\n"
    output += f"\n### Rewritten Full Article\n"
    for idx, para in enumerate(paragraphs,1):
        output += f"Paragraph {idx}:\n{para}\n"

    return output


# --------------------------------------
# REWRITE NEWS FUNCTION (No-AI wrapper)
# --------------------------------------
def rewrite_news_patrika_style(raw_text):
    return rewrite_news_manual(raw_text)


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
st.caption("Rajasthan Patrika – SEO Hindi News Rewriter | No-AI Version")
