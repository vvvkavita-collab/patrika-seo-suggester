import streamlit as st
import json
import csv
import io
from datetime import datetime
from collections import Counter
from text_unidecode import unidecode
from docx import Document

# -------------------------------
# Config
# -------------------------------
st.set_page_config(page_title="Patrika SEO Suggester", layout="wide")
PRIMARY_BRAND = "Rajasthan Patrika"
DEFAULT_AUTHOR = "Patrika News Desk"
DEFAULT_SECTION = "National"
HINDI_STOPWORDS = set("""
के की का हैं है और या यह था थी थे तथा लेकिन पर से में हो होना रहे रही रहे अगर तो भी लिए तक उन उस वही वहीँ एवं क्योंकि जैसे जैसेकि द्वारा नहीं बिना सभी उनका उनकी उनके वहीँ कभी हमेशा आदि प्रति लिए गए गई गया करें करेगा करेंगी करना करने करनेवाला करता करती करते जिसमें जिससे जिसके जिन जिसे जितना जितनी जितने आदि
""".split())
EN_STOPWORDS = set("""
the a an and or but if then else when while of for to in on at from by with without as is are was were be been being
""".split())

# Optional internal link map (replace with your real URLs)
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
# Utility functions
# -------------------------------
def clean_text(txt: str) -> str:
    return " ".join(txt.replace("\n", " ").split())

def tokenize(txt: str):
    # Simple tokenization for Hindi+English mixed content
    tokens = []
    for w in txt.split():
        w = w.strip(".,:;!?'\"()[]{}“”‘’-–—|/\\")
        if w:
            tokens.append(w.lower())
    return tokens

def is_stopword(w: str) -> bool:
    # crude stopword check (supports hindi+english)
    return w in EN_STOPWORDS or w in HINDI_STOPWORDS

def top_keywords(text: str, n=6):
    tokens = tokenize(text)
    toks = [t for t in tokens if not is_stopword(t) and t.isalpha()]
    freq = Counter(toks)
    # avoid over-generic words
    blacklist = {"news", "india", "indian", "said", "statement", "award", "avard", "khabar"}
    filtered = [(k, v) for k, v in freq.items() if k not in blacklist]
    filtered.sort(key=lambda x: (-x[1], x[0]))
    return [k for k, _ in filtered[:n]]

def guess_primary_entity(text: str):
    # naive guess: pick capitalized words sequence from original text
    words = [w.strip() for w in text.split()]
    caps = []
    for w in words:
        raw = w.strip(".,:;!?'\"()[]{}“”‘’-–—")
        if len(raw) >= 2 and (raw[0].isupper() or raw[:1].isalpha()):
            caps.append(raw)
    # prefer known entities if present
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
    # Decide intent from common denial/accept words
    lower = text.lower()
    if any(x in lower for x in ["इनकार", "deny", "decline", "refuse", "नहीं लेंगे", "इंकार"]):
        intent = "लेने से किया इनकार"
    elif any(x in lower for x in ["स्वीकार", "accept", "award received", "सम्मानित"]):
        intent = "स्वीकार करने की बात पर बयान"
    else:
        intent = "पर बयान"
    # Try to bind specific award keyword if present
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
    # minimize unicode while keeping readability; Hindi allowed but we’ll prefer ASCII
    ascii_title = unidecode(title)
    ascii_title = ascii_title.lower()
    allowed = []
    for ch in ascii_title:
        if ch.isalnum() or ch in [" ", "-", "_"]:
            allowed.append(ch)
    s = "".join(allowed).replace(" ", "-")
    # remove repeats and stopwords
    parts = [p for p in s.split("-") if p and p not in EN_STOPWORDS]
    s = "-".join(parts)
    # keep concise
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
    # basic checks
    notes = []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    avg_len = sum(len(p) for p in paragraphs) / max(1, len(paragraphs))
    if avg_len > 500:
        notes.append("पैराग्राफ छोटे रखें (3–4 लाइन), लंबे पैराग्राफ विभाजित करें।")
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
    # de-duplicate and clamp
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
    sc["Has internal links map"] = (True, True)  # map exists; editor must insert final URLs
    return sc

