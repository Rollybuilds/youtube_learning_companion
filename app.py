import streamlit as st
from google import genai

st.set_page_config(page_title="YouTube Learning Companion", page_icon="📚", layout="wide")

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


def ask_gemini(prompt):
    """Try each model in order and return the first answer that works."""
    last_error = None
    for name in MODELS:
        try:
            response = client.models.generate_content(model=name, contents=prompt)
            return response.text
        except Exception as e:
            last_error = e
    raise last_error


st.title("📚 YouTube Learning Companion")
st.caption("Paste a lecture transcript. Get notes, a quiz, and flashcards.")

left, right = st.columns([1, 1.4], gap="large")

with left:
    transcript = st.text_area(
        "Lecture transcript",
        height=350,
        placeholder="Paste your transcript here...",
    )
    st.caption(f"{len(transcript):,} characters")
    generate = st.button("Generate study pack", type="primary", use_container_width=True)

    if generate:
        if not transcript.strip():
            st.warning("Please paste a transcript first.")
        else:
            notes_prompt = f"""
You are a study assistant for exam-preparing students.
Using ONLY the transcript below, write clear notes in simple language
with exactly these sections:

## Main Topics
3-6 bullet points.

## Key Concepts
The most important ideas, each explained in 1-2 sentences.

## Definitions
Important terms with short definitions.

## Examples
Examples from the transcript, explained simply.

## Important Takeaway
One short paragraph on what the student must remember.

Transcript:
{transcript}
"""
            with st.spinner("Creating your notes..."):
                try:
                    st.session_state["notes"] = ask_gemini(notes_prompt)
                    st.session_state["transcript"] = transcript
                except Exception as e:
                    st.error("Something went wrong. Please try again in a minute.")
                    st.caption(f"Technical detail: {e}")

with right:
    tab_notes, tab_quiz, tab_cards = st.tabs(["📝 Notes", "❓ Quiz", "🗂️ Flashcards"])

    with tab_notes:
        if "notes" in st.session_state:
            st.markdown(st.session_state["notes"])
        else:
            st.info("Your notes will appear here.")

    with tab_quiz:
        st.info("Quiz is coming in the next step.")

    with tab_cards:
        st.info("Flashcards are coming in the next step.")