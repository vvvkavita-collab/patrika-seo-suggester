# patrika_full_rewriter.py
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

# Optional: OpenAI
try:
    import openai
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

# -----------------------
# Page config / defaults
# -----------------------
st.set_page_config(page_title="Patrika — Full News Rewriter (SEO)", layout="wide")
PRIMARY_BRAND = "Rajasthan Patrika"
DEFAULT_AUTHOR = "Patrika News Desk"
DEFAULT_SECTION = "National"

# -----------------------
# Utility / cleaning
# -----------------------
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
    Remove common byline / date / photo credit / location prefixes that often appear at the top.
    Keeps the actual article body.
    """
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned_lines = []
    skip_first_n = 0
    for i, ln in enumerate(lines):
        low = ln.lower()
        # patterns that indicate byline / date / photo credit
        if re.match(r'^(by|written by|reporter|staff reporter|patrika news desk)\b', low) or \
           re.search(r'\b(photo|photo:|image:|credit:|graphic)\b', low) or \
           re.match(r'^(updated|update|last updated|updated on)\b', low) or \
           re.match(r'^[A-Z][a-z]+ \d{1,2}, \d{4}$', ln) or \
           re.match(r'^[A-Z][a-z]+ \d{1,2} \d{4}$', ln) or \
           re.match(r'^\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', low) or \
           re.match(r'^[A-Za-z]{2,20}\s*,\s*[A-Za-z]{2,20}$', ln):  # simple location patterns like "New Delhi, India"
            # Skip this line (treat as metadata)
            continue
        # remove lines that are short author-like tokens: "Himadri Joshi", "Patrika Graphic"
        if 1 < len(ln.split()) <= 3 and all(w.istitle() for w in ln.split()):
            # ambiguous: could be real sentence; but common pattern is author or credit
            # skip if next line begins with '—' or '—' used as separator too
            continue
        cleaned_lines.append(ln)
    # join preserving paragraph breaks where more than one newline existed in original
    # Use double-newline separation if original had paragraphs
    # Attempt to keep paragraphs: detect long continuous chunks separated by blank lines in original
    original_paragraphs = re.split(r'\n\s*\n', text)
    # For each original paragraph, remove if it's likely metadata
    final_pars = []
    for p in original_paragraphs:
        p_strip = p.strip()
        # if paragraph is short (<6 words) and contains photo/byline words, skip
        if len(p_strip.split()) < 6 and re.search(r'\b(by|photo|credit|updated|reporter|desk)\b', p_strip, re.I):
            continue
        # else clean internal newlines
        final_pars.append(clean_whitespace(p_strip))
    if final_pars:
        return "\n\n".join(final_pars)
    # fallback: join cleaned_lines
    return "\n\n".join(cleaned_lines)

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

def top_keywords(text: str, n=6):
    tokens = re.findall(r'\w+', (text or "").lower())
    tokens = [t for t in tokens if t not in EN_STOPWORDS and t not in HINDI_STOPWORDS and len(t) > 2]
    freq = Counter(tokens)
    most = [k for k,_ in freq.most_common(n)]
    return most

# -----------------------
# Extraction heuristics
# -----------------------
def fetch_article_from_url(url: str, timeout=12):
    """
    Heuristic extraction using requests + bs4. Returns dict {title, body, canonical, error}
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PatrikaRewriter/1.0)"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        # title heuristics
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        # body heuristics
        body = ""
        article = soup.find("article")
        if article:
            ps = article.find_all("p")
            body = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
        if not body:
            # search common containers
            selectors = [
                {"name": "div", "attrs": {"class": re.compile(r"(content|article|main|story|post)", re.I)}},
                {"name": "div", "attrs": {"id": re.compile(r"(content|article|main|story|post)", re.I)}},
            ]
            for sel in selectors:
                nodes = soup.find_all(sel["name"], sel["attrs"])
                for n in nodes:
                    ps = n.find_all("p")
                    if ps and len(ps) >= 2:
                        cand = "\n\n".join([p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)])
                        if len(cand.split()) > 40:
                            body = cand
                            break
                if body:
                    break
        if not body:
            # fallback: gather all large <p>
            ps = soup.find_all("p")
            cand = []
            for p in ps:
                t = p.get_text(" ", strip=True)
                if len(t.split()) > 15:
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

# -----------------------
# OpenAI integration (structured JSON)
# -----------------------
def get_openai_key():
    # Streamlit secrets: st.secrets["openai"]["api_key"] or env var OPENAI_API_KEY
    try:
        k = st.secrets["openai"]["api_key"]
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")

