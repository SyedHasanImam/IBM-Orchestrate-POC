import requests
import streamlit as st
from config import BACKEND_API_URL

st.set_page_config(page_title="Orchestrate POC", page_icon="📋")
st.title("Orchestrate POC")


def render_workflow_tab(workflow_name: str, title: str, run_spinner_text: str) -> None:
    thread_key = f"{workflow_name}_thread_id"
    report_key = f"{workflow_name}_report"
    finalized_key = f"{workflow_name}_finalized"

    if thread_key not in st.session_state:
        st.session_state[thread_key] = None
        st.session_state[report_key] = None
        st.session_state[finalized_key] = None

    st.subheader(title)

    if st.button(
        f"Run {title}",
        disabled=st.session_state[thread_key] is not None,
        key=f"{workflow_name}_run_button",
    ):
        with st.spinner(run_spinner_text):
            try:
                resp = requests.post(
                    f"{BACKEND_API_URL}/reports/{workflow_name}/run", timeout=120
                )
            except requests.RequestException as e:
                st.error(f"Could not reach the backend API: {e}")
                resp = None

        if resp is not None:
            if resp.status_code == 200:
                data = resp.json()
                st.session_state[thread_key] = data["thread_id"]
                st.session_state[report_key] = data["report"]
                st.session_state[finalized_key] = None
            else:
                st.error(f"Failed to run report: {resp.text}")

    if st.session_state[report_key]:
        st.markdown("### Draft Report")
        st.markdown(st.session_state[report_key])

        if st.session_state[finalized_key] is None:
            st.markdown("### Reviewer Decision")
            actor = st.text_input("Your name", key=f"{workflow_name}_actor")
            comment = st.text_area("Comment (optional)", key=f"{workflow_name}_comment")
            col1, col2 = st.columns(2)
            with col1:
                approve_clicked = st.button(
                    "Approve",
                    type="primary",
                    disabled=not actor,
                    key=f"{workflow_name}_approve",
                )
            with col2:
                reject_clicked = st.button(
                    "Reject", disabled=not actor, key=f"{workflow_name}_reject"
                )

            if approve_clicked or reject_clicked:
                decision = "approved" if approve_clicked else "rejected"
                try:
                    resp = requests.post(
                        f"{BACKEND_API_URL}/reports/{workflow_name}/"
                        f"{st.session_state[thread_key]}/decision",
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
                        st.session_state[finalized_key] = resp.json()
                        st.rerun()
                    else:
                        st.error(f"Failed to submit decision: {resp.text}")

        if st.session_state[finalized_key]:
            data = st.session_state[finalized_key]
            if data["event_type"] == "report_approved":
                st.success(
                    f"Report approved and finalized. Audit log ID: {data['audit_log_id']}"
                )
            else:
                st.warning(f"Report rejected. Audit log ID: {data['audit_log_id']}")

            if st.button("Start a new report run", key=f"{workflow_name}_reset"):
                st.session_state[thread_key] = None
                st.session_state[report_key] = None
                st.session_state[finalized_key] = None
                st.rerun()


def render_catalog_tab() -> None:
    st.subheader("Agent Catalog")
    st.caption(
        "Pulled live from the agent_registry table — new workflows appear "
        "here once their YAML is loaded, with no frontend code changes."
    )
    try:
        resp = requests.get(f"{BACKEND_API_URL}/catalog", timeout=15)
    except requests.RequestException as e:
        st.error(f"Could not reach the backend API: {e}")
        return

    if resp.status_code != 200:
        st.error(f"Failed to load catalog: {resp.text}")
        return

    entries = resp.json()
    if not entries:
        st.info("No workflows registered yet.")
        return

    st.dataframe(entries, use_container_width=True, hide_index=True)


def render_chat_tab() -> None:
    st.subheader("Ask a Question")
    st.caption(
        "Ad hoc questions get routed to one specialist agent directly — "
        "this never runs the full report-generation pipelines above."
    )

    if "chat_thread_id" not in st.session_state:
        st.session_state.chat_thread_id = None
        st.session_state.chat_history = []

    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            if entry.get("routed_to"):
                st.caption(f"Routed to: {entry['routed_to']}")

    question = st.chat_input("Ask about holdings or compliance...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Routing to the right specialist..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_API_URL}/chat",
                        json={
                            "thread_id": st.session_state.chat_thread_id,
                            "message": question,
                        },
                        timeout=60,
                    )
                except requests.RequestException as e:
                    st.error(f"Could not reach the backend API: {e}")
                    resp = None

            if resp is not None:
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.chat_thread_id = data["thread_id"]
                    st.markdown(data["message"])
                    if data.get("routed_to"):
                        st.caption(f"Routed to: {data['routed_to']}")
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": data["message"],
                            "routed_to": data.get("routed_to"),
                        }
                    )
                else:
                    st.error(f"Failed to get a response: {resp.text}")

    if st.session_state.chat_history and st.button("Start a new conversation"):
        st.session_state.chat_thread_id = None
        st.session_state.chat_history = []
        st.rerun()


tab_trustee, tab_catalog, tab_chat = st.tabs(
    ["Trustee Compliance Reporting", "Agent Catalog", "Chat"]
)

with tab_trustee:
    render_workflow_tab(
        "trustee_compliance_reporting",
        "Monthly Trustee Compliance Reporting",
        "Running the compliance pipeline — this calls the AI a few times, please wait...",
    )

with tab_catalog:
    render_catalog_tab()

with tab_chat:
    render_chat_tab()
