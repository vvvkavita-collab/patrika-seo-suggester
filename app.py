import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import io
import csv
from docx import Document

# -------------------------------
# Utility functions
# -------------------------------

def clean_text(txt: str) -> str:
    return " ".join(txt.replace("\n", " ").split())

def extract_keywords(text: str, n=5):
    words = [w.strip(".,:;!?\"'()[]") for w in text.split()]
    freq = {}
    for w in words:
        if len(w) > 3:
            freq[w.lower()] = freq.get(w.lower(), 0) + 1
    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [k for k, _ in sorted_kw[:n]]

def generate_title(text: str):
    kws = extract_keywords(text, n=3)
    if not kws:
        return "SEO-अनुकूल शीर्षक"
    return f"{kws[0].capitalize()} पर बड़ा बयान, {', '.join(kws[1:])} चर्चा में"

def generate_meta(text: str):
    kws = extract_keywords(text, n=3)
    meta = f"यह खबर {', '.join(kws)} पर केंद्रित है। इसमें मुख्य बयान और प्रतिक्रियाएं शामिल हैं।"
    return meta[:160]

def generate_full_article(text: str):
    paras = text.split(". ")
    article = "#### 🟢 इंट्रोडक्शन\n" + " ".join(paras[:2]) + "\n\n"
    if len(paras) > 2:
        article += "#### 🟠 मुख्य बयान\n" + " ".join(paras[2:4]) + "\n\n"
    if len(paras) > 4:
        article += "#### 🟣 प्रतिक्रियाएं\n" + " ".join(paras[4:6]) + "\n\n"
    article += "#### ⚪ निष्कर्ष\nयह खबर महत्वपूर्ण है और आगे चर्चा का विषय बनेगी।"
    return article

def fetch_page_content(url: str):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])
        return clean_text(text)
    except Exception as e:
        return f"Error fetching page: {e}"

def docx_file(title, meta, article):
    doc = Document()
    doc.add_heading("Patrika SEO Suggester Output", level=1)
    doc.add_heading("Suggested Title", level=2)
    doc.add_paragraph(title)
    doc.add_heading("Suggested Meta", level=2)
    doc.add_paragraph(meta)
    doc.add_heading("Suggested Full Article", level=2)
    doc.add_paragraph(article)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def html_snippet(title, meta, canonical, json_ld):
    return f"""<!-- SEO snippet start -->
<title>{title}</title>
<meta name="description" content="{meta}">
<link rel="canonical" href="{canonical}">
<script type="application/ld+json">
{json_ld}
</script>
<!-- SEO snippet end -->
"""

def schema_json_ld(headline, description, date_published, author, publisher, section):
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": headline,
        "description": description,
        "datePublished": date_published,
        "author": {"@type": "Person", "name": author},
        "publisher": {"@type": "Organization", "name": publisher},
        "articleSection": section,
        "isAccessibleForFree": True
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

def csv_file_row(article_id, reporter, title, meta, section):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ArticleID", "Reporter", "Title", "Meta", "Section"])
    writer.writerow([article_id, reporter, title, meta, section])
    output.seek(0)
    return output

# -------------------------------
# Streamlit UI
# -------------------------------

st.set_page_config(page_title="Patrika SEO Suggester", layout="wide")
st.title("📰 Patrika SEO Suggester")
st.caption("Paste news text OR paste published article link → Get SEO-ready output + downloads")

option = st.radio("Choose input method:", ["Paste News Text", "Paste News URL"])

news_text = ""
if option == "Paste News Text":
    news_text = st.text_area("Paste your news article here:", height=250)
elif option == "Paste News URL":
    url = st.text_input("Paste published article URL:")
    if url:
        st.info("Fetching content from URL...")
        news_text = fetch_page_content(url)

if st.button("Analyze & Suggest", type="primary") and news_text.strip():
    body = clean_text(news_text)
    suggested_title = generate_title(body)
    suggested_meta = generate_meta(body)
    full_article = generate_full_article(body)
    date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
    schema = schema_json_ld(suggested_title, suggested_meta, date_published, "Patrika News Desk", "Rajasthan Patrika", "National")
    canonical_url = "https://www.patrika.com/national/" + "sample-slug"

    st.success("✅ SEO Suggestions Generated")

    st.markdown("### 🏷 Suggested Title (as per Google SEO guideline)")
    st.write(suggested_title)

    st.markdown("### 📝 Suggested Meta Description (as per Google SEO guideline)")
    st.write(suggested_meta)

    st.markdown("### 📄 Suggested Full Article (SEO-ready format)")
    st.markdown(full_article)

    st.markdown("### 🔗 Suggested Internal Links")
    st.write("- Congress News: https://www.patrika.com/national-news/congress/")
    st.write("- National Politics: https://www.patrika.com/national-news/politics/")

    st.markdown("### 🖼 Suggested Image Alt Texts")
    st.write("- Generic news image")
    st.write("- Related event scene")

    st.markdown("### 🧾 NewsArticle JSON-LD")
    st.code(schema, language="json")

    st.markdown("### 📥 Downloads")
    docx_bytes = docx_file(suggested_title, suggested_meta, full_article)
    st.download_button("Download DOCX", data=docx_bytes, file_name="seo_suggestions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    snippet = html_snippet(suggested_title, suggested_meta, canonical_url, schema)
    st.download_button("Download HTML snippet", data=snippet, file_name="seo_snippet.html", mime="text/html")

    st.download_button("Download JSON-LD", data=schema, file_name="newsarticle.json", mime="application/ld+json")

    csv_io = csv_file_row("ART001", "Staff Reporter", suggested_title, suggested_meta, "National")
    st.download_button("Download CSV summary", data=csv_io.getvalue(), file_name="summary.csv", mime="text/csv")

else:
    st.info("कृपया खबर पेस्ट करें या लिंक डालें और 'Analyze & Suggest' पर क्लिक करें।")
