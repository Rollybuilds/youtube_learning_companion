import streamlit as st
from google import genai

st.title("📚 YouTube Learning Companion")
st.write("Turn any video transcript into a summary and a quiz.")

# Connect to Gemini using the secret key
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

transcript = st.text_area("Paste your video transcript here", height=250)

if st.button("Generate Learning Pack"):
    if not transcript.strip():
        st.warning("Please paste a transcript first.")
    else:
        prompt = f"""
You are a helpful study assistant for college students.
Using ONLY the transcript below, create:

## Summary
A short summary in 4-5 simple sentences.

## Key Points
5 bullet points of the most important ideas.

## Quiz
5 multiple-choice questions (A, B, C, D) based on the transcript.
After the quiz, add an "Answer Key" with the correct options.

Transcript:
{transcript}
"""
        with st.spinner("Creating your learning pack..."):
            models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]
            result = None
            last_error = None

            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    result = response.text
                    break
                except Exception as e:
                    last_error = e

            if result:
                st.markdown(result)
            else:
                st.error("Something went wrong. Please try again in a minute.")
                st.caption(f"Technical detail: {last_error}")