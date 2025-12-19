import os
import json
import requests
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from PyPDF2 import PdfReader
from docx import Document


# =====================================================
# CARICAMENTO VARIABILI D'AMBIENTE
# =====================================================

# Carica il file .env (solo lato server)
load_dotenv()


# =====================================================
# INIZIALIZZAZIONE FLASK
# =====================================================

app = Flask(__name__)

# Limite massimo upload file (200 MB)
# Protegge il server da upload eccessivi
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


# =====================================================
# CONFIGURAZIONE PATH E DIRECTORY
# =====================================================

# Directory base del progetto (dove si trova app.py)
BASE_DIR = Path(__file__).resolve().parent

# Directory upload (configurabile da .env)
# Se non esiste viene creata automaticamente
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "upload"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================
# CONFIGURAZIONE CORS
# =====================================================

# URL del frontend autorizzato (Svelte, React, ecc.)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Abilita CORS solo per il frontend specificato
CORS(app, origins=[FRONTEND_URL])


# =====================================================
# CONFIGURAZIONE OLLAMA
# =====================================================

# URL del server Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modello Ollama da usare (deve essere già scaricato)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# Timeout massimo per la chiamata a Ollama (secondi)
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))


# =====================================================
# TIPI DI FILE CONSENTITI
# =====================================================

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


# =====================================================
# FUNZIONI DI SUPPORTO
# =====================================================

def allowed_file(filename: str) -> bool:
    """
    Verifica se l'estensione del file è consentita
    """
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def normalize_text(text: str, max_chars: int = 12000) -> str:
    """
    Pulisce e limita il testo per evitare prompt troppo lunghi
    """
    return text.strip()[:max_chars]


def extract_text_from_txt(path: Path) -> str:
    """
    Estrae testo da file .txt
    """
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_pdf(path: Path) -> str:
    """
    Estrae testo da file PDF
    """
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(path: Path) -> str:
    """
    Estrae testo da file Word (.docx)
    """
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_any(path: Path) -> str:
    """
    Determina il tipo di file e usa l'estrattore corretto
    """
    if not allowed_file(path.name):
        raise ValueError("Tipo file non consentito")

    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path)
    elif path.suffix.lower() == ".docx":
        return extract_text_from_docx(path)
    else:
        return extract_text_from_txt(path)


def call_ollama(text: str) -> dict:
    """
    Invia il testo a Ollama e restituisce un JSON strutturato
    """

    prompt = f"""
Analizza il seguente documento.

Estrai SOLO se presenti le seguenti informazioni:
- tipo_documento (fattura, contratto, lettera, ricevuta, altro)
- data_documento
- data_scadenza
- soggetti_coinvolti (persone o aziende)
- descrizione_breve

IMPORTI:
Se presenti, restituisci il seguente formato JSON:

"importi": {{
  "totale": numero o null,
  "imponibile": numero o null,
  "iva": numero o null,
  "altri": [
    {{
      "descrizione": stringa,
      "valore": numero,
      "valuta": stringa
    }}
  ]
}}

Regole:
- Usa SOLO numeri
- Se un campo non esiste usa null
- NON inventare valori

Rispondi ESCLUSIVAMENTE con JSON valido.

Documento:

```
{text}
```
"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=OLLAMA_TIMEOUT
    )

    # Lancia eccezione se Ollama risponde con errore HTTP
    response.raise_for_status()

    data = response.json()

    # Ollama restituisce il JSON come stringa
    return json.loads(data.get("response", "{}"))


# =====================================================
# ENDPOINT API
# =====================================================

@app.route("/api/analyze", methods=["POST"])
def analyze_file():
    """
    Endpoint:
    POST /api/analyze
    Content-Type: multipart/form-data
    Campo richiesto: file
    """

    # Verifica presenza file
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return jsonify({"error": "File mancante"}), 400

    # Percorso temporaneo del file
    tmp_path = UPLOAD_DIR / uploaded_file.filename

    try:
        # Salva file su disco
        uploaded_file.save(tmp_path)

        # Estrae il testo
        raw_text = extract_text_from_any(tmp_path)
        text = normalize_text(raw_text)

        if not text:
            return jsonify({"error": "Testo vuoto o non leggibile"}), 400

        # Analizza con Ollama
        result = call_ollama(text)

        return jsonify({
            "filename": uploaded_file.filename,
            "extracted_data": result
        })

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except requests.RequestException as re:
        return jsonify({"error": f"Errore Ollama: {str(re)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Errore interno: {str(e)}"}), 500

    finally:
        # Cancella SEMPRE il file temporaneo
        if tmp_path.exists():
            tmp_path.unlink()


# =====================================================
# AVVIO SERVER
# =====================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5001")),
        debug=False
    )
