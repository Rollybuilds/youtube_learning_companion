import time
from html import escape
import re 
import json
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="YouTube Learning Companion", page_icon="📚", layout="wide")

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=45000),
)
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


def ask_gemini(prompt, as_json=False):
    """Try each model in order, and record how long each attempt took."""
    config = None
    if as_json:
        config = types.GenerateContentConfig(response_mime_type="application/json")
    log = []
    for name in MODELS:
        start = time.time()
        try:
            response = client.models.generate_content(
                model=name, contents=prompt, config=config
            )
            log.append(f"{name}: OK in {time.time() - start:.1f}s")
            st.session_state["timing_log"] = log
            return response.text
        except Exception as e:
            log.append(f"{name}: failed after {time.time() - start:.1f}s ({str(e)[:80]})")
    st.session_state["timing_log"] = log
    raise RuntimeError("All models failed. " + " | ".join(log))

def make_quiz(transcript, difficulty):
    """Ask Gemini for 5 questions and return them as a clean Python list."""
    prompt = f"""
You are an exam coach. Using ONLY the transcript below, write 5 multiple-choice
questions at {difficulty} difficulty.
- Easy: simple recall of facts.
- Medium: understanding of ideas.
- Hard: applying or comparing ideas.

Return ONLY a JSON list of 5 items. Each item must have these keys:
"question": the question text,
"options": a list of exactly 4 answer strings (no A/B/C/D labels),
"answer_index": the position of the correct option (0 to 3),
"explanation": 2 sentences on why it is correct and the concept behind it,
"topic": a 2 to 4 word topic name.

Transcript:
{transcript}
"""
    quiz = json.loads(ask_gemini(prompt, as_json=True))
    if isinstance(quiz, dict):
        quiz = next(iter(quiz.values()))
    clean = [
        q for q in quiz
        if len(q.get("options", [])) == 4 and q.get("answer_index") in (0, 1, 2, 3)
    ]
    if not clean:
        raise ValueError("The AI returned an unusable quiz. Please try again.")
    return clean
