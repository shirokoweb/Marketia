"""Streamlit entry point.

Run with: ``streamlit run streamlit_app.py``

This shim keeps the project root tidy for Streamlit Community Cloud, which
defaults to a file at the repository root. All UI logic lives in
``marketia/ui/app.py``.
"""

from marketia.ui.app import main

main()
