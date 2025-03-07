import os
import tempfile
import json
import subprocess
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Insanely Fast Whisper API")

def run_transcription(audio_path: str, transcript_path: str) -> None:
    """
    Calls the insanely-fast-whisper CLI to transcribe the given audio file.
    The transcription output is saved to transcript_path.
    """
    # Adjust additional CLI arguments as needed (e.g., --model-name, --flash, etc.)
    cmd = [
        "insanely-fast-whisper",
        "--file-name", audio_path,
        "--transcript-path", transcript_path,
        # Uncomment or add other options as required:
        # "--model-name", "openai/whisper-large-v3",
        # "--device-id", "0"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"CLI error: {result.stderr}")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Accepts an uploaded audio file, runs transcription via insanely-fast-whisper,
    and returns the JSON transcription.
    """
    # Save the uploaded file to a temporary location
    file_ext = os.path.splitext(file.filename)[1]
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_audio:
            contents = await file.read()
            tmp_audio.write(contents)
            audio_path = tmp_audio.name

        # Create a temporary file for the transcription output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_transcript:
            transcript_path = tmp_transcript.name

        # Run the transcription
        run_transcription(audio_path, transcript_path)

        # Read and parse the transcription output
        with open(transcript_path, "r") as f:
            transcript_data = json.load(f)

        return JSONResponse(content=transcript_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary files if they exist
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if 'transcript_path' in locals() and os.path.exists(transcript_path):
            os.remove(transcript_path)

if __name__ == "__main__":
    import uvicorn 
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
