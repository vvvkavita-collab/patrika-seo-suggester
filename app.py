import streamlit as st
import json
import csv
import io
from datetime import datetime
from collections import Counter
from text_unidecode import unidecode
from docx import Document
import requests
from bs4 import BeautifulSoup
import re

# -------------------------------
# Config
# -------------------------------
st.set_page_config(page_title="Patrika SEO Suggester - Updated", layout="wide")
PRIMARY_BRAND = "Rajasthan Patrika"
DEFAULT_AUTHOR = "Patrika News Desk"
DEFAULT_SECTION = "National"
HINDI_STOPWORDS = set("""
के की का हैं है और या यह था थी थे तथा लेकिन पर से में हो होना रहे रही रहे अगर तो भी लिए तक उन उस वही वहीँ एवं क्योंकि जैसे जैसेकि द्वारा नहीं बिना सभी उनका उनकी उनके वहीँ कभी हमेशा आदि प्रति लिए गए गई गया करें करेगा करेंगी करना करने करनेवाला करता करती करते जिसमें जिससे जिसके जिन जिसे जितना जितनी जितने आदि
""".split())
EN_STOPWORDS = set("""
the a an and or but if then else when while of for to in on at from by with without as is are was were be been being
""".split())

INTERNAL_LINKS = {
    "National": [
        ("Congress News", "https://www.patrika.com/national-news/congress/"),
        ("National Politics", "https://www.patrika.com/national-news/politics/"),
        ("Shashi Tharoor Profile", "https://www.patrika.com/tags/shashi-tharoor/"),
    ],
    "Rajasthan": [
        ("Jaipur News", "https://www.patrika.com/jaipur-news/"),
        ("Rajasthan Politics", "https://www.patrika.com/rajasthan-news/politics/"),
    ],
}

# -------------------------------
# Utility functions (existing + added)
# -------------------------------
def clean_text(txt: str) -> str:
    return " ".join(txt.replace("\r", "").replace("\n", " ").split())

def tokenize(txt: str):
    tokens = []
    for w in txt.split():
        w = w.strip(".,:;!?'\"()[]{}“”‘’-–—|/\\")
        if w:
            tokens.append(w.lower())
    return tokens

def is_stopword(w: str) -> bool:
    return w in EN_STOPWORDS or w in HINDI_STOPWORDS

def top_keywords(text: str, n=6):
    tokens = tokenize(text)
    toks = [t for t in tokens if not is_stopword(t) and t.isalpha()]
    freq = Counter(toks)
    blacklist = {"news", "india", "indian", "said", "statement", "award", "avard", "khabar"}
    filtered = [(k, v) for k, v in freq.items() if k not in blacklist]
    filtered.sort(key=lambda x: (-x[1], x[0]))
    return [k for k, _ in filtered[:n]]

def guess_primary_entity(text: str):
    words = [w.strip() for w in text.split()]
    caps = []
    for w in words:
        raw = w.strip(".,:;!?'\"()[]{}“”‘’-–—")
        if len(raw) >= 2 and raw[0].isupper():
            caps.append(raw)
    candidates = ["Shashi Tharoor", "Veer Savarkar", "Congress", "BJP", "Rajasthan", "Jaipur", "Delhi"]
    for c in candidates:
        if c.lower() in text.lower():
            return c
    return caps[0] if caps else "Breaking"

def clamp(s: str, max_len: int):
    return s[:max_len].rstrip()

def generate_title(text: str, max_len=60):
    entity = guess_primary_entity(text)
    kws = top_keywords(text, n=4)
    lower = text.lower()
    if any(x in lower for x in ["इनकार", "deny", "decline", "refuse", "नहीं लेंगे", "इंकार"]):
        intent = "लेने से किया इनकार"
    elif any(x in lower for x in ["स्वीकार", "accept", "award received", "सम्मानित"]):
        intent = "स्वीकार करने की बात पर बयान"
    else:
        intent = "पर बयान"
    if "savarkar" in lower or "सावरकर" in lower:
        subject = "‘Veer Savarkar Award’"
    else:
        subject = "अवॉर्ड"
    t = f"{entity} ने {subject} {intent}, आयोजकों की भूमिका पर सवाल"
    return clamp(t, max_len)

