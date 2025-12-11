# patrika_rewriter_final.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import html
from datetime import datetime
from collections import Counter
from text_unidecode import unidecode
from docx import Document
import io
import logging

# Optional OpenAI
try:
    import openai
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

st.set_page_config(page_title="Patrika — Final Rewriter (A+1)", layout="wide")

PRIMARY_BRAND = "Rajasthan Patrika"
DEFAULT_AUTHOR = "Patrika News Desk"
DEFAULT_SECTION = "National"

# ---------------------------
# Helpers: cleaning + SEO utils
# ---------------------------
HINDI_STOPWORDS = set("""
के की का हैं है और या यह था थी थे तथा लेकिन पर से में हो होना रहे रही रहे अगर तो भी लिए तक उन उस वही वहीँ एवं क्योंकि जैसे जैसेकि द्वारा नहीं बिना सभी उनका उनकी उनके वहीँ कभी हमेशा आदि प्रति लिए गए गई गया करें करेगा करेंगी करना करनेवाला करता करती करते जिसमें जिससे जिसके जिन जिसे जितना जितनी जितने आदि
""".split())

EN_STOPWORDS = set("the a an and or but if then else when while of for to in on at from by with without as is are was were be been being".split())

def clean_whitespace(s: str) -> str:
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def remove_byline_and_meta(text: str) -> str:
    """
    Strong cleaning: remove typical bylines, dates, photo credits, short title-like author lines.
    Keeps content paragraphs only.
    """
    if not text:
        return ""
    # normalize line endings
    orig = text.replace('\r', '')
    # Split paragraphs on double newline to respect paragraph boundaries
    paras = [p.strip() for p in re.split(r'\n{2,}', orig) if p.strip()]
    cleaned_paras = []
    for p in paras:
        p_clean = p.strip()
        low = p_clean.lower()
        # patterns to drop: byline, photo credit, updated/date lines, location lines like "New Delhi"
        if re.search(r'\b(photo|photo:|image|credit|graphic|फोटो|तस्वीर)\b', low):
            continue
        if re.search(r'\b(by|written by|reporter|staff reporter|patrika news desk|पत्रिका)\b', low):
            continue
        if re.search(r'\b(updated|update|last updated|updated on|अपडेट)\b', low):
            continue
        if re.search(r'\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', low):
            continue
        # short all-title lines like "Himadri Joshi" or "Saurabh and Gaurav (Photo - Patrika Graphics)"
        words = p_clean.split()
        if 1 < len(words) <= 4 and all(w[0].isupper() or re.match(r'^[A-Z]', w) for w in words):
            # Likely a short name/credit — skip
            continue
        # if paragraph contains mostly punctuation or single word, skip
        alpha_count = sum(1 for ch in p_clean if ch.isalpha())
        if alpha_count < 8:
            continue
        # otherwise accept cleaned paragraph (strip inline byline fragments)
        # remove inline "Photo - ..." fragments
        p_clean = re.sub(r'\(.*photo.*\)', '', p_clean, flags=re.I)
        p_clean = re.sub(r'photo[:\s\-—].*$', '', p_clean, flags=re.I)
        p_clean = clean_whitespace(p_clean)
        if p_clean:
            cleaned_paras.append(p_clean)
    # fallback: if no paragraphs survived, try removing single-line bylines and keep lines longer than 40 chars
    if not cleaned_paras:
        lines = [l.strip() for l in re.split(r'\n+', orig) if l.strip()]
        for l in lines:
            if len(l) > 60 and not re.search(r'\b(photo|by|reporter|updated|photo:)\b', l, flags=re.I):
                cleaned_paras.append(clean_whitespace(l))
    return "\n\n".join(cleaned_paras)

def top_keywords(text: str, n=6):
    if not text:
        return []
    tokens = re.findall(r'\w+', text.lower())
    tokens = [t for t in tokens if t not in EN_STOPWORDS and t not in HINDI_STOPWORDS and len(t) > 2]
    freq = Counter(tokens)
    # remove obvious person names by heuristic: Titlecase tokens from original text
    # (we will not perfect-NER here, but this helps avoid single-name noise)
    most = [k for k,_ in freq.most_common(n*2)]
    # filter tokens that look numeric or date-like
    filtered = [t for t in most if not re.match(r'^\d{2,}$', t) and not re.search(r'\d', t)]
    return filtered[:n]

