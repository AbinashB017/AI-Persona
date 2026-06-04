"""
frontend/components/sidebar.py
Sidebar: backend status + interview booking form.
"""
import streamlit as st
from frontend.utils import api_client
import datetime


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🤖 Abinash AI Persona")
        st.markdown("*Powered by Llama 3.3 70B + RAG*")
        st.divider()

        # ── Backend health ──
        st.markdown("### 🩺 System Status")
        try:
            h = api_client.health()
            st.success(f"✅ Online — {h.get('documents_indexed', 0)} docs indexed")
            st.caption(f"Model: `{h.get('model', 'N/A')}`")
        except Exception:
            st.error("❌ Backend offline — start FastAPI first")

        st.divider()

        # ── Clear chat ──
        st.markdown("### 🗑️ Chat")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(datetime.datetime.now().timestamp())
            st.rerun()

        st.divider()

        # ── Book interview ──
        st.markdown("### 📅 Schedule an Interview")
        with st.form("booking_form", clear_on_submit=True):
            name = st.text_input("Your Name *")
            email = st.text_input("Your Email *")
            date = st.date_input(
                "Preferred Date *",
                min_value=datetime.date.today() + datetime.timedelta(days=1),
                value=datetime.date.today() + datetime.timedelta(days=2),
            )
            time_slot = st.selectbox(
                "Preferred Time (IST) *",
                ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"],
            )
            reason = st.text_area("Reason / Notes", placeholder="AI Engineer interview", height=68)
            submitted = st.form_submit_button("📬 Book Interview", use_container_width=True)

            if submitted:
                if not name or not email:
                    st.error("Name and email are required.")
                else:
                    with st.spinner("Booking..."):
                        try:
                            result = api_client.book_meeting(
                                name=name,
                                email=email,
                                date=date.strftime("%Y-%m-%d"),
                                time_slot=time_slot,
                                reason=reason or "Interview",
                            )
                            if result.get("success"):
                                st.success(result["message"])
                                if result.get("meeting_url"):
                                    st.markdown(f"[🎥 Join Meeting]({result['meeting_url']})")
                            else:
                                st.error(f"Booking failed: {result.get('message')}")
                        except Exception as e:
                            st.error(f"Error: {e}")

        st.divider()
        st.caption("© 2025 Abinash Behera — IIIT Nagpur")
