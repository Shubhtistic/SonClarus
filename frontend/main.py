import streamlit as st
import httpx
import time

API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Sonclarus AI", layout="centered")

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "show_register" not in st.session_state:
    st.session_state.show_register = False
if "skip" not in st.session_state:
    st.session_state.skip = 0


def fetch_download_url(job_id: str, stage: str):
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    try:
        res = httpx.get(
            f"{API_BASE_URL}/download/{job_id}",
            params={"stage": stage},
            headers=headers,
        )
        if res.status_code == 200:
            return res.json().get("download_url")
        return None
    except Exception:
        return None


if not st.session_state.is_logged_in:
    st.title("Welcome to Sonclarus")

    if not st.session_state.show_register:
        st.subheader("Login to your account")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                try:
                    payload = {"username": email, "password": password}
                    response = httpx.post(f"{API_BASE_URL}/login", data=payload)

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.access_token = data.get("access_token")
                        st.session_state.is_logged_in = True
                        st.rerun()
                    else:
                        st.error(f"Login failed: {response.text}")
                except httpx.RequestError as e:
                    st.error(f"Connection failed: {e}")

        st.write("Don't have an account?")
        if st.button("Register Here"):
            st.session_state.show_register = True
            st.rerun()

    else:
        st.subheader("Create an account")
        with st.form("register_form"):
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Register")

            if submitted:
                try:
                    payload = {"email": new_email, "password": new_password}
                    response = httpx.post(f"{API_BASE_URL}/register", json=payload)

                    if response.status_code == 201:
                        data = response.json()
                        st.success("Registration successful!")
                        st.info(f"Your User ID: {data.get('id')}")
                        st.info("You have 100MB free storage available.")
                        if st.button("Go to Login"):
                            st.session_state.show_register = False
                            st.rerun()
                    else:
                        st.error(f"Registration failed: {response.text}")
                except httpx.RequestError as e:
                    st.error(f"Connection failed: {e}")

        if st.button("Back to Login"):
            st.session_state.show_register = False
            st.rerun()

else:
    with st.sidebar:
        st.title("Controls")
        if st.button("Logout", use_container_width=True):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            try:
                httpx.post(f"{API_BASE_URL}/logout", headers=headers)
            except Exception:
                pass
            st.session_state.access_token = None
            st.session_state.is_logged_in = False
            st.rerun()

        st.markdown("---")
        st.header("Job History")

        show_history = st.toggle("Load Processing History")

        if show_history:
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            try:
                jobs_res = httpx.get(
                    f"{API_BASE_URL}/jobs",
                    params={"skip": st.session_state.skip, "limit": 10},
                    headers=headers,
                )

                if jobs_res.status_code == 200:
                    jobs_data = jobs_res.json()
                    total_jobs = jobs_data.get("total", 0)
                    jobs_list = jobs_data.get("data", [])

                    if not jobs_list:
                        st.info("No jobs found.")
                    else:
                        for job in jobs_list:
                            filename = job.get("filename", "Unknown")
                            job_id = job.get("job_id", "")
                            summary = job.get("summary", "")

                            with st.expander(f"**{filename}**"):

                                if summary:
                                    st.markdown("**Summary:**")
                                    st.caption(summary)
                                    st.markdown("---")

                                if job_id:
                                    st.markdown("**Downloads:**")
                                    url_t = fetch_download_url(job_id, "transcribe")
                                    if url_t:
                                        st.link_button(
                                            "Transcript",
                                            url_t,
                                            use_container_width=True,
                                        )

                                    url_s1 = fetch_download_url(job_id, "separated1")
                                    if url_s1:
                                        st.link_button(
                                            "Speaker 1",
                                            url_s1,
                                            use_container_width=True,
                                        )

                                    url_s2 = fetch_download_url(job_id, "separated2")
                                    if url_s2:
                                        st.link_button(
                                            "Speaker 2",
                                            url_s2,
                                            use_container_width=True,
                                        )

                        st.markdown("---")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.session_state.skip > 0:
                                if st.button("Prev"):
                                    st.session_state.skip -= 10
                                    st.rerun()
                        with col2:
                            if st.session_state.skip + 10 < total_jobs:
                                if st.button("Next"):
                                    st.session_state.skip += 10
                                    st.rerun()
                        st.caption(
                            f"Showing {st.session_state.skip + 1}-{min(st.session_state.skip + 10, total_jobs)} of {total_jobs}"
                        )

            except Exception as e:
                st.error(f"Failed to load jobs: {e}")

    st.success("You are securely logged in!")
    st.markdown("---")

    st.subheader("1. Upload Audio")

    uploaded_file = st.file_uploader("Choose an audio file", type=["wav"])

    if uploaded_file is not None:
        st.write(f"**Filename:** {uploaded_file.name}")
        st.write(f"**Size:** {uploaded_file.size / (1024 * 1024):.2f} MB")
        st.audio(uploaded_file)

        if st.button("Start Processing Pipeline"):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}

            with st.status("Initializing Job...", expanded=True) as status:
                try:
                    status.update(label="Requesting secure S3 upload link...")

                    payload = {
                        "filename": uploaded_file.name,
                        "file_size_bytes": uploaded_file.size,
                    }

                    req_response = httpx.post(
                        f"{API_BASE_URL}/uploads/request", headers=headers, json=payload
                    )
                    req_response.raise_for_status()

                    upload_data = req_response.json()
                    job_id = upload_data["job_id"]
                    presigned_url = upload_data["presigned_post"]["url"]
                    presigned_fields = upload_data["presigned_post"]["fields"]

                    status.update(label="Uploading file directly to AWS S3...")

                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    }
                    s3_response = httpx.post(
                        presigned_url, data=presigned_fields, files=files
                    )

                    if s3_response.status_code == 204:
                        status.update(label="File secured. Notifying worker queue...")

                        confirm_response = httpx.post(
                            f"{API_BASE_URL}/uploads/confirm/{job_id}", headers=headers
                        )
                        confirm_response.raise_for_status()

                        status.update(
                            label="Job successfully queued!", state="complete"
                        )
                        st.success(
                            "File uploaded! Open the sidebar history to check its status."
                        )
                        time.sleep(2)
                        st.rerun()

                    else:
                        status.update(label="S3 Upload Failed", state="error")
                        st.error(f"AWS Error: {s3_response.text}")

                except httpx.HTTPStatusError as e:
                    status.update(label="API Error", state="error")
                    st.error(f"Backend rejected the request: {e.response.text}")
                except Exception as e:
                    status.update(label="Unexpected Error", state="error")
                    st.error(str(e))