def call_openai_structured(article_body: str, original_title: str = "", language="hi"):
    """
    Call OpenAI to return JSON with:
    { titles: [t1,t2,t3], meta: "...", slug: "...", keywords: [...], headings: [{h2, h3:[...]}], paragraphs: [...], notes: [...] }
    The prompt forces JSON-only response.
    """
    api_key = get_openai_key()
    if not api_key or not HAS_OPENAI:
        return None
    openai.api_key = api_key

    # Prompt: precise and strict. Ask for 3 title options, full meta, etc.
    prompt = f"""
You are a professional Hindi news editor and SEO specialist working for Rajasthan Patrika.
Language: Hindi. Tone: Patrika-style clear reportage.

Input:
Original title (if any): {original_title}
Article body (raw, cleaned of byline): {article_body}

Task:
Return a JSON object ONLY (no explanation) with keys:
- titles: array of 3 SEO-friendly headline strings (Hindi). Prefer 50-60 characters but it's ok if slightly off. Titles should be distinct and click-worthy while factual.
- meta: one SEO meta description (Hindi), about 140-160 characters, summarizing the article, no author/date.
- slug: url-safe slug (lowercase, hyphen-separated).
- keywords: array of 6 short keywords/phrases (Hindi/Hinglish) relevant to the article.
- headings: array of section objects. Each object: {{ "h2": "<text>", "h3": ["s1","s2"] }}. Provide at least 2 H2 sections if possible.
- paragraphs: array of rewritten paragraph strings in Hindi — keep facts only (do NOT invent facts). Paragraphs should be short (3-6 lines).
- notes: array of 2-4 short SEO/readability suggestions.

Constraints:
- Do NOT invent new facts or people. If a fact is uncertain, use neutral phrasing like "प्रतिक्रिया का इंतजार है" or omit.
- Do NOT include author name, date, or photo credit in paragraphs/meta/title.
- Return valid JSON only.

Now produce the JSON.
"""

    try:
        # Use ChatCompletion for structured response
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # change if unavailable in your account
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        raw = response["choices"][0]["message"]["content"].strip()
        # strip code fences if any
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        return parsed
    except Exception as e:
        logging.exception("OpenAI call failed")
        return None

