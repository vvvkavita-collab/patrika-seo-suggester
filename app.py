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
st.title("📰 Patrika SEO News Rewriter (Hindi) – No-AI Improved Version")

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
            r"Published.*?\d{4}",
            r"Updated.*?\d{4}",
            r"By\s+[A-Za-z ]+",
            r"\(IANS\)|\(ANI\)|\(PTI\)",
            r"Photo.*?:", r"Image.*?:",
            r"posted\s+by.*",
            r"2 min read",
            r"\d{1,2} [A-Za-z]+ \d{4}",
            r"•\s+\w+",
            r"पत्रिका|स्पेशल|ई-पेपर|मेरी खबर|शॉर्ट्स|वीडियोज़"
        ]

        for p in patterns:
            clean_text = re.sub(p, "", clean_text, flags=re.IGNORECASE)

        return clean_text.strip()

    except Exception as e:
        return f"Error extracting content: {str(e)}"

# --------------------------------------
# MANUAL CLEAN & STRUCTURE FUNCTION
# --------------------------------------
def rewrite_news_manual(raw_text):
    # 1. Split into sentences
    sentences = re.split(r'[।!?]', raw_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # 2. Group into paragraphs (2–3 sentences each)
    paragraphs = []
    i = 0
    while i < len(sentences):
        para = '। '.join(sentences[i:i+3]) + '।'
        paragraphs.append(para)
        i += 3
        if len(paragraphs) >= 7:
            break

    # 3. Add placeholder H2 subheadings
    subheadings = []
    for idx in range(len(paragraphs)):
        subheadings.append(f"### Subheading {idx+1}")

    # 4. Titles (first 3 meaningful sentences)
    titles = []
    for s in sentences[:10]:
        if len(titles) < 3:
            titles.append(s.strip()[:80])

    # 5. Meta description (first 140–160 chars)
    meta = ' '.join(sentences[:5])
    meta = meta[:160].rstrip() + '…' if len(meta) > 160 else meta

    # 6. URL Slug
    stopwords = ['का','की','के','और','से','है','हैं','में','पर','कि']
    words = re.findall(r'\w+', raw_text)
    slug_words = [w for w in words[:10] if w not in stopwords]
    if transliteration_available:
        slug = '-'.join([transliterate(w, sanscript.DEVANAGARI, sanscript.ITRANS) for w in slug_words])
    else:
        slug = '-'.join(slug_words)

    # 7. Keywords (top meaningful words)
    words_filtered = [w for w in words if len(w) > 2 and w not in stopwords]
    freq = Counter(words_filtered)
    keywords = [w for w,_ in freq.most_common(10)]

    # 8. Format output
    output = "### Suggested Titles (3 options)\n"
    for idx, t in enumerate(titles,1):
        output += f"{idx}. {t}\n"

    output += f"\n### SEO Meta (140–160 chars)\n{meta}\n"
    output += f"\n### Suggested URL Slug\n{slug}\n"
    output += f"\n### Suggested Keywords\n{', '.join(keywords)}\n"
    output += f"\n### Rewritten Full Article\n"

    for idx, para in enumerate(paragraphs,1):
        output += f"{subheadings[idx-1]}\nParagraph {idx}:\n{para}\n\n"

    return output

# --------------------------------------
# REWRITE NEWS FUNCTION (No-AI)
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
st.caption("Rajasthan Patrika – SEO Hindi News Rewriter | No-AI Improved Version")
