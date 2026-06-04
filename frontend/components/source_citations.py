"""
frontend/components/source_citations.py
Renders collapsible source citations in Streamlit.
"""
import streamlit as st


def render_sources(sources: list[dict]) -> None:
    """Render a collapsible expander showing retrieved source chunks."""
    if not sources:
        return

    with st.expander(f"📚 Sources ({len(sources)} retrieved)", expanded=False):
        for i, src in enumerate(sources, 1):
            source_name = src.get("source", "Unknown")
            doc_type = src.get("doc_type", "")
            url = src.get("url", "")
            excerpt = src.get("excerpt", "")

            icon = "📄" if doc_type == "resume" else "💻"
            st.markdown(f"**{icon} [{i}] `{source_name}`**")

            if url:
                st.markdown(f"🔗 [{url}]({url})")

            if excerpt:
                st.caption(f"> {excerpt[:300]}{'...' if len(excerpt) > 300 else ''}")

            if i < len(sources):
                st.divider()
