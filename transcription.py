import assemblyai as aai
from config import ASSEMBLYAI_API_KEY

aai.settings.api_key = ASSEMBLYAI_API_KEY

def transcribe_from_url(audio_url: str):
    config = aai.TranscriptionConfig(
        speech_models=["universal"]
    )

    transcript = aai.Transcriber(config=config).transcribe(audio_url)

    if transcript.status == "error":
        raise RuntimeError(transcript.error)

    return transcript.json_response