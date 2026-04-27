"""Streamlit entry point for Marketia. Invoked by ``streamlit_app.py``."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from marketia.core import (
    RESEARCH_MODEL_FAST,
    RESEARCH_MODEL_MAX,
    MissingAPIKeyError,
    configure_logging,
    load_client,
)
from marketia.settings import get_file_search_stores, set_file_search_stores
from marketia.ui.styles import CUSTOM_CSS
from marketia.ui.tabs import followup_tab, new_research_tab


def _render_sidebar() -> tuple[str, str, str, list[str]]:
    """Render the sidebar and return ``(api_key, output_dir, agent_model, file_search_stores)``."""
    with st.sidebar:
        st.header("Settings")
        env_key = os.getenv("GOOGLE_API_KEY", "")
        api_key = st.text_input(
            "Google API Key",
            value=env_key,
            type="password",
            help="Your Google AI Studio API key",
        )
        if not api_key:
            st.warning("Please enter your API Key to proceed.")
            st.stop()

        st.divider()
        speed = st.radio(
            "Speed vs. Depth",
            options=["Fast", "Max"],
            help=(
                "**Fast** (~$1–3): quick, broad insights.\n\n"
                "**Max** (~$3–7): deeper, more comprehensive analysis."
            ),
            horizontal=True,
            key="agent_speed",
        )
        agent_model = RESEARCH_MODEL_MAX if speed == "Max" else RESEARCH_MODEL_FAST

        st.divider()
        env_vault = os.getenv("OBSIDIAN_VAULT_PATH", "")
        output_dir = st.text_input(
            "Output Directory",
            value=env_vault,
            placeholder="/Users/you/Obsidian/Research/",
            help="Path to save reports. Leave empty to save in current directory.",
        )

        if output_dir:
            resolved = Path(output_dir).expanduser()
            if not resolved.is_dir():
                st.warning(f"Directory not found: {resolved}")
                output_dir = ""
            else:
                output_dir = str(resolved)
                st.caption(f"📁 Saving to: `{output_dir}`")

        st.divider()
        with st.expander("Private Data (file_search)"):
            st.caption(
                "Add Gemini file-search store names to query your private corpus. "
                "Stores are created out-of-band via the Gemini API."
            )
            saved_stores = get_file_search_stores()
            stores_text = st.text_area(
                "Store names (one per line)",
                value="\n".join(saved_stores),
                placeholder="fileSearchStores/my-corpus",
                key="file_search_stores_input",
            )
            if st.button("Save stores", key="save_stores"):
                parsed = [s.strip() for s in stores_text.splitlines() if s.strip()]
                set_file_search_stores(parsed)
                st.success(f"Saved {len(parsed)} store(s).")
            file_search_stores = [s.strip() for s in stores_text.splitlines() if s.strip()]

        st.info("Status: Ready")
        return api_key, output_dir, agent_model, file_search_stores


def _get_client(api_key: str):
    """Cache the genai client across reruns via session state."""
    cached = st.session_state.get("_client_for_key")
    if cached and cached[0] == api_key:
        return cached[1]
    try:
        client = load_client(api_key)
    except MissingAPIKeyError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state["_client_for_key"] = (api_key, client)
    return client


def main() -> None:
    """Configure the page and render the tabs."""
    load_dotenv()
    configure_logging(level=logging.INFO)
    st.set_page_config(
        page_title="Marketia Research",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    api_key, output_dir, agent_model, file_search_stores = _render_sidebar()
    client = _get_client(api_key)

    st.title("📊 Marketia Research Hub")

    tab1, tab2 = st.tabs(["🚀 New Research", "🔍 Follow-up Analysis"])
    with tab1:
        new_research_tab(
            client, output_dir, agent=agent_model, file_search_stores=file_search_stores
        )
    with tab2:
        followup_tab(client, output_dir, agent=agent_model, file_search_stores=file_search_stores)


main()
