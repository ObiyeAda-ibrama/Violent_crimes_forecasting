import json
from typing import Any, Dict, Iterable, List, Optional, Union

import pandas as pd
import streamlit as st


def _extract_description(payload: Dict[str, Any]) -> str:
    """Best-effort extraction of description text from the payload.

    The payload may contain a nested "load" object with a "Description" field,
    or it may use alternate keys such as "description".
    """
    if not isinstance(payload, dict):
        return ""

    load_value = payload.get("load")
    # If load is a dict and contains Description
    if isinstance(load_value, dict):
        description_candidate = load_value.get("Description")
        if isinstance(description_candidate, str):
            return description_candidate

    # Fallback common keys
    for key in ("Description", "description", "desc", "summary"):
        description_candidate = payload.get(key)
        if isinstance(description_candidate, str):
            return description_candidate

    # Nothing suitable found
    return ""


def _normalize_row(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a single search result into a table row.

    Expected item structure: {"id": <qdrant_id>, "payload": {...}}
    Returns a dict with the display columns and the internal ID for de-duplication.
    """
    if not isinstance(item, dict):
        return None

    qdrant_id = item.get("id")
    payload = item.get("payload")

    if qdrant_id is None or not isinstance(payload, dict):
        return None

    name_value = payload.get("name")
    created_value = payload.get("created_ts")
    modified_value = payload.get("modified_ts")
    link_value = payload.get("link")
    description_value = _extract_description(payload)

    return {
        "_ID": qdrant_id,  # internal column used for de-duplication only
        "Name": name_value if isinstance(name_value, str) else "",
        "Created": created_value if isinstance(created_value, str) else created_value,
        "Modified": modified_value if isinstance(modified_value, str) else modified_value,
        "Description": description_value,
        "Link": link_value if isinstance(link_value, str) else "",
    }


def _coerce_input_to_list(results_with_ids: Union[str, Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Accept either a JSON string or an iterable of dicts and return a list of dicts."""
    if isinstance(results_with_ids, str):
        try:
            parsed = json.loads(results_with_ids)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        return []
    # Already a python structure
    if isinstance(results_with_ids, Iterable):
        return [x for x in results_with_ids if isinstance(x, dict)]
    return []


def update_articles_dataframe(results_with_ids: Union[str, Iterable[Dict[str, Any]]]) -> pd.DataFrame:
    """Update session-stored articles dataframe using threat_bulletin results and return it.

    - Accepts the raw output from threat_bulletin (JSON string or list of dicts)
    - Normalizes to the display schema: Name, Created, Modified, Description, Link
    - De-duplicates based on the Qdrant ID so the same report is not saved twice
    - Stores the accumulated dataframe in st.session_state["articles_df"]
    """
    # Ensure session storage exists
    if "_seen_qdrant_ids" not in st.session_state:
        st.session_state["_seen_qdrant_ids"] = set()
    if "articles_df" not in st.session_state:
        st.session_state["articles_df"] = pd.DataFrame(
            columns=["Name", "Created", "Modified", "Description", "Link"]
        )

    raw_items = _coerce_input_to_list(results_with_ids)
    normalized_rows: List[Dict[str, Any]] = []

    for item in raw_items:
        # Skip error entries from the tool
        if "error" in item:
            continue
        row = _normalize_row(item)
        if not row:
            continue
        qdrant_id = row.get("_ID")
        if qdrant_id in st.session_state["_seen_qdrant_ids"]:
            continue
        st.session_state["_seen_qdrant_ids"].add(qdrant_id)
        normalized_rows.append(row)

    if normalized_rows:
        # Build a DataFrame for the new rows without the internal _ID column
        new_df = pd.DataFrame([{k: v for k, v in r.items() if k != "_ID"} for r in normalized_rows])
        st.session_state["articles_df"] = pd.concat(
            [st.session_state["articles_df"], new_df], ignore_index=True
        )

    return st.session_state["articles_df"]


def render_articles_dataframe(results_with_ids: Union[str, Iterable[Dict[str, Any]]]) -> None:
    """Convenience wrapper to update and display the dataframe in Streamlit."""
    df = update_articles_dataframe(results_with_ids)
    st.dataframe(df, use_container_width=True)