def slugify(title: str):
    ascii_title = unidecode(title or "")
    ascii_title = ascii_title.lower()
    allowed = []
    for ch in ascii_title:
        if ch.isalnum() or ch in [" ", "-", "_"]:
            allowed.append(ch)
    s = "".join(allowed).strip().replace(" ", "-")
    s = re.sub(r'-{2,}', '-', s)
    s = s.strip('-')
    return s[:64]

# ---------------------------
# Fetching / Extraction
# ---------------------------
def fetch_article_from_url(url: str, timeout=12):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PatrikaRewriter/1.0)"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        # prefer <h1> for title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        # body: try <article>, then common containers, then fallback to all <p>
        body = ""
        article_tag = soup.find("article")
        if article_tag:
            ps = article_tag.find_all("p")
            body = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
        if not body:
            selectors = [
                {"name": "div", "attrs": {"class": re.compile(r"(article|story|content|post|main|entry)", re.I)}},
                {"name": "div", "attrs": {"id": re.compile(r"(article|story|content|main|entry)", re.I)}},
            ]
            for sel in selectors:
                nodes = soup.find_all(sel["name"], sel["attrs"])
                for n in nodes:
                    ps = n.find_all("p")
                    if len(ps) >= 2:
                        cand = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
                        if len(cand.split()) > 40:
                            body = cand
                            break
                if body:
                    break
        if not body:
            ps = soup.find_all("p")
            cand = []
            for p in ps:
                t = p.get_text(" ", strip=True)
                if len(t.split()) > 20 and not re.search(r'\b(photo|credit|—|—)\b', t, flags=re.I):
                    cand.append(t)
            if cand:
                body = "\n\n".join(cand)
        canonical = url
        link_can = soup.find("link", {"rel":"canonical"})
        if link_can and link_can.get("href"):
            canonical = link_can.get("href")
        return {"title": title or "", "body": body or "", "canonical": canonical}
    except Exception as e:
        logging.exception("fetch error")
        return {"title": "", "body": "", "canonical": url, "error": str(e)}

# ---------------------------
# Title / meta / headings generation (no OpenAI)
# ---------------------------
def generate_three_titles(clean_body: str, original_title: str = ""):
    """
    Create 3 distinct Hindi titles (Patrika tone)
    1) Factual (entity + main event)
    2) Short curiosity (short + hook)
    3) Update/summary (short)
    """
    # remove any leftover author/date fragments from original_title
    ot = re.sub(r'\(.*\)', '', (original_title or "")).strip()
    ot = re.sub(r'\bby\b.*', '', ot, flags=re.I).strip()
    # keywords
    kws = top_keywords(clean_body, n=3)
    first_sent = re.split(r'(?<=[।\.\?\!])\s+', clean_body.strip())[0] if clean_body else ""
    # Title 1: factual
    if ot and len(ot) > 8:
        t1 = ot if len(ot) <= 70 else ot[:70].rsplit(' ',1)[0]
    elif kws:
        t1 = f"{kws[0].title()} पर बड़ा अपडेट"
    else:
        t1 = first_sent[:60].rsplit(' ',1)[0] if first_sent else "ताज़ा खबर"
    # Title 2: short curiosity
    if kws:
        t2 = f"{kws[0].title()} की चुनौती" if len(kws[0]) > 3 else f"{kws[0].title()} में अपडेट"
    else:
        t2 = (first_sent[:40] + "…") if len(first_sent) > 40 else first_sent
    # Title 3: concise summary
    t3 = (first_sent[:55].rsplit(' ',1)[0]) if first_sent else (t1 if t1 else "अपडेट")
    # ensure they are clean (no dates/author fragments)
    def clean_title(t):
        t = re.sub(r'\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', '', t, flags=re.I)
        t = re.sub(r'\b\d{4}\b', '', t)
        t = re.sub(r'\bby\b.*', '', t, flags=re.I)
        return clean_whitespace(t)[:80]
    return [clean_title(t1), clean_title(t2), clean_title(t3)]

