# Website Suggestion Assistant (Streamlit)
# Features:
# 1) Input a shopping query
# 2) Extract product category via keywords (from categories.json)
# 3) Suggest websites from websites.json
# 4) Optionally use LangChain + OpenAI to generate short reasons (fallback if unavailable)
# 5) Show Assistant suggestion with clickable links
# 6) Friendly error if category not recognized

import json
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse  # for deep-link building

import streamlit as st

# Try to use LangChain + OpenAI if available and if OPENAI_API_KEY is set.
try:
    from langchain_openai import ChatOpenAI  # Requires: langchain-openai
    _lc_available = True
except Exception:
    _lc_available = False


# ---------- Config & Helpers ----------

@st.cache_data(show_spinner=False)
def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _data_path(*parts: str) -> str:
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, *parts)

def load_datasets() -> Tuple[Dict, Dict]:
    categories = load_json(_data_path("data", "categories.json"))
    websites = load_json(_data_path("data", "websites.json"))
    return categories, websites

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()

def extract_category(query: str, categories: Dict) -> Optional[str]:
    """
    Simple keyword-based category extraction.
    Returns the best matching category name or None if not found.
    """
    q = normalize_text(query)
    best_cat = None
    best_score = 0
    for cat, cfg in categories.items():
        kws = cfg.get("keywords", [])
        score = sum(1 for kw in kws if re.search(rf"\b{re.escape(kw.lower())}\b", q))
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat if best_score > 0 else None

def budget_present(query: str) -> bool:
    q = normalize_text(query)
    # Examples: "₹50,000", "under 50000", "rs 2000", "rupees 1500"
    return bool(re.search(r"(₹|rs\.?|rupees?)\s*\d[\d,]*|under\s*\d[\d,]*", q))

def deterministic_reason(site_name: str, category: str, query: str) -> str:
    has_budget = budget_present(query)
    base = f"{site_name} is a reliable place to browse {category} with broad selection, trusted sellers, and convenient delivery."
    if category == "electronics":
        base = f"{site_name} offers a strong range of electronics with specs filters, trusted warranties, and quick delivery options."
    elif category == "fashion":
        base = f"{site_name} features extensive fashion catalogs, frequent discounts, and easy returns for size or style."
    elif category == "furniture":
        base = f"{site_name} lists sturdy furniture with style/size filters, clear specs, and delivery/assembly support."
    if has_budget:
        base += " Use price filters and deals to stay within your budget."
    return base

def make_llm():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not _lc_available or not api_key:
        return None
    try:
        # gpt-4o-mini is a good balance of cost/quality; adjust as you like.
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=api_key)
    except Exception:
        return None

def reason_with_llm(llm, query: str, category: str, site_name: str, site_url: str) -> str:
    """
    Generate a single short sentence reason with LangChain + OpenAI.
    Falls back to deterministic_reason on any error.
    """
    try:
        prompt = (
            "You are a helpful shopping assistant for India. "
            "Given a user shopping query, a product category, and a website, write ONE short, specific sentence "
            "(max 25 words) explaining why the site is a good place to buy. "
            "Be factual. Don't invent prices or stock. If budget is mentioned, suggest using filters/deals.\n\n"
            f"User query: {query}\n"
            f"Category: {category}\n"
            f"Website: {site_name} ({site_url})\n"
            "Answer:"
        )
        # ChatOpenAI.invoke accepts a string prompt and returns an object with .content
        result = llm.invoke(prompt)
        text = (result.content or "").strip()
        if not text:
            raise ValueError("Empty LLM response")
        # Keep it to one sentence; trim if overly long.
        text = re.split(r"[\.!?]", text)[0].strip()
        return text + "."
    except Exception:
        return deterministic_reason(site_name, category, query)

def to_slug(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "search"

def build_deep_link(site_name: str, base_url: str, query: str, category: str) -> str:
    """
    Build a deep search URL per site so users land on relevant results, not homepages.
    Includes Myntra's slug + rawQuery + p=1 pattern as requested.
    """
    host = urlparse(base_url).netloc.lower()
    q_norm = normalize_text(query)
    q_enc = quote(q_norm)

    # Electronics
    if "amazon.in" in host:
        if site_name.lower().startswith("amazon fashion") or category == "fashion":
            return f"https://www.amazon.in/s?k={q_enc}&i=apparel"
        return f"https://www.amazon.in/s?k={q_enc}"
    if "flipkart.com" in host:
        return f"https://www.flipkart.com/search?q={q_enc}"
    if "croma.com" in host:
        return f"https://www.croma.com/searchB?q={q_enc}"
    if "reliancedigital.in" in host:
        return f"https://www.reliancedigital.in/search?q={q_enc}"

    # Fashion
    if "myntra.com" in host:
        slug = to_slug(q_norm)
        return f"https://www.myntra.com/{slug}?rawQuery={q_enc}&p=1"
    if "ajio.com" in host:
        return f"https://www.ajio.com/search/?text={q_enc}"

    # Furniture
    if "pepperfry.com" in host:
        return f"https://www.pepperfry.com/site_product/search?q={q_enc}"
    if "ikea.com" in host:
        return f"https://www.ikea.com/in/en/search/?q={q_enc}"
    if "urbanladder.com" in host:
        return f"https://www.urbanladder.com/products/search?keywords={q_enc}"

    # Fallback
    return base_url


# ---------- Streamlit UI ----------

st.set_page_config(page_title="Website Suggestions", page_icon="🛒", layout="centered")
st.title("Website Suggestions for Your Purchase")
st.caption("Enter what you want to buy. The assistant will detect the category and suggest websites with a brief reason.")

query = st.text_input(
    "What are you looking to buy?",
    placeholder="e.g., I want to buy a laptop under ₹50,000",
)

submitted = st.button("Get suggestions")

if submitted:
    if not query.strip():
        st.warning("Please enter a shopping query to continue.")
        st.stop()

    try:
        categories, websites = load_datasets()
    except Exception:
        st.error("Could not load local datasets. Please ensure categories.json and websites.json are present.")
        st.stop()

    category = extract_category(query, categories)

    if not category:
        st.info("I couldn't recognize the product category. Try adding a few more details (e.g., 'laptop', 'sofa', or 'sneakers').")
        st.stop()

    sites: List[Dict[str, str]] = websites.get(category, [])
    if not sites:
        st.info(f"No websites configured for the '{category}' category yet. Please update websites.json.")
        st.stop()

    st.subheader("Assistant’s suggestion")
    st.write(f"For the category '{category}', here are some good places to start:")

    llm = make_llm()

    # Display each site with deep link + concise reason
    for site in sites:
        name = site.get("name", "Website")
        base_url = site.get("url", "#")

        deep_url = build_deep_link(name, base_url, query, category)  # use deep links
        reason = reason_with_llm(llm, query, category, name, deep_url) if llm else deterministic_reason(name, category, query)

        st.markdown(f"- [{name}]({deep_url})")
        st.caption(reason)

    st.divider()
    st.caption("Tip: You can expand categories and websites by editing the JSON files in streamlit-app/data.")
