#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Website Suggestion Assistant
--------------------------------
A minimal Streamlit app that:
- Extracts a product category from a free-form query using categories.json
- Suggests websites from websites.json for that category
- Uses LangChain + OpenAI to generate short, helpful reasoning per website
- Displays clickable links and an assistant suggestion

How to run locally:
1) Install dependencies:
   pip install streamlit langchain langchain-openai openai tiktoken

2) Set your OpenAI API key (example for macOS/Linux):
   export OPENAI_API_KEY="your_openai_api_key"

3) Start the app:
   streamlit run app.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

# LangChain + OpenAI (modern imports)
try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
except Exception:
    # Provide a helpful message if imports fail
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore
    StrOutputParser = None  # type: ignore


# ---------- Config ----------

APP_TITLE = "AI Website Suggestion Assistant"
APP_CAPTION = "Enter what you want to buy. I’ll suggest the best sites and why."

DATA_DIR = Path("data")
CATEGORIES_FILE = DATA_DIR / "categories.json"
WEBSITES_FILE = DATA_DIR / "websites.json"

DEFAULT_MODEL = "gpt-4o-mini"  # keep costs low; change to another supported model if needed
TEMPERATURE = 0.2

# ---------- Helpers ----------


def load_json(path: Path) -> dict:
    """Load a JSON file and return a dict. Raises FileNotFoundError/JSONDecodeError on error."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_keyword_index(categories_map: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Invert the categories map into a keyword->category index.
    e.g., {"electronics": ["laptop", "mobile"]} -> {"laptop": "electronics", "mobile": "electronics"}
    """
    index: Dict[str, str] = {}
    for category, keywords in categories_map.items():
        for kw in keywords:
            index[kw.lower().strip()] = category
    return index


def detect_category(query: str, categories_map: Dict[str, List[str]]) -> Optional[str]:
    """
    Very simple keyword-based category detection.
    - Lowercases query
    - Checks if any keyword for a category is a substring of the query
    Returns the first category with the highest keyword match count (basic tie-breaker).
    """
    text = query.lower()
    best_cat = None
    best_score = 0

    for category, keywords in categories_map.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_cat = category

    return best_cat if best_score > 0 else None


def ensure_llm() -> Optional[ChatOpenAI]:
    """
    Configure the LangChain OpenAI chat model if available and OPENAI_API_KEY is set.
    Returns None if not configured (app will gracefully fall back).
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    if ChatOpenAI is None:
        return None

    # ChatOpenAI uses OPENAI_API_KEY from environment automatically
    try:
        llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=TEMPERATURE)
        return llm
    except Exception:
        return None


def generate_reasons_for_websites(
    llm: ChatOpenAI,
    user_query: str,
    category: str,
    websites: List[Dict[str, str]],
) -> Dict[str, str]:
    """
    Use the LLM to produce a short, tailored reason for each website.
    Returns a dict {website_name: reason}. Falls back to basic reasons on any error.
    """
    # Build a concise description of each website for the prompt
    website_lines = []
    for w in websites:
        strengths = w.get("strengths", [])
        strengths_txt = ", ".join(strengths) if strengths else "general strengths"
        website_lines.append(f"- {w['name']}: {strengths_txt}")

    # Prompt instructs JSON-only output for easy parsing
    prompt = ChatPromptTemplate.from_template(
        """You are a helpful shopping assistant.
User's query: "{user_query}"
Detected category: "{category}"

Below is a list of websites and their typical strengths. For EACH website, write ONE short sentence (<=22 words) explaining WHY it's a good choice specifically for this user's query and context (consider Indian market and budget hints if present).

Websites:
{website_list}

Output rules:
- Return a VALID JSON object only, no markdown or extra text.
- Keys MUST be exactly the website names from the list above.
- Values are the one-sentence reasons.

