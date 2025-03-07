from flask import Flask, request, jsonify
from wasmer import engine, Store, Module, Instance, ImportObject
import os
import fs, pathlib
import time

app = Flask(__name__)

# Load the WASM module.
wasm_file_path = "whisper.wasm"  # Adjust if necessary.
store = Store(engine.JIT(compiler="cranelift"))
with open(wasm_file_path, "rb") as wasm_file:
    wasm_bytes = wasm_file.read()
module = Module(store, wasm_bytes)
# Create an empty ImportObject unless your module requires imports.
import_object = ImportObject()
instance = Instance(module, import_object)

# Map exported functions from the WASM module.
allocate = instance.exports.allocate     # Should allocate memory; returns pointer.
free = instance.exports.free             # Frees memory.
load_audio = instance.exports.load_audio # Loads audio data into the module.
run_whisper = instance.exports.run_whisper  # Runs the transcription.
get_transcript = instance.exports.get_transcript  # Returns a pointer to a null-terminated transcript.

def read_null_terminated_string(ptr):
    mem_view = instance.exports.memory.uint8_view()
    chars = []
    i = ptr
    while mem_view[i] != 0:
        chars.append(chr(mem_view[i]))
        i += 1
    return "".join(chars)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    # Check if an audio file was uploaded.
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    audio_file = request.files["file"]
    audio_bytes = audio_file.read()
    
    # Allocate memory in WASM and copy audio bytes.
    audio_length = len(audio_bytes)
    ptr = allocate(audio_length)
    memory = instance.exports.memory.uint8_view(ptr)
    for i, b in enumerate(audio_bytes):
        memory[i] = b
    
    # Call the WASM function to load the audio.
    load_audio(ptr, audio_length)
    
    # Free the allocated memory for audio input.
    free(ptr)
    
    # Run the Whisper transcription.
    run_whisper()
    
    # Retrieve the transcript from WASM memory.
    transcript_ptr = get_transcript()
    transcript = read_null_terminated_string(transcript_ptr)
    
    # Optionally, save the audio file in /public/recordings (for inspection).
    recordings_dir = os.path.join(os.getcwd(), "public", "recordings")
    pathlib.Path(recordings_dir).mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    file_name = f"recording-{timestamp}.wav"
    file_path = os.path.join(recordings_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(audio_bytes)
    
    # Return the transcript and a URL (relative) to the saved file.
    # Adjust file URL according to your deployment.
    file_url = f"/recordings/{file_name}"
    
    if transcript.strip() == "":
        return jsonify({
            "error": "Empty transcription",
            "details": "Transcript is empty or undefined",
            "fileUrl": file_url
        }), 500

    return jsonify({"transcript": transcript, "fileUrl": file_url}), 200

if __name__ == "__main__":
    # Use PORT environment variable for Render or default to 5000.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
