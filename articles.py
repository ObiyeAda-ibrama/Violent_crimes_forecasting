import json
from typing import Any, Dict, List

import streamlit as st
import pandas as pd


# Try to import the low-level search tool from main.py
try:
    from main import threat_bulletin  # type: ignore
except Exception:  # pragma: no cover - streamlit runtime guard
    threat_bulletin = None  # type: ignore


def _normalize_results(raw_json: str) -> List[Dict[str, Any]]:
    """Parse the JSON string from threat_bulletin into a list of dicts.

    Expected schema per item:
    {"id": <qdrant_id>, "payload": {"load": str, "created_ts": str, "modified_ts": str, "name": str, "source": str, "link": str}}
    """
    try:
        data = json.loads(raw_json)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "error" in item:
            # Skip error entries; they will be surfaced separately in the UI
            continue
        qdrant_id = item.get("id")
        payload = item.get("payload", {}) or {}
        name = payload.get("name")
        created = payload.get("created_ts")
        modified = payload.get("modified_ts")
        load = payload.get("load")
        link = payload.get("link")

        normalized.append(
            {
                "id": qdrant_id,
                "Name": name,
                "Created": created,
                "Modified": modified,
                "Load": load,
                "Link": link,
            }
        )

    return normalized


def _ensure_session_state():
    if "articles_df" not in st.session_state:
        st.session_state["articles_df"] = pd.DataFrame(
            columns=["id", "Name", "Created", "Modified", "Load", "Link"]
        )
    if "seen_ids" not in st.session_state:
        st.session_state["seen_ids"] = set()


def _append_unique_rows(rows: List[Dict[str, Any]]):
    if not rows:
        return
    df_new = pd.DataFrame(rows)
    if df_new.empty:
        return

    # Drop exact duplicates within the new batch by 'id'
    if "id" in df_new.columns:
        df_new = df_new.drop_duplicates(subset=["id"], keep="first")

    # Filter out rows whose ids have already been seen in this session
    seen_ids = st.session_state["seen_ids"]
    if "id" in df_new.columns:
        df_new = df_new[~df_new["id"].isin(seen_ids)]

    if df_new.empty:
        return

    # Append and de-duplicate the accumulated dataframe by 'id'
    st.session_state["articles_df"] = (
        pd.concat([st.session_state["articles_df"], df_new], ignore_index=True)
        .drop_duplicates(subset=["id"], keep="first")
    )

    # Update the seen id set
    for value in df_new["id"].dropna().tolist():
        seen_ids.add(value)


def main():
    st.set_page_config(page_title="Threat Bulletins", layout="wide")
    st.title("Threat Bulletins")

    _ensure_session_state()

    query = st.text_input("Enter search query", value="")

    col_run, col_clear = st.columns([1, 1])
    with col_run:
        run = st.button("Search", type="primary")
    with col_clear:
        clear = st.button("Clear Results")

    if clear:
        st.session_state["articles_df"] = st.session_state["articles_df"].iloc[0:0]
        st.session_state["seen_ids"] = set()

    # Perform search when requested
    if run:
        if threat_bulletin is None:
            st.error("Cannot import 'threat_bulletin' from main.py. Ensure it exists and is importable.")
        else:
            with st.spinner("Searching threat bulletins..."):
                raw = threat_bulletin(query)
                # Also surface errors if present
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = []
                for item in parsed:
                    if isinstance(item, dict) and "error" in item:
                        st.warning(f"Search error: {item['error']}")
                rows = _normalize_results(raw)
                _append_unique_rows(rows)

    df_display = st.session_state["articles_df"]

    # Show only requested columns
    columns_to_show = ["Name", "Created", "Modified", "Load", "Link"]
    if not df_display.empty:
        st.dataframe(
            df_display[columns_to_show],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No results yet. Enter a query and click Search.")


def articles_card():
    """Display a card with article names from the session dataframe.

    - If the dataframe is not found in session state -> show "Article records file not found."
    - If the dataframe exists but has no rows -> show "No articles have been generated yet."
    - Otherwise, show a list of article names and a link to the Articles page.
    """
    with st.container():
        st.page_link("articles.py", label="Articles", icon=":material/articles:")

        df = st.session_state.get("articles_df")
        columns_to_show = ["Name", "Created", "Modified", "Load", "Link"]

        if df is None:
            st.write("Article records file not found.")
            return

        # Names list
        if "Name" in df.columns:
            names_series = df["Name"].dropna().astype(str).drop_duplicates()
            if names_series.empty:
                st.write("No articles have been generated yet.")
            else:
                for article_name in names_series.tolist():
                    st.markdown(f"- {article_name}")
        else:
            st.write("No articles have been generated yet.")

        # Always display the dataframe if available (even if empty)
        df_to_show = df.copy()
        for col in columns_to_show:
            if col not in df_to_show.columns:
                df_to_show[col] = None
        st.dataframe(
            df_to_show[columns_to_show],
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()