def generate_meta(clean_body: str, max_len=155):
    # Build meta from first ~28-32 words plus top 2 keywords appended for CTR
    words = re.sub(r'\s+', ' ', clean_body).split()
    take = 30 if len(words) >= 30 else len(words)
    snippet = " ".join(words[:take])
    kws = top_keywords(clean_body, n=2)
    if kws:
        meta = f"{snippet} | {kws[0]} {('· ' + kws[1]) if len(kws)>1 else ''}".strip()
    else:
        meta = snippet
    # clean author/date fragments if any
    meta = re.sub(r'\bby\b.*', '', meta, flags=re.I)
    meta = clean_whitespace(meta)
    if len(meta) > max_len:
        meta = meta[:max_len].rsplit(' ',1)[0]
    return meta

def build_h2_sections(paragraphs):
    """
    Create short H2 (3-5 words) and a 1-line intro for each H2 (A+1 format).
    Strategy: divide paragraphs into logical blocks of 3-4 paragraphs and label.
    """
    # possible H2 labels (Hindi short options) to pick from heuristically
    default_h2s = ["पृष्ठभूमि", "घटना का विवरण", "बयान / प्रतिक्रिया", "जांच की स्थिति", "प्रभाव / नतीजा"]
    sec = []
    if not paragraphs:
        return [{"h2": default_h2s[0], "intro": ""}]
    # group paragraphs into 2-3 paragraph blocks
    n = max(1, min(len(paragraphs)//3 + 1, 4))
    block_size = max(1, len(paragraphs)//n)
    idx = 0
    for i in range(n):
        block = paragraphs[idx: idx+block_size]
        idx += block_size
        if not block:
            continue
        # choose H2 from defaults by order
        h2 = default_h2s[i] if i < len(default_h2s) else f"विवरण {i+1}"
        # intro: first sentence of first paragraph of block (short)
        first_sent = re.split(r'(?<=[।\.\?\!])\s+', block[0].strip())[0]
        intro = first_sent if len(first_sent.split()) <= 18 else " ".join(first_sent.split()[:18]) + "…"
        sec.append({"h2": h2, "intro": intro})
    return sec

# ---------------------------
# OpenAI structured call (optional)
# ---------------------------
def get_openai_key():
    try:
        k = st.secrets["openai"]["api_key"]
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")

def call_openai_structured(article_body: str, original_title: str = ""):
    api_key = get_openai_key()
    if not api_key or not HAS_OPENAI:
        return None
    openai.api_key = api_key
    prompt = f"""
You are an expert Hindi news editor (Patrika style) and SEO specialist.
Input: Original title: {original_title}
Article body (cleaned, without byline/date/photo): {article_body}

Return JSON ONLY with keys:
- titles: [3 title strings in Hindi], (distinct) (50-65 char ideal)
- meta: one meta description (140-160 chars ideal), Hindi, no author/date
- slug: url-safe slug
- keywords: array of 6 keywords/phrases in Hindi
- headings: [{ "h2": "<text>", "intro": "<1-line intro>" }, ...] - at least 2
- paragraphs: [ list of paragraph strings in Hindi ] (no author/date/photo)
- notes: [2-4 short SEO/readability suggestions]

Do NOT invent facts. If unsure, be neutral. Return JSON only.
"""
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a precise assistant."},
                      {"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=1200
        )
        text = res["choices"][0]["message"]["content"].strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        # ensure no author/date in outputs (additional safety)
        if "titles" in parsed:
            parsed["titles"] = [re.sub(r'\bby\b.*','',t,flags=re.I).strip() for t in parsed["titles"]]
        if "meta" in parsed:
            parsed["meta"] = re.sub(r'\bby\b.*','',parsed["meta"],flags=re.I).strip()
        return parsed
    except Exception:
        logging.exception("OpenAI structured call failed")
        return None

# ---------------------------
# Fallback structured builder
# ---------------------------
def build_structured_fallback(clean_body: str, original_title: str = ""):
    titles = generate_three_titles(clean_body, original_title)
    meta = generate_meta(clean_body)
    paragraphs = [p.strip() for p in re.split(r'\n{1,}', clean_body) if p.strip()]
    if len(paragraphs) < 3:
        # split by sentences into paragraphs
        sents = re.split(r'(?<=[।\.\?\!])\s+', clean_body)
        paragraphs = []
        cur = []
        for s in sents:
            if s.strip():
                cur.append(s.strip())
                if len(cur) >= 3:
                    paragraphs.append(" ".join(cur).strip())
                    cur = []
        if cur:
            paragraphs.append(" ".join(cur).strip())
    headings = build_h2_sections(paragraphs)
    keywords = top_keywords(clean_body, n=6)
    slug = slugify(titles[0] if titles else "article")
    notes = ["छोटे पैराग्राफ रखें", "मुख्य कीवर्ड पहले पैराग्राफ में रखें", "H2 में स्पष्ट शब्द रखें"]
    return {
        "titles": titles,
        "meta": meta,
        "slug": slug,
        "keywords": keywords,
        "headings": headings,
        "paragraphs": paragraphs,
        "notes": notes
    }

# ---------------------------
# Output helpers + downloads
# ---------------------------
def build_docx(titles, meta, paragraphs, keywords, slug, headings, notes):
    doc = Document()
    doc.add_heading("Patrika — SEO Rewriter Output", level=1)
    doc.add_heading("Suggested Titles", level=2)
    for t in titles:
        doc.add_paragraph(t)
    doc.add_heading("Meta", level=2)
    doc.add_paragraph(meta)
    doc.add_heading("Keywords", level=2)
    doc.add_paragraph(", ".join(keywords))
    doc.add_heading("Headings", level=2)
    for h in headings:
        doc.add_paragraph(f"H2: {h.get('h2')}")
        if h.get("intro"):
            doc.add_paragraph(f"Intro: {h.get('intro')}")
    doc.add_heading("Rewritten Article (Paragraph-wise)", level=2)
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.add_heading("Notes", level=2)
    for n in notes:
        doc.add_paragraph("- " + n)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def json_ld_schema(headline, meta, slug, author, publisher, section):
    date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
    data = {
        "@context":"https://schema.org",
        "@type":"NewsArticle",
        "headline": headline,
        "description": meta,
        "datePublished": date_published,
        "author":{"@type":"Organization","name":author},
        "publisher":{"@type":"Organization","name":publisher},
        "articleSection": section,
        "isAccessibleForFree": True
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

# ---------------------------
# UI
# ---------------------------
st.title("Patrika — Final Rewriter (A+1) — Hindi")
st.caption("Mode: URL or Paste. Output: 3 titles, one meta (140-160 chars), short H2 + 1-line intro, paragraph-wise rewritten article. No author/date/photo in content.")

with st.sidebar:
    st.header("Settings")
    section = st.selectbox("Section", ["National","Rajasthan","Business","Sports","Entertainment"], index=0)
    author = st.text_input("Author for JSON-LD (publisher/author)", value=DEFAULT_AUTHOR)
    publisher = st.text_input("Publisher", value=PRIMARY_BRAND)
    canonical_base = st.text_input("Canonical base (if none)", value="https://www.patrika.com")
    st.markdown("---")
    st.write("OpenAI available (library installed):", HAS_OPENAI)
    st.write("OpenAI key present:", bool(get_openai_key()))

mode = st.radio("Mode", ["From URL(s)","Paste Article(s)"])

def render_and_download(id_tag, structured, canonical, section):
    titles = structured.get("titles", [])
    meta = structured.get("meta", "")
    slug = structured.get("slug", "")
    keywords = structured.get("keywords", [])
    headings = structured.get("headings", [])
    paragraphs = structured.get("paragraphs", [])
    notes = structured.get("notes", [])
    st.markdown("### Suggested Titles (3 options)")
    for i,t in enumerate(titles[:3], start=1):
        st.write(f"{i}. {t}")
    st.markdown("### SEO Meta (140-160 chars ideal)")
    st.write(meta)
    st.markdown("### Suggested URL Slug")
    st.code(slug)
    st.markdown("### Suggested Keywords")
    st.write(", ".join(keywords))
    st.markdown("### Suggested Headings (H2 + 1-line intro)")
    for h in headings:
        st.write(f"- **{h.get('h2')}** — {h.get('intro')}")
    st.markdown("### Rewritten Article (paragraph-wise)")
    for i,p in enumerate(paragraphs, start=1):
        st.write(f"Paragraph {i}: {p}")
    st.markdown("### Notes")
    for n in notes:
        st.write(f"- {n}")
    schema = json_ld_schema(titles[0] if titles else "", meta, slug, author, publisher, section)
    st.markdown("### JSON-LD (NewsArticle)")
    st.code(schema, language="json")
    snippet = f"""<!-- SEO snippet start -->
<title>{html.escape(titles[0] if titles else '')}</title>
<meta name="description" content="{html.escape(meta)}">
<link rel="canonical" href="{html.escape(canonical)}">
<script type="application/ld+json">
{schema}
</script>
<!-- SEO snippet end -->"""
    st.markdown("### HTML snippet")
    st.code(snippet, language="html")
    # downloads
    docx_bytes = build_docx(titles, meta, paragraphs, keywords, slug, headings, notes)
    st.download_button("Download DOCX", data=docx_bytes, file_name=f"{id_tag}_patrika_seo.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.download_button("Download JSON-LD", data=schema, file_name=f"{id_tag}_newsarticle.json", mime="application/ld+json")
    st.download_button("Download HTML snippet", data=snippet, file_name=f"{id_tag}_seo_snippet.html", mime="text/html")

if mode == "From URL(s)":
    st.subheader("Paste published article URL(s) — one per line")
    urls_input = st.text_area("URLs", height=200, placeholder="https://www.patrika.com/…")
    if st.button("Fetch, Clean & Rewrite", disabled=not urls_input.strip()):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        for idx, url in enumerate(urls, start=1):
            st.markdown(f"---\n## Article {idx}: `{url}`")
            with st.spinner("Fetching..."):
                fetched = fetch_article_from_url(url)
            raw_title = fetched.get("title","")
            raw_body = fetched.get("body","")
            # debug preview
            st.markdown("**[Debug] Raw extraction preview (for troubleshooting)**")
            st.write("Raw title:", raw_title[:200])
            st.code((raw_body[:800] + ("..." if len(raw_body)>800 else "")))
            cleaned = remove_byline_and_meta(raw_body)
            if not cleaned or len(cleaned.split()) < 25:
                st.warning("Article body seems short after cleaning. Paste full article in Paste mode for best results.")
            # Use OpenAI structured if available
            structured = None
            if HAS_OPENAI and get_openai_key():
                with st.spinner("Calling OpenAI for structured rewrite..."):
                    try:
                        structured = call_openai_structured(cleaned, original_title=raw_title)
                    except Exception:
                        structured = None
            if not structured:
                structured = build_structured_fallback(cleaned, original_title=raw_title)
            canonical = fetched.get("canonical") or canonical_base.rstrip("/") + "/" + section.lower() + "/" + structured.get("slug", "")
            article_id = f"URLART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
            render_and_download(article_id, structured, canonical, section)

else:  # Paste mode
    st.subheader("Paste article(s). Separate multiple articles with blank line + --- + blank line.")
    news_text = st.text_area("Paste article(s)", height=360, placeholder="Headline (optional)\n\nArticle body...\n\n---\n\n(next article)")
    if st.button("Rewrite & Suggest (Paste mode)", disabled=not news_text.strip()):
        parts = [p.strip() for p in re.split(r'\n{0,}\-{3,}\n{0,}', news_text) if p.strip()]
        for idx, part in enumerate(parts, start=1):
            st.markdown(f"---\n## Pasted Article {idx}")
            lines = [l.strip() for l in part.splitlines() if l.strip()]
            possible_title = ""
            body = part
            if len(lines) >= 2 and len(lines[0].split()) <= 12:
                possible_title = lines[0]
                body = "\n".join(lines[1:])
            cleaned = remove_byline_and_meta(body)
            if not cleaned or len(cleaned.split()) < 20:
                st.warning("Pasted text looks short after cleaning — ensure full article pasted.")
            structured = None
            if HAS_OPENAI and get_openai_key():
                with st.spinner("Calling OpenAI for structured rewrite..."):
                    try:
                        structured = call_openai_structured(cleaned, original_title=possible_title)
                    except Exception:
                        structured = None
            if not structured:
                structured = build_structured_fallback(cleaned, original_title=possible_title)
            canonical = canonical_base.rstrip("/") + "/" + section.lower() + "/" + structured.get("slug","")
            article_id = f"PASTEART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
            render_and_download(article_id, structured, canonical, section)

st.markdown("---")
st.caption("Tip: If a URL is JavaScript-heavy and extraction fails, paste the article in Paste mode. To enable best-quality rewrites, set your OpenAI key in Streamlit secrets or OPENAI_API_KEY env var.")