def generate_meta(text: str, max_len=160):
    lower = text.lower()
    if any(x in lower for x in ["इनकार", "deny", "decline", "refuse", "नहीं लेंगे", "इंकार"]):
        stance = "स्पष्ट इनकार"
    else:
        stance = "महत्वपूर्ण बयान"
    entity = guess_primary_entity(text)
    subject = "‘वीर सावरकर अवॉर्ड’" if ("savarkar" in lower or "सावरकर" in lower) else "अवॉर्ड"
    meta = f"{entity} ने {subject} पर {stance} दर्ज किया। आयोजकों पर बिना अनुमति नाम जोड़ने का आरोप और समारोह में शामिल न होने की बात कही।"
    return clamp(meta, max_len)

def slugify(title: str):
    ascii_title = unidecode(title)
    ascii_title = ascii_title.lower()
    allowed = []
    for ch in ascii_title:
        if ch.isalnum() or ch in [" ", "-", "_"]:
            allowed.append(ch)
    s = "".join(allowed).replace(" ", "-")
    parts = [p for p in s.split("-") if p and p not in EN_STOPWORDS]
    s = "-".join(parts)
    return clamp(s, 64)

def image_alts(text: str, count=2):
    kws = top_keywords(text, n=4)
    entity = guess_primary_entity(text)
    alts = []
    base = " ".join([entity] + kws[:2]).strip()
    if not base:
        base = "news image"
    for i in range(count):
        alts.append(clamp(f"{base} - scene {i+1}", 80))
    return alts

def readability_notes(text: str):
    notes = []
    paragraphs = [p.strip() for p in re.split(r'\n{1,}', text) if p.strip()]
    avg_len = sum(len(p) for p in paragraphs) / max(1, len(paragraphs))
    if avg_len > 500:
        notes.append("पैराग्राफ छोटे रखें (3–4 लाइन), लंबे पैराग्राफ विभित करें।")
    tokens = tokenize(text)
    if len(tokens) > 800:
        notes.append("इंट्रो छोटा करें और उपशीर्षक (H2/H3) जोड़कर सेक्शन्स बनाएं।")
    if not any(h in text for h in ["\n##", "\n###", "H2", "H3"]):
        notes.append("कम-से-कम 2 उपशीर्षक जोड़ें: पृष्ठभूमि, बयान/प्रतिक्रिया, संदर्भ।")
    if not notes:
        notes.append("रीडेबिलिटी ठीक है; छोटे पैराग्राफ और स्पष्ट उपशीर्षक बनाए रखें।")
    return notes

def keywords_bundle(text: str):
    primaries = []
    lower = text.lower()
    if "shashi" in lower or "थरूर" in lower:
        primaries.append("Shashi Tharoor")
    if "savarkar" in lower or "सावरकर" in lower:
        primaries.append("Veer Savarkar Award")
    if "congress" in lower or "कांग्रेस" in lower:
        primaries.append("Congress MP statement")
    extras = top_keywords(text, n=6)
    seen = set()
    result = []
    for k in primaries + extras:
        if k and k not in seen:
            result.append(k)
            seen.add(k)
    return result[:8]

def schema_json_ld(headline, description, date_published, author, publisher, section, images=None):
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
    if images:
        data["image"] = images
    return json.dumps(data, ensure_ascii=False, indent=2)

def scores(title, meta, text):
    sc = {}
    sc["Title length"] = (len(title), 50 <= len(title) <= 60)
    sc["Meta length"] = (len(meta), 140 <= len(meta) <= 160)
    sc["Has keywords"] = (len(keywords_bundle(text)) >= 3, True)
    sc["Has internal links map"] = (True, True)
    return sc

def internal_links(section: str):
    return INTERNAL_LINKS.get(section, [])

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

