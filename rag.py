from langchain_groq import ChatGroq
from config import GROQ_API_KEY
from vectorstore import vectorstore
from utils import is_date_question  # or paste function here

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.1-8b-instant",
    temperature=0.2
)

def ask(query: str, k=5):
    date_aware = is_date_question(query)

    docs = vectorstore.similarity_search(query, k=k)

    context_blocks = []

    for d in docs:
        meta = d.metadata

        if date_aware:
            block = f"""
Date: {meta.get("date")}
File: {meta.get("filename")}
Content:
{d.page_content}
""".strip()
        else:
            # 🧠 Clean, human context — no dates, no timestamps
            block = d.page_content.strip()

        context_blocks.append(block)

    context = "\n\n".join(context_blocks)

    # 🧠 Adaptive prompt
    if date_aware:
        prompt = f"""
You are answering questions using transcript content and metadata.

RULES:
- Mention dates only if relevant to the question.
- Summarize naturally; do not list chunks.
- Do not overwhelm the user with metadata.
- Use dates to anchor events, not to narrate logs.

Context:
{context}

Question:
{query}

Answer (clear, human summary):
""".strip()
    else:
        prompt = f"""
You are answering questions using retrieved transcript content.

RULES:
- Do NOT invent facts or motivations.
- Do NOT assume unstated causes.
- Use ONLY the provided context.
- Do NOT mention timestamps or metadata unless explicitly asked.
- Explain events clearly, including what happened and why it mattered,
  but ONLY if that information is present in the context.

Context:
{context}

Question:
{query}

Answer guidelines:
- Write a clear, complete explanation in 2–4 sentences.
- Include cause, event, and outcome if they are supported by the text.
- If details are missing, say so briefly.

Answer:
""".strip()


    response = llm.invoke(prompt)

    return {
        "answer": response.content.strip()
    }
    