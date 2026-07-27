import requests
import streamlit as st
from config import BACKEND_API_URL

st.set_page_config(page_title="Trustee Compliance Reporting", page_icon="📋")
st.title("Monthly Trustee Compliance Reporting")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
    st.session_state.report = None
    st.session_state.finalized = None

if st.button(
    "Run Trustee Compliance Report",
    disabled=st.session_state.thread_id is not None,
):
    with st.spinner(
        "Running the compliance pipeline — this calls the AI a few times, please wait..."
    ):
        try:
            resp = requests.post(
                f"{BACKEND_API_URL}/reports/trustee-compliance/run", timeout=120
            )
        except requests.RequestException as e:
            st.error(f"Could not reach the backend API: {e}")
            resp = None

    if resp is not None:
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.thread_id = data["thread_id"]
            st.session_state.report = data["report"]
            st.session_state.finalized = None
        else:
            st.error(f"Failed to run report: {resp.text}")

if st.session_state.report:
    st.markdown("### Draft Report")
    st.markdown(st.session_state.report)

    if st.session_state.finalized is None:
        st.markdown("### Trustee Decision")
        actor = st.text_input("Your name")
        comment = st.text_area("Comment (optional)")
        col1, col2 = st.columns(2)
        with col1:
            approve_clicked = st.button("Approve", type="primary", disabled=not actor)
        with col2:
            reject_clicked = st.button("Reject", disabled=not actor)

        if approve_clicked or reject_clicked:
            decision = "approved" if approve_clicked else "rejected"
            try:
                resp = requests.post(
                    f"{BACKEND_API_URL}/reports/trustee-compliance/"
                    f"{st.session_state.thread_id}/decision",
                    json={
                        "decision": decision,
                        "actor": actor,
                        "comment": comment or None,
                    },
                    timeout=30,
                )
            except requests.RequestException as e:
                st.error(f"Could not reach the backend API: {e}")
                resp = None

            if resp is not None:
                if resp.status_code == 200:
                    st.session_state.finalized = resp.json()
                    st.rerun()
                else:
                    st.error(f"Failed to submit decision: {resp.text}")

    if st.session_state.finalized:
        data = st.session_state.finalized
        if data["event_type"] == "report_approved":
            st.success(f"Report approved and finalized. Audit log ID: {data['audit_log_id']}")
        else:
            st.warning(f"Report rejected. Audit log ID: {data['audit_log_id']}")

        if st.button("Start a new report run"):
            st.session_state.thread_id = None
            st.session_state.report = None
            st.session_state.finalized = None
            st.rerun()