Example format:
{
  "Amazon India": "Reason here.",
  "Flipkart": "Reason here."
}"""
    )

    chain = prompt | llm | StrOutputParser()

    try:
        raw = chain.invoke(
            {
                "user_query": user_query,
                "category": category,
                "website_list": "\n".join(website_lines),
            }
        )
        # Parse JSON; if it fails, fall back
        reasons = json.loads(raw)
        if not isinstance(reasons, dict):
            raise ValueError("Model did not return a JSON object.")
        # Keep only known website names
        allowed = {w["name"] for w in websites}
        filtered = {k: str(v) for k, v in reasons.items() if k in allowed}
        return filtered
    except Exception:
        # Fallback deterministic reasons
        return build_fallback_reasons(websites, category, user_query)


def build_fallback_reasons(
    websites: List[Dict[str, str]],
    category: str,
    user_query: str,
) -> Dict[str, str]:
    """
    If LLM is not available or output fails to parse, produce a basic reason from strengths.
    """
    reasons: Dict[str, str] = {}
    for w in websites:
        strengths = w.get("strengths", [])
        strength_tip = ", ".join(strengths[:2]) if strengths else "good selection and reliability"
        reasons[w["name"]] = f"Great for {category}; known for {strength_tip}."
    return reasons


def render_links_with_reasons(websites: List[Dict[str, str]], reasons: Dict[str, str]) -> None:
    """
    Render a clean list of clickable links with short reasons.
    """
    for w in websites:
        name = w["name"]
        url = w.get("url", "#")
        reason = reasons.get(name, "").strip()
        # Clickable link + short reason
        st.markdown(f"- [{name}]({url}) — {reason}")


# ---------- Streamlit UI ----------

st.set_page_config(page_title=APP_TITLE, page_icon="🤖", layout="centered")

st.title(APP_TITLE)
st.caption(APP_CAPTION)

with st.expander("About this app"):
    st.write(
        "This app uses a small JSON dataset to map product keywords to categories and "
        "recommend popular websites for those categories. It uses OpenAI via LangChain "
        "to generate short, helpful reasons for each website. If the API key isn't set, "
        "the app still works with fallback reasons."
    )

user_query = st.text_input(
    "What do you want to buy?",
    placeholder="e.g., I want to buy a laptop under ₹50,000",
)

submit = st.button("Suggest Websites", type="primary")

if submit:
    if not user_query.strip():
        st.warning("Please enter a brief description of what you want to buy.")
        st.stop()

    # Load datasets
    try:
        categories_map = load_json(CATEGORIES_FILE)  # {category: [keywords]}
        websites_map = load_json(WEBSITES_FILE)      # {category: [{name,url,strengths}, ...]}
    except FileNotFoundError as e:
        st.error(f"Dataset file missing: {e}")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse dataset JSON: {e}")
        st.stop()

    # Detect category
    category = detect_category(user_query, categories_map)
    if not category:
        st.info(
            "I couldn't recognize the category from your query. "
            "Try being more specific (e.g., 'gaming laptop', 'wooden dining table', 'running shoes')."
        )
        st.stop()

    # Pull websites for this category
    sites: List[Dict[str, str]] = websites_map.get(category, [])
    if not sites:
        st.info(
            f"I found the category '{category}', but I don't have websites for it yet. "
            "Please update websites.json with entries for this category."
        )
        st.stop()

    # Generate reasons (LLM if available, else fallback)
    llm = ensure_llm()
    if llm is None:
        st.warning(
            "OPENAI_API_KEY not configured or LangChain OpenAI not available. "
            "Showing fallback reasons."
        )
        reasons = build_fallback_reasons(sites, category, user_query)
    else:
        reasons = generate_reasons_for_websites(llm, user_query, category, sites)

    # Present results
    st.subheader("🤖 Assistant’s suggestion")
    st.write(
        f"Based on your query, here are some good places to shop for {category}."
    )
    render_links_with_reasons(sites, reasons)

    # Friendly hint
    st.caption(
        "Tip: Prices and availability can vary by city and time. "
        "Check return policies and warranty before purchasing."
)