# -----------------------
# Local fallback generator (if OpenAI not available)
# -----------------------
def fallback_generate(article_body: str, original_title: str = ""):
    # generate 3 titles using entity + top keywords
    kws = top_keywords(article_body, n=4)
    entity = ""
    # try to guess entity: first significant Titlecase tokens in body
    m = re.search(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b', article_body)
    if m:
        entity = m.group(1)
    titles = []
    base_short = " ".join(article_body.split()[:10])
    if original_title and len(original_title) > 6:
        cleaned = re.sub(r'[\|\—\–\:].*$', '', original_title).strip()
        titles.append(cleaned[:60])
    else:
        if entity:
            titles.append(f"{entity} — {kws[0].title()}"[:60])
        else:
            titles.append(base_short[:60])
    # two more variants
    if kws:
        titles.append(f"{base_short} — {kws[0].title()}"[:60])
        if len(kws) > 1:
            titles.append(f"{kws[0].title()} पर अपडेट: {kws[1].title()}"[:60])
        else:
            titles.append(f"{base_short} — रिपोर्ट"[:60])
    else:
        titles.append(base_short[:60])
        titles.append((base_short + " - अपडेट")[:60])
    # meta: first ~28-32 words
    words = re.sub(r'\s+', ' ', article_body).split()
    meta = " ".join(words[:30])
    if len(meta) > 155:
        meta = meta[:155].rsplit(' ',1)[0]
    # slug
    slug = slugify(titles[0])
    # headings: simple split into two sections
    headings = [{"h2":"पृष्ठभूमि","h3":[]},{"h2":"बयान/प्रतिक्रिया","h3":[]}]
    # paragraphs: split by double newline or sentences
    paras = [p.strip() for p in re.split(r'\n{1,}', article_body) if p.strip()]
    if len(paras) < 3:
        # fallback split by sentences into ~4 paragraphs
        sents = re.split(r'(?<=[।\.\?\!])\s+', article_body)
        paras = []
        cur = []
        for i, s in enumerate(sents):
            cur.append(s.strip())
            if len(cur) >= 3:
                paras.append(" ".join(cur).strip())
                cur=[]
        if cur:
            paras.append(" ".join(cur).strip())
    # keywords
    keywords = kws or top_keywords(article_body, n=6)
    notes = ["छोटे पैराग्राफ रखें", "मुख्य कीवर्ड पहले पैराग्राफ में रखें"]
    return {
        "titles": titles[:3],
        "meta": meta,
        "slug": slug,
        "keywords": keywords,
        "headings": headings,
        "paragraphs": paras,
        "notes": notes
    }

# -----------------------
# Output helpers & downloads
# -----------------------
def build_docx(title, meta, paragraphs, keywords, slug, headings, notes):
    doc = Document()
    doc.add_heading("Patrika — SEO Rewriter Output", level=1)
    doc.add_heading("Suggested Titles", level=2)
    for t in title:
        doc.add_paragraph(t)
    doc.add_heading("Meta (SEO)", level=2)
    doc.add_paragraph(meta)
    doc.add_heading("Keywords", level=2)
    doc.add_paragraph(", ".join(keywords))
    doc.add_heading("Suggested Headings", level=2)
    for h in headings:
        doc.add_paragraph(f"H2: {h.get('h2')}")
        for h3 in h.get("h3", []):
            doc.add_paragraph(f"  H3: {h3}")
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

def json_ld_schema(title, meta, slug, author, publisher, section):
    date_published = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": meta,
        "datePublished": date_published,
        "author": {"@type":"Organization","name":author},
        "publisher": {"@type":"Organization","name":publisher},
        "articleSection": section,
        "isAccessibleForFree": True
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

# -----------------------
# UI
# -----------------------
st.title("Patrika — Full News Rewriter (SEO) — Hindi")
st.caption("Input: Published URL(s) or paste article. Output: 3 titles, SEO meta, subheadings, paragraph-wise rewritten article (Patrika style).")

with st.sidebar:
    st.header("Settings")
    section = st.selectbox("Section", ["National","Rajasthan","Business","Sports","Entertainment"], index=0)
    author = st.text_input("Author for JSON-LD (publisher/author)", value=DEFAULT_AUTHOR)
    publisher = st.text_input("Publisher", value=PRIMARY_BRAND)
    canonical_base = st.text_input("Canonical base (if none)", value="https://www.patrika.com")
    st.markdown("---")
    st.write("OpenAI status:")
    st.write(f"OpenAI library installed: {HAS_OPENAI}")
    st.write("OpenAI key present:", bool(get_openai_key()))

mode = st.radio("Mode", ["From URL(s)","Paste Article(s)"])

if mode == "From URL(s)":
    st.subheader("Paste one or more published article URLs (one per line)")
    urls_input = st.text_area("URLs", height=160, placeholder="https://www.example.com/news/123")
    if st.button("Fetch, Clean & Rewrite", disabled=not urls_input.strip()):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        for idx, url in enumerate(urls, start=1):
            st.markdown(f"---\n## Article {idx}: `{url}`")
            with st.spinner("Fetching..."):
                fetched = fetch_article_from_url(url)
            if fetched.get("error"):
                st.error(f"Fetch error: {fetched['error']}")
                continue
            raw_title = fetched.get("title","")
            raw_body = fetched.get("body","")
            # debug raw preview
            st.markdown("**[Debug] Raw extraction preview**")
            st.write("Raw title:", raw_title[:250])
            st.code((raw_body[:800] + ("..." if len(raw_body)>800 else "")))
            # clean out bylines/dates/credits
            cleaned = remove_byline_and_meta(raw_body)
            if not cleaned or len(cleaned.split()) < 30:
                st.warning("Article body seems too short after cleaning. Paste article manually in Paste mode for best results.")
            # Call OpenAI
            suggested = None
            if HAS_OPENAI and get_openai_key():
                with st.spinner("Calling OpenAI for structured rewrite..."):
                    suggested = call_openai_structured(cleaned, original_title=raw_title, language="hi")
            if not suggested:
                suggested = fallback_generate(cleaned, original_title=raw_title)
            # render
            titles = suggested.get("titles") if suggested.get("titles") else [suggested.get("title")] if suggested.get("title") else suggested.get("titles", [])
            meta = suggested.get("meta","")
            slug = suggested.get("slug") or slugify(titles[0] if titles else "article")
            keywords = suggested.get("keywords") or top_keywords(cleaned, n=6)
            headings = suggested.get("headings") or []
            paragraphs = suggested.get("paragraphs") or [cleaned]
            notes = suggested.get("notes") or []
            # display structured output
            st.markdown("### Suggested Titles (3 options)")
            for i, t in enumerate(titles[:3], start=1):
                st.write(f"{i}. {t}")
            st.markdown("### SEO Meta (140-160 chars ideal)")
            st.write(meta)
            st.markdown("### Suggested URL Slug")
            st.code(slug)
            st.markdown("### Suggested Keywords")
            st.write(", ".join(keywords))
            st.markdown("### Suggested Headings (H2 / H3)")
            for s in headings:
                st.write(f"- H2: {s.get('h2')}")
                for h3 in s.get("h3", []):
                    st.write(f"  - H3: {h3}")
            st.markdown("### Rewritten Article (Paragraph-wise)")
            for i,p in enumerate(paragraphs, start=1):
                st.write(f"Paragraph {i}: {p}")
            st.markdown("### Notes")
            for n in notes:
                st.write(f"- {n}")
            # Downloads
            article_id = f"URLART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
            schema = json_ld_schema(titles[0] if titles else "", meta, slug, author, publisher, section)
            docx_bytes = build_docx(titles[:3], meta, paragraphs, keywords, slug, headings, notes)
            st.download_button("Download DOCX", data=docx_bytes, file_name=f"{article_id}_patrika_seo.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.download_button("Download JSON-LD", data=schema, file_name=f"{article_id}_newsarticle.json", mime="application/ld+json")
            # HTML snippet
            canonical = fetched.get("canonical") or canonical_base.rstrip("/") + "/" + section.lower() + "/" + slug
            snippet = f"""<!-- SEO snippet start -->
<title>{html.escape(titles[0])}</title>
<meta name="description" content="{html.escape(meta)}">
<link rel="canonical" href="{html.escape(canonical)}">
<script type="application/ld+json">
{schema}
</script>
<!-- SEO snippet end -->"""
            st.markdown("### HTML snippet")
            st.code(snippet, language="html")
elif mode == "Paste Article(s)":
    st.subheader("Paste one or more articles. Use blank line + --- + blank line to separate multiple articles.")
    news_text = st.text_area("Paste article(s) (headline optional)", height=360, placeholder="हेडलाइन (optional)\n\nलेख... \n\n---\n\n(Next article)")
    if st.button("Rewrite & Suggest (Paste mode)", disabled=not news_text.strip()):
        parts = [p.strip() for p in re.split(r'\n{0,}\-{3,}\n{0,}', news_text) if p.strip()]
        for idx, part in enumerate(parts, start=1):
            st.markdown(f"---\n## Pasted Article {idx}")
            # try to detect a first-line headline if short
            lines = [l.strip() for l in part.splitlines() if l.strip()]
            possible_title = ""
            body = part
            if len(lines) >= 2 and len(lines[0].split()) <= 12:
                possible_title = lines[0]
                body = "\n".join(lines[1:])
            cleaned = remove_byline_and_meta(body)
            if not cleaned or len(cleaned.split()) < 20:
                st.warning("Pasted article appears short after cleaning. Ensure full article pasted.")
            # OpenAI or fallback
            suggested = None
            if HAS_OPENAI and get_openai_key():
                with st.spinner("Calling OpenAI for structured rewrite..."):
                    suggested = call_openai_structured(cleaned, original_title=possible_title, language="hi")
            if not suggested:
                suggested = fallback_generate(cleaned, original_title=possible_title)
            titles = suggested.get("titles") if suggested.get("titles") else []
            meta = suggested.get("meta","")
            slug = suggested.get("slug") or slugify(titles[0] if titles else "article")
            keywords = suggested.get("keywords") or top_keywords(cleaned, n=6)
            headings = suggested.get("headings") or []
            paragraphs = suggested.get("paragraphs") or [cleaned]
            notes = suggested.get("notes") or []
            # display
            st.markdown("### Suggested Titles (3 options)")
            for i, t in enumerate(titles[:3], start=1):
                st.write(f"{i}. {t}")
            st.markdown("### SEO Meta")
            st.write(meta)
            st.markdown("### Suggested URL Slug")
            st.code(slug)
            st.markdown("### Suggested Headings (H2 / H3)")
            for s in headings:
                st.write(f"- H2: {s.get('h2')}")
                for h3 in s.get("h3", []):
                    st.write(f"  - H3: {h3}")
            st.markdown("### Rewritten Article (Paragraph-wise)")
            for i,p in enumerate(paragraphs, start=1):
                st.write(f"Paragraph {i}: {p}")
            st.markdown("### Notes")
            for n in notes:
                st.write(f"- {n}")
            # downloads
            article_id = f"PASTEART-{datetime.now().strftime('%Y%m%d%H%M%S')}-{idx}"
            schema = json_ld_schema(titles[0] if titles else "", meta, slug, author, publisher, section)
            docx_bytes = build_docx(titles[:3], meta, paragraphs, keywords, slug, headings, notes)
            st.download_button("Download DOCX", data=docx_bytes, file_name=f"{article_id}_patrika_seo.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.download_button("Download JSON-LD", data=schema, file_name=f"{article_id}_newsarticle.json", mime="application/ld+json")
            canonical = canonical_base.rstrip("/") + "/" + section.lower() + "/" + slug
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

st.markdown("---")
st.caption("Tip: For best extraction from JS-heavy sites, paste article text in Paste mode. To use OpenAI for better rewrites, add your API key in Streamlit secrets or environment variable OPENAI_API_KEY.")