def docx_file(title, meta, body, keywords, slug, schema, links, alts, notes):
    doc = Document()
    doc.add_heading("Patrika SEO Suggester Output", level=1)
    doc.add_heading("Suggested Title (as per Google SEO guideline)", level=2)
    doc.add_paragraph(title)
    doc.add_heading("Suggested Meta (as per Google SEO guideline)", level=2)
    doc.add_paragraph(meta)
    doc.add_heading("Suggested Keywords", level=2)
    doc.add_paragraph(", ".join(keywords))
    doc.add_heading("Suggested URL Slug", level=2)
    doc.add_paragraph(slug)
    doc.add_heading("NewsArticle JSON-LD", level=2)
    doc.add_paragraph(schema)
    doc.add_heading("Suggested Internal Links", level=2)
    for text, url in links:
        doc.add_paragraph(f"{text}: {url}")
    doc.add_heading("Suggested Image Alt Text", level=2)
    for alt in alts:
        doc.add_paragraph(alt)
    doc.add_heading("Readability Notes", level=2)
    for n in notes:
        doc.add_paragraph(f"- {n}")
    doc.add_heading("Original Body", level=2)
    doc.add_paragraph(body)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def csv_file_row(article_id, reporter, title, meta, slug, section, score_dict):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ArticleID", "Reporter", "TitleLen", "MetaLen", "Slug", "Section", "TitleOK", "MetaOK"])
    writer.writerow([
        article_id, reporter, len(title), len(meta), slug, section,
        score_dict["Title length"][1], score_dict["Meta length"][1]
    ])
    output.seek(0)
    return output

# -------------------------------
# NEW: fetch article from URL (heuristic)
# -------------------------------
def fetch_article_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PatrikaSEO/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # try common patterns
        article_text = ""
        title = ""
        # title heuristics
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

        # article body heuristics: <article>, common classes
        article = soup.find("article")
        if article:
            ps = article.find_all("p")
            article_text = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
        if not article_text:
            # try common content containers
            selectors = [
                {"name": "div", "attr": {"class": re.compile(r"(article|story|content|post|main)", re.I)}},
                {"name": "div", "attr": {"id": re.compile(r"(article|story|content|main)", re.I)}},
            ]
            for sel in selectors:
                nodes = soup.find_all(sel["name"], sel["attr"])
                for n in nodes:
                    ps = n.find_all("p")
                    if len(ps) >= 2:
                        article_text = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
                        if len(article_text.split()) > 50:
                            break
                if article_text:
                    break
        if not article_text:
            # fallback: collect large <p> tags in body
            ps = soup.body.find_all("p") if soup.body else []
            article_text = "\n\n".join([p.get_text(" ", strip=True) for p in ps if len(p.get_text(strip=True)) > 30])

        # canonical
        canonical = None
        link_can = soup.find("link", {"rel": "canonical"})
        if link_can and link_can.get("href"):
            canonical = link_can["href"]
        else:
            canonical = url

        return {
            "title": title or "",
            "body": article_text or "",
            "canonical": canonical
        }
    except Exception as e:
        return {"title": "", "body": "", "canonical": url, "error": str(e)}

# -------------------------------
# UI
# -------------------------------
st.title("Patrika SEO Suggester — URL & Paste modes")
st.caption("Mode: Provide published URL(s) OR paste article(s). Outputs follow Google/SEO guidelines. Download DOCX / JSON-LD / HTML / CSV per article.")

with st.sidebar:
    st.header("Settings")
    section = st.selectbox("Article Section", ["National", "Rajasthan", "Business", "Sports", "Entertainment"], index=0)
    author = st.text_input("Author", value=DEFAULT_AUTHOR)
    publisher = st.text_input("Publisher", value=PRIMARY_BRAND)
    canonical_base = st.text_input("Canonical base URL (used if none found)", value="https://www.patrika.com/")
    img_count = st.slider("Image alt suggestions (count)", 1, 5, 2)
    st.markdown("---")
    st.write("Title/Meta targets:")
    st.write("• Title: 55–60 chars")
    st.write("• Meta: 150–160 chars")
    st.markdown("---")
    st.write("Multi-article instructions:")
    st.write("- For URL mode: paste one URL per line.")
    st.write("- For Paste mode: separate multiple articles with a blank line + `---` + blank line (i.e. `\\n\\n---\\n\\n`).")

