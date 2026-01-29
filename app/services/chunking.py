def chunk_transcript(transcript_json, words_per_chunk=40):
    """
    Build time-aware chunks from AssemblyAI word-level timestamps.
    """

    words = transcript_json.get("words", [])
    if not words:
        return []

    chunks = []

    buffer = []
    start_time = None

    for i, word in enumerate(words):
        if start_time is None:
            start_time = word["start"] / 1000  # ms → seconds

        buffer.append(word["text"])

        # Emit chunk
        if len(buffer) >= words_per_chunk:
            end_time = word["end"] / 1000

            chunks.append({
                "text": " ".join(buffer),
                "start": start_time,
                "end": end_time,
            })

            buffer = []
            start_time = None

    # Remaining words
    if buffer:
        chunks.append({
            "text": " ".join(buffer),
            "start": start_time,
            "end": words[-1]["end"] / 1000,
        })

    return chunks