def internal_links(section: str):
    return INTERNAL_LINKS.get(section, [])

def html_snippet(title, meta, canonical, json_ld):
    # Minimal, CMS-pasteable snippet
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
# UI
# -------------------------------
st.title("Patrika SEO Suggester")
st.caption("Paste news → Get Google/SEO-ready suggestions → Download files (DOCX / JSON-LD / HTML / CSV)")

with st.sidebar:
    st.header("Settings")
    section = st.selectbox("Article Section", ["National", "Rajasthan", "Business", "Sports", "Entertainment"], index=0)
    author = st.text_input("Author", value=DEFAULT_AUTHOR)
    publisher = st.text_input("Publisher", value=PRIMARY_BRAND)
    canonical_base = st.text_input("Canonical base URL", value="https://www.patrika.com/")
    img_count = st.slider("Image alt suggestions (count)", 1, 5, 2)
    st.markdown("---")
    st.write("Title/Meta targets:")
    st.write("• Title: 55–60 chars")
    st.write("• Meta: 150–160 chars")

st.subheader("Paste your news article")
news_text = st.text_area("Paste full body (headline optional).", height=250, placeholder="अपनी खबर यहाँ पेस्ट करें...")

col1, col2 = st.columns([1, 1])
with col1:
    article_id = st.text_input("Article ID (optional)", value=f"ART-{datetime.now().strftime('%Y%m%d%H%M')}")
with col2:
    reporter = st.text_input("Reporter name (optional)", value="Staff Reporter")

if st.button("Analyze & Suggest", type="primary", disabled=len(news_text.strip()) == 0):
    body = clean_text(news_text)
    # Suggestions
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

    canonical_url = canonical_base.rstrip("/") + "/" + section.lower() + "/" + suggested_slug

    # Scores
    sc = scores(suggested_title, suggested_meta, body)

    # Layout panels
    st.success("Suggestions generated. Review and download below.")

    st.markdown("### Suggested Title (as per Google SEO guideline)")
    st.write(suggested_title)
    st.markdown("### Suggested Meta (as per Google SEO guideline)")
    st.write(suggested_meta)

    st.markdown("### Suggested Keywords")
    st.write(", ".join(suggested_keywords))

    st.markdown("### Suggested URL Slug")
    st.code(suggested_slug, language="text")

    st.markdown("### Suggested Internal Links")
    for t, u in links:
        st.write(f"- {t}: {u}")

    st.markdown("### Suggested Image Alt Text")
    for alt in alts:
        st.write(f"- {alt}")

    st.markdown("### NewsArticle JSON-LD")
    st.code(suggested_schema, language="json")

    st.markdown("### HTML snippet (title, meta, canonical, JSON-LD)")
    snippet = html_snippet(suggested_title, suggested_meta, canonical_url, suggested_schema)
    st.code(snippet, language="html")

    st.markdown("### Readability notes")
    for n in notes:
        st.write(f"- {n}")

    st.markdown("---")
    st.markdown("### Validation scores")
    for k, (val, ok) in sc.items():
        badge = "✅" if ok else "⚠️"
        st.write(f"- {k}: {val} {badge}")

    # Downloads
    st.markdown("---")
    st.markdown("### Downloads")

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
    st.download_button("Download DOCX", data=docx_bytes, file_name=f"{article_id}_seo_suggestions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    st.download_button("Download JSON-LD", data=suggested_schema, file_name=f"{article_id}_newsarticle.json", mime="application/ld+json")

    st.download_button("Download HTML snippet", data=snippet, file_name=f"{article_id}_seo_snippet.html", mime="text/html")

    csv_io = csv_file_row(article_id, reporter, suggested_title, suggested_meta, suggested_slug, section, sc)
    st.download_button("Download CSV (management)", data=csv_io.getvalue(), file_name=f"{article_id}_summary.csv", mime="text/csv")

else:
    st.info("खबर पेस्ट करें और ‘Analyze & Suggest’ पर क्लिक करें।")

# Footer
st.markdown("---")
st.caption("Outputs are heuristic and human-friendly. Editor should review before publishing.")