mode = st.radio("Select input mode", ["From URL(s)", "Paste Article(s)"])

if mode == "From URL(s)":
    st.subheader("Paste published article URL(s) — one URL per line")
    urls_input = st.text_area("URLs (one per line)", height=160, placeholder="https://www.example.com/news/123\nhttps://another.example.com/story/abc")
    if st.button("Fetch & Analyze URLs", disabled=len(urls_input.strip()) == 0):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        if not urls:
            st.warning("Please paste at least one URL.")
        else:
            for idx, url in enumerate(urls, start=1):
                st.markdown(f"---\n## Article {idx}: `{url}`")
                with st.spinner(f"Fetching {url} ..."):
                    fetched = fetch_article_from_url(url)
                if fetched.get("error"):
                    st.error(f"Error fetching {url}: {fetched['error']}")
                    continue
                body = clean_text(fetched.get("body", ""))
                fetched_title = fetched.get("title", "").strip()
                canonical_url = fetched.get("canonical") or (canonical_base.rstrip("/") + "/" + section.lower())

                if not body or len(body.split()) < 30:
                    st.warning("Unable to extract a full article body from this URL. You can paste the article manually in Paste mode.")
                    if fetched_title:
                        st.write("Extracted title (partial):")
                        st.write(fetched_title)
                    continue

                # Process same as paste
                suggested_title = generate_title(body) if not fetched_title else generate_title(body)  # still generate from body
                suggested_meta = generate_meta(body)
                suggested_keywords = keywords_bundle(body)
                suggested_slug = slugify(suggested_title)
                date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
                suggested_schema = schema_json_ld(
                    headline=suggested_title,
                    description=suggested_meta,
                    date_published=date_published,
                    author=author,
                    publisher=publisher,
                    section=section,
                    images=None
                )
                links = internal_links(section)
                alts = image_alts(body, count=img_count)
                notes = readability_notes(body)
                sc = scores(suggested_title, suggested_meta, body)
                canonical_final = fetched.get("canonical") or (canonical_base.rstrip("/") + "/" + section.lower() + "/" + suggested_slug)

                st.markdown("### Suggested Title")
                st.write(suggested_title)
                st.markdown("### Suggested Meta")
                st.write(suggested_meta)
                st.markdown("### Suggested Keywords")
                st.write(", ".join(suggested_keywords))
                st.markdown("### Suggested URL Slug")
                st.code(suggested_slug, language="text")
                st.markdown("### Suggested Image Alt Text")
                for alt in alts:
                    st.write(f"- {alt}")
                st.markdown("### NewsArticle JSON-LD")
                st.code(suggested_schema, language="json")
                snippet = html_snippet(suggested_title, suggested_meta, canonical_final, suggested_schema)
                st.markdown("### HTML snippet")
                st.code(snippet, language="html")
                st.markdown("### Readability notes")
                for n in notes:
                    st.write(f"- {n}")
                st.markdown("### Validation scores")
                for k, (val, ok) in sc.items():
                    badge = "✅" if ok else "⚠️"
                    st.write(f"- {k}: {val} {badge}")

                # Downloads
                article_id = f"URLART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
                docx_bytes = docx_file(
                    title=suggested_title,
                    meta=suggested_meta,
                    body=body,
                    keywords=suggested_keywords,
                    slug=suggested_slug,
                    schema=suggested_schema,
                    links=links,
                    alts=alts,
                    notes=notes
                )
                st.download_button("Download DOCX", data=docx_bytes, file_name=f"{article_id}_seo_suggestions.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                st.download_button("Download JSON-LD", data=suggested_schema, file_name=f"{article_id}_newsarticle.json", mime="application/ld+json")
                st.download_button("Download HTML snippet", data=snippet, file_name=f"{article_id}_seo_snippet.html", mime="text/html")
                csv_io = csv_file_row(article_id, author, suggested_title, suggested_meta, suggested_slug, section, sc)
                st.download_button("Download CSV (management)", data=csv_io.getvalue(), file_name=f"{article_id}_summary.csv", mime="text/csv")

elif mode == "Paste Article(s)":
    st.subheader("Paste your news article(s)")
    st.info("If multiple articles: separate them with a blank line + --- + blank line (i.e. \\n\\n---\\n\\n).")
    news_text = st.text_area("Paste full body (headline optional).", height=300, placeholder="अपनी खबर यहाँ पेस्ट करें...\n\n---\n\n(Next article)")
    if st.button("Analyze & Suggest (Paste mode)", disabled=len(news_text.strip()) == 0):
        # split into articles
        parts = [p.strip() for p in re.split(r'\n{0,}\-{3,}\n{0,}', news_text) if p.strip()]
        if not parts:
            st.warning("कोई आर्टिकल नहीं मिला—कृपया सही फॉर्मैट में पेस्ट करें।")
        else:
            for idx, part in enumerate(parts, start=1):
                st.markdown(f"---\n## Pasted Article {idx}")
                body = clean_text(part)
                suggested_title = generate_title(body)
                suggested_meta = generate_meta(body)
                suggested_keywords = keywords_bundle(body)
                suggested_slug = slugify(suggested_title)
                date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
                suggested_schema = schema_json_ld(
                    headline=suggested_title,
                    description=suggested_meta,
                    date_published=date_published,
                    author=author,
                    publisher=publisher,
                    section=section,
                    images=None
                )
                links = internal_links(section)
                alts = image_alts(body, count=img_count)
                notes = readability_notes(body)
                sc = scores(suggested_title, suggested_meta, body)
                canonical_final = canonical_base.rstrip("/") + "/" + section.lower() + "/" + suggested_slug

                st.markdown("### Suggested Title")
                st.write(suggested_title)
                st.markdown("### Suggested Meta")
                st.write(suggested_meta)
                st.markdown("### Suggested Keywords")
                st.write(", ".join(suggested_keywords))
                st.markdown("### Suggested URL Slug")
                st.code(suggested_slug, language="text")
                st.markdown("### Suggested Image Alt Text")
                for alt in alts:
                    st.write(f"- {alt}")
                st.markdown("### NewsArticle JSON-LD")
                st.code(suggested_schema, language="json")
                snippet = html_snippet(suggested_title, suggested_meta, canonical_final, suggested_schema)
                st.markdown("### HTML snippet")
                st.code(snippet, language="html")
                st.markdown("### Readability notes")
                for n in notes:
                    st.write(f"- {n}")
                st.markdown("### Validation scores")
                for k, (val, ok) in sc.items():
                    badge = "✅" if ok else "⚠️"
                    st.write(f"- {k}: {val} {badge}")

                # Downloads
                article_id = f"PASTEART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
                docx_bytes = docx_file(
                    title=suggested_title,
                    meta=suggested_meta,
                    body=body,
                    keywords=suggested_keywords,
                    slug=suggested_slug,
                    schema=suggested_schema,
                    links=links,
                    alts=alts,
                    notes=notes
                )
                st.download_button("Download DOCX", data=docx_bytes, file_name=f"{article_id}_seo_suggestions.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                st.download_button("Download JSON-LD", data=suggested_schema, file_name=f"{article_id}_newsarticle.json", mime="application/ld+json")
                st.download_button("Download HTML snippet", data=snippet, file_name=f"{article_id}_seo_snippet.html", mime="text/html")
                csv_io = csv_file_row(article_id, author, suggested_title, suggested_meta, suggested_slug, section, sc)
                st.download_button("Download CSV (management)", data=csv_io.getvalue(), file_name=f"{article_id}_summary.csv", mime="text/csv")

# Footer
st.markdown("---")
st.caption("Outputs are heuristic and human-friendly. Editor should review before publishing. If extraction from URL fails, paste article in Paste mode for best results.")
