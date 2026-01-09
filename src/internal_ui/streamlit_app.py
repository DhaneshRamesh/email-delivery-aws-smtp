"""Streamlit internal UI for sending test emails via the API."""
from __future__ import annotations

import os

import requests
import streamlit as st


def api_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def _resolve_api_base() -> str:
    override = st.session_state.get("api_base_override", "").strip()
    if override:
        return override
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").strip()


def main() -> None:
    st.set_page_config(page_title="Email Delivery UI", layout="centered")
    st.title("Email Delivery UI")

    api_base = _resolve_api_base()
    st.caption(f"API base: {api_base}")

    with st.sidebar:
        st.subheader("API Settings")
        st.text_input(
            "API base override",
            key="api_base_override",
            help="Optional override for the API base URL.",
        )
        st.caption(f"Resolved API base: {api_base}")
        if st.button("Test API"):
            try:
                response = requests.get(api_url(api_base, "/health"), timeout=10)
                if response.status_code == 404:
                    response = requests.get(api_url(api_base, "/api/health"), timeout=10)
                if response.ok:
                    st.success(f"API OK ({response.status_code})")
                else:
                    st.error(f"API check failed ({response.status_code})")
                    st.text(response.text)
            except requests.RequestException as exc:
                st.error(f"API check failed: {exc}")

    to_email = st.text_input("To", value="success@simulator.amazonses.com")
    subject = st.text_input("Subject", value="UI test")
    body = st.text_area("Body", value="hello", height=160)
    enqueue = st.checkbox("Enqueue (send via worker)", value=False)

    if st.button("Send"):
        if not to_email.strip() or not subject.strip():
            st.error("To and Subject are required.")
            return

        payload = {
            "recipient": to_email.strip(),
            "subject": subject.strip(),
            "body": body,
            "enqueue": enqueue,
        }
        try:
            response = requests.post(api_url(api_base, "/send/send-test"), json=payload, timeout=10)
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
            return

        st.write(f"HTTP {response.status_code}")
        try:
            data = response.json()
            st.json(data)
            message_id = data.get("message_id") or data.get("MessageId")
            if message_id:
                st.success(f"Message ID: {message_id}")
        except ValueError:
            st.write(response.text)


if __name__ == "__main__":
    main()
