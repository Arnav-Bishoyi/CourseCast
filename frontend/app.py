import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
import requests
import streamlit as st

API = os.environ.get("COURSECAST_API_URL", "http://127.0.0.1:8000").rstrip("/")
TZ = ZoneInfo("America/Chicago")
st.set_page_config(page_title="CourseCast demo", page_icon="📚", layout="centered")
st.title("CourseCast")
st.warning("Demo data only. Course IDs, CRNs, statuses and probabilities below are synthetic. Do not use for registration decisions.")
st.caption("Will a section remain open until your registration ticket? This is the starter interface, not a trained forecaster.")

def api_call(method, path, **kwargs):
    try:
        response = requests.request(method, API + path, timeout=10, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            st.error(f"API returned {response.status_code}: {detail}")
            return None
        return response.json()
    except (requests.RequestException, ValueError) as error:
        st.error(f"Could not load the demo API: {error}. Start the backend first.")
        return None

payload = api_call("GET", "/sections", params={"term": "2027-spring"})
if payload is None:
    st.stop()
sections = payload["sections"]
if not sections:
    st.info("No sections found for this term.")
    st.stop()
labels = {s["crn"]: f'{s["subject"]} {s["course_number"]} {s["section_number"]} ({s["crn"]})' for s in sections}
with st.form("forecast"):
    crn = st.selectbox("Section", list(labels), format_func=labels.get)
    day = st.date_input("Ticket date (America/Chicago)", value=datetime(2026, 10, 13).date())
    clock = st.time_input("Ticket time (America/Chicago)", value=time(12, 0))
    submitted = st.form_submit_button("Show demo forecast")
if submitted:
    ticket = datetime.combine(day, clock, tzinfo=TZ)
    result = api_call("POST", "/forecast", json={"term": "2027-spring", "crn": crn, "ticket_at": ticket.isoformat()})
    if result:
        st.session_state["result"] = result
        st.session_state["section"] = next(s for s in sections if s["crn"] == crn)
result = st.session_state.get("result")
if result:
    st.subheader("Demo result")
    st.caption(f'Ticket requested: {result["ticket_at"]} (UTC)')
    if result["forecast_status"] == "available":
        st.metric("Demo probability of remaining open", f'{result["probability"]:.0%}')
        import pandas as pd
        frame = pd.DataFrame(result["curve"])
        frame["at"] = pd.to_datetime(frame["at"], utc=True).dt.tz_convert(TZ)
        st.line_chart(frame.set_index("at")["probability"], y_label="Probability (0 to 1)", x_label="America/Chicago")
    else:
        st.info(result["message"])
    if result["is_stale"]:
        st.warning("The synthetic observation is older than two hours. A live app must flag stale data too.")
    with st.expander("Section detail", expanded=True):
        section = st.session_state["section"]
        st.write(f'Source status: {section["status"]} (synthetic)')
        st.write(f'Observation: {result["observed_at"]} (UTC)')
        st.write(f'Demo source: {result["source"]}')
        st.caption("Grade history is not connected yet.")
        st.json(section)
