from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from google.cloud import speech
from google.cloud import texttospeech
from google.cloud import language_v1
import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('tts', exist_ok=True)  # Ensure tts folder exists as well

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(folder):
    files = []
    for filename in os.listdir(folder):
        if allowed_file(filename):
            files.append(filename)
    files.sort(reverse=True)
    return files

def analyze_sentiment(text):
    """Analyze sentiment using Google Natural Language API."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    
    response = client.analyze_sentiment(request={"document": document})
    sentiment_score = response.document_sentiment.score
    sentiment_magnitude = response.document_sentiment.magnitude

    # Classify sentiment
    if sentiment_score <= -0.25:
        sentiment_label = "Negative"
    elif sentiment_score >= 0.25:
        sentiment_label = "Positive"
    else:
        sentiment_label = "Neutral"
    
    return sentiment_score, sentiment_magnitude, sentiment_label

@app.route('/')
def index():
    files = get_files(UPLOAD_FOLDER)  # Files from the 'uploads' folder
    tts_files = get_files('tts')  # Files from the 'tts' folder
    return render_template('index.html', files=files, tts_files=tts_files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file:
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Google Speech-to-Text API integration
        client = speech.SpeechClient()
        with open(file_path, 'rb') as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            language_code="en-US",
            audio_channel_count=1,
        )

        response = client.recognize(config=config, audio=audio)

        # Save transcript to a .txt file
        transcript = "\n".join([result.alternatives[0].transcript for result in response.results])
        transcript_path = file_path + '.txt'
        

        with open(transcript_path, 'w') as f:
            f.write(transcript)

        sentiment_score, sentiment_magnitude, sentiment_label = analyze_sentiment(transcript)
    # Save the transcript and sentiment analysis in a new file in uploads folder
        sentiment_filepath = file_path+'_sentiment'+'.txt'
        
        with open(sentiment_filepath, 'w') as f:
            f.write(f"Original Text:\n{transcript}\n\n")
            f.write(f"Sentiment Score: {sentiment_score}\n")
            f.write(f"Sentiment Magnitude: {sentiment_magnitude}\n")
            f.write(f"Sentiment Label: {sentiment_label}\n")
     
    return redirect('/')  # success

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    
    if not text.strip():
        flash("Text input is empty")
        return redirect(request.url)
    
    timestamp = datetime.now().strftime("%Y%m%d-%I%M%S%p")
    text_filename = f"{timestamp}.txt"
    audio_filename = f"{timestamp}.wav"
    sentiment_filename=f"{timestamp}_sentiment.txt"

    text_file_path = os.path.join('tts', text_filename)
    audio_file_path = os.path.join('tts', audio_filename)
    sentiment_file_path=os.path.join('tts', sentiment_filename)

    # Save the input text to a .txt file in the 'tts' folder
    with open(text_file_path, 'w') as out:
        out.write(text)

    
    # Perform Sentiment Analysis
    sentiment_score, sentiment_magnitude, sentiment_label = analyze_sentiment(text)

    # Save the input text and sentiment to a file
    with open(sentiment_file_path, 'w') as out:
        out.write(f"Original Text:\n{text}\n\n")
        out.write(f"Sentiment Score: {sentiment_score}\n")
        out.write(f"Sentiment Magnitude: {sentiment_magnitude}\n")
        out.write(f"Sentiment Label:\n{sentiment_label}\n")
    # Google Text-to-Speech API integration
    client = texttospeech.TextToSpeechClient()

    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

    # Save the generated speech as a .wav file in the 'tts' folder
    with open(audio_file_path, 'wb') as out:
        out.write(response.audio_content)

    return redirect('/')  # success

# Route to serve files from either uploads or tts folder
@app.route('/<folder>/<filename>')
def uploaded_file(folder, filename):
    if folder not in ['uploads', 'tts']:
        return "Invalid folder", 404

    folder_path = os.path.join(folder, filename)
    if os.path.exists(folder_path):
        return send_from_directory(folder, filename)
    else:
        return "File not found", 404

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_from_directory('', 'script.js')

if __name__ == '__main__':
    app.run(debug=True)