def clean_transcript(text):
    """Remove YouTube timestamps like '38:4138 minutes, 41 seconds'."""
    pattern = r"\d{1,2}:\d{2}(?::\d{2})?(?:\d+\s*hours?,?\s*)?(?:\d+\s*minutes?,?\s*)?(?:\d+\s*seconds?)?"
    text = re.sub(pattern, " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()

def make_flashcards(transcript):
    """Ask Gemini for question-and-answer flashcards."""
    prompt = f"""
You are a study coach. Using ONLY the transcript below, create 8 flashcards
that help a student revise the most important ideas.

Return ONLY a JSON list of 8 items. Each item must have these keys:
"front": a short question or term,
"back": a clear answer in 1-2 simple sentences.

Transcript:
{transcript}
"""
    cards = json.loads(ask_gemini(prompt, as_json=True))
    if isinstance(cards, dict):
        cards = next(iter(cards.values()))
    clean = [c for c in cards if c.get("front") and c.get("back")]
    if not clean:
        raise ValueError("The AI returned unusable flashcards. Please try again.")
    return clean
def answer_question(transcript, question):
    """Answer a question using only the transcript."""
    prompt = f"""
You are a patient tutor. Answer the student's question using ONLY the
transcript below. Use simple words and keep it under 150 words.
If the transcript does not cover it, say "This isn't covered in the lecture."

Question: {question}

Transcript:
{transcript}
"""
    return ask_gemini(prompt)

st.title("📚 YouTube Learning Companion")
st.caption("Paste a lecture transcript. Get notes, a quiz, and flashcards.")

left, right = st.columns([1, 1.4], gap="large")

with left:
    transcript = st.text_area(
        "Lecture transcript",
        height=350,
        placeholder="Paste your transcript here...",
    )
    transcript = clean_transcript(transcript)
    st.caption(f"{len(transcript):,} characters")

    MAX_CHARS = 30000
    if len(transcript) > MAX_CHARS:
       st.warning("Long transcript: using the first 30,000 characters to keep things fast.")
       transcript = transcript[:MAX_CHARS]

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
                    # New transcript means the old quiz no longer applies
                    st.session_state.pop("quiz", None)
                    st.session_state.pop("quiz_result", None)
                    st.session_state.pop("cards", None)
                    st.session_state.pop("chat", None)
                except Exception as e:
                    st.error("Something went wrong. Please try again in a minute.")
                    st.caption(f"Technical detail: {e}")

with right:
    tab_notes, tab_quiz, tab_cards, tab_ask = st.tabs(["📝 Notes", "❓ Quiz", "🗂️ Flashcards", "💬 Ask"])

    with tab_notes:
        if "notes" in st.session_state:
            st.markdown(st.session_state["notes"])
        else:
            st.info("Your notes will appear here.")

    with tab_quiz:
        if "transcript" not in st.session_state:
            st.info("Generate your notes first, then come back here for a quiz.")
        else:
            difficulty = st.radio(
                "Difficulty", ["Easy", "Medium", "Hard"], index=1, horizontal=True
            )
            if st.button("Generate quiz"):
                with st.spinner("Writing your quiz..."):
                    try:
                        st.session_state["quiz"] = make_quiz(
                            st.session_state["transcript"], difficulty
                        )
                        st.session_state["quiz_id"] = st.session_state.get("quiz_id", 0) + 1
                        st.session_state.pop("quiz_result", None)
                    except Exception as e:
                        st.error("Could not create the quiz. Please try again.")
                        st.caption(f"Technical detail: {e}")

            quiz = st.session_state.get("quiz")
            if quiz:
                quiz_id = st.session_state["quiz_id"]
                with st.form(f"quiz_form_{quiz_id}"):
                    for i, q in enumerate(quiz):
                        st.radio(
                            f"**{i + 1}. {q['question']}**",
                            q["options"],
                            index=None,
                            key=f"q_{quiz_id}_{i}",
                        )
                    submitted = st.form_submit_button("Submit answers")

                if submitted:
                    results = []
                    for i, q in enumerate(quiz):
                        picked = st.session_state.get(f"q_{quiz_id}_{i}")
                        correct = q["options"][q["answer_index"]]
                        results.append({
                            "picked": picked,
                            "correct": correct,
                            "is_correct": picked == correct,
                            "explanation": q.get("explanation", ""),
                            "topic": q.get("topic", "General"),
                        })
                    st.session_state["quiz_result"] = results

                results = st.session_state.get("quiz_result")
                if results:
                    score = sum(r["is_correct"] for r in results)
                    st.subheader(f"Score: {score}/{len(results)}")
                    for i, r in enumerate(results):
                        if r["is_correct"]:
                            st.success(f"Question {i + 1}: Correct")
                        else:
                            st.error(
                                f"Question {i + 1}: Incorrect. "
                                f"You chose: {r['picked'] or 'no answer'}. "
                                f"Correct answer: {r['correct']}"
                            )
                        st.caption(r["explanation"])
                    weak = sorted({r["topic"] for r in results if not r["is_correct"]})
                    if weak:
                        st.warning("Topics to revise: " + ", ".join(weak))
                    else:
                        st.success("No weak topics. Nice work!")

    with tab_cards:
        if "transcript" not in st.session_state:
            st.info("Generate your notes first, then come back here for flashcards.")
        else:
            if st.button("Generate flashcards"):
                with st.spinner("Making your flashcards..."):
                    try:
                        st.session_state["cards"] = make_flashcards(
                            st.session_state["transcript"]
                        )
                        st.session_state["card_i"] = 0
                        st.session_state["show_back"] = False
                    except Exception as e:
                        st.error("Could not create flashcards. Please try again.")
                        st.caption(f"Technical detail: {e}")

            cards = st.session_state.get("cards")
            if cards:
                i = st.session_state.get("card_i", 0)
                card = cards[i]
                st.caption(f"Card {i + 1} of {len(cards)}")
                showing_back = st.session_state.get("show_back", False)
                text = escape(card["back"] if showing_back else card["front"])
                tag = "ANSWER" if showing_back else "QUESTION"
                bg = "#EEF2FF" if showing_back else "#4F46E5"
                fg = "#1F2937" if showing_back else "#FFFFFF"
                st.markdown(
                    f"""
<div style="background:{bg};color:{fg};border-radius:20px;padding:48px 28px;min-height:220px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;box-shadow:0 6px 18px rgba(79,70,229,0.18);">
<div style="font-size:12px;letter-spacing:2px;opacity:0.7;margin-bottom:14px;">{tag}</div>
<div style="font-size:22px;font-weight:600;line-height:1.4;">{text}</div>
</div>
""",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                if c1.button("⬅️ Previous", disabled=(i == 0), use_container_width=True):
                    st.session_state["card_i"] = i - 1
                    st.session_state["show_back"] = False
                    st.rerun()
                label = "🔄 Flip card"
                if c2.button(label, use_container_width=True):
                    st.session_state["show_back"] = not st.session_state.get("show_back", False)
                    st.rerun()
                if c3.button("Next ➡️", disabled=(i == len(cards) - 1), use_container_width=True):
                    st.session_state["card_i"] = i + 1
                    st.session_state["show_back"] = False
                    st.rerun()
    with tab_ask:
        if "transcript" not in st.session_state:
            st.info("Generate your notes first, then ask questions about the lecture.")
        else:
            st.caption("Ask anything about the lecture. Answers come only from your transcript.")
            with st.form("ask_form", clear_on_submit=True):
                question = st.text_input(
                    "Your question", placeholder="Explain this part in simple words..."
                )
                asked = st.form_submit_button("Ask")

            if asked and question.strip():
                with st.spinner("Thinking..."):
                    try:
                        answer = answer_question(st.session_state["transcript"], question)
                        st.session_state.setdefault("chat", []).append((question, answer))
                    except Exception as e:
                        st.error("Could not get an answer. Please try again.")
                        st.caption(f"Technical detail: {e}")

            for q, a in reversed(st.session_state.get("chat", [])):
                with st.container(border=True):
                    st.markdown(f"**You:** {q}")
                    st.markdown(a)
    if "timing_log" in st.session_state:
        with st.expander("⏱️ Speed details"):
            for line in st.session_state["timing_log"]:
                st.write(line)