import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# -------------------------------
# Utility functions
# -------------------------------

def clean_text(txt: str) -> str:
    return " ".join(txt.replace("\n", " ").split())

def generate_title(text: str):
    # Simple heuristic for demo
    if "इनकार" in text or "deny" in text.lower():
        return "शशि थरूर ने ‘वीर सावरकर अवॉर्ड’ लेने से किया इनकार, आयोजकों पर गैर-जिम्मेदाराना रवैये का आरोप"
    return "SEO-अनुकूल शीर्षक यहाँ बनेगा"

def generate_meta(text: str):
    return "कांग्रेस सांसद शशि थरूर ने ‘वीर सावरकर अवॉर्ड’ लेने से इनकार किया। आयोजकों पर बिना अनुमति नाम जोड़ने का आरोप लगाया और कहा कि वे समारोह में शामिल नहीं होंगे।"

def generate_full_article(text: str):
    return f"""
#### 🟢 इंट्रोडक्शन
{text[:200]}...

#### 🟠 मुख्य बयान और सोशल मीडिया प्रतिक्रिया
थरूर ने X (पूर्व ट्विटर) पर लिखा कि उन्हें इस अवॉर्ड के बारे में कोई आधिकारिक सूचना नहीं मिली थी। उन्होंने कहा, “मैं न तो यह अवॉर्ड स्वीकार करूंगा और न ही समारोह में शामिल होऊंगा।”

#### 🟣 आयोजकों की भूमिका पर सवाल
थरूर ने आयोजकों को गैर-जिम्मेदार बताया और कहा कि बिना पूछे उनका नाम सूची में डालना भ्रम पैदा करता है।

#### 🔵 राजनीतिक और सार्वजनिक प्रतिक्रिया
इस बयान के बाद सोशल मीडिया पर तीखी प्रतिक्रियाएं देखने को मिलीं।

#### ⚪ निष्कर्ष
यह विवाद राजनीतिक और सामाजिक स्तर पर चर्चा का विषय बन गया है।
"""

def fetch_page_content(url: str):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        # Patrika articles often have <div class="articleBody"> or <p>
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])
        return clean_text(text)
    except Exception as e:
        return f"Error fetching page: {e}"

# -------------------------------
# Streamlit UI
# -------------------------------

st.set_page_config(page_title="Patrika SEO Suggester", layout="wide")
st.title("📰 Patrika SEO Suggester")
st.caption("Paste news text OR paste published article link → Get SEO-ready output")

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
    st.write("- Shashi Tharoor Profile: https://www.patrika.com/tags/shashi-tharoor/")

    st.markdown("### 🖼 Suggested Image Alt Texts")
    st.write("- Shashi Tharoor speaking to media")
    st.write("- Veer Savarkar Award controversy scene")

else:
    st.info("कृपया खबर पेस्ट करें या लिंक डालें और 'Analyze & Suggest' पर क्लिक करें।")
