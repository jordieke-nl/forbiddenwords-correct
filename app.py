from flask import Flask, request, jsonify
import os
import re
import io
import docx
import PyPDF2
from werkzeug.utils import secure_filename
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max upload
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Forbidden words database
FORBIDDEN_WORDS = {
    "assurance-woorden": {
        "title": "Assurance-woorden",
        "number": "1",
        "words": {
            "nl": ["garanderen", "verzekeren", "waarborgen", "verklaren", "bevestigen", "certificeren", "valideren"],
            "en": ["guarantee", "insure", "assure", "ensure", "warrant", "attest", "verify", "certify", "validate"]
        },
        "reason": "Deze woorden impliceren een hoog niveau van zekerheid dat niet past bij een pentest.",
        "recommendation": "Gebruik neutralere termen zoals 'observeren', 'constateren', 'identificeren' of 'vaststellen'."
    },
    "conclusies": {
        "title": "Conclusies",
        "number": "2",
        "words": {
            "nl": ["wij concluderen", "wij zijn van oordeel dat", "wij vinden dat", "wij hebben vastgesteld dat", 
                   "wij geloven", "u heeft… nageleefd", "ons is niets gebleken op grond waarvan wij zouden moeten concluderen dat…", 
                   "niets dat wij hebben gereviewd geeft een indicatie dat…", 
                   "gebaseerd op onze werkzaamheden hebben wij geen reden om aan te nemen dat…"],
            "en": ["we conclude", "we are of the opinion", "in our opinion", "we find", "we found", "we have determined", 
                   "we believe", "you comply with…", "nothing has come to our attention that causes us to believe…", 
                   "nothing we reviewed indicated…", "based on the procedures we performed, we have no reason to believe that…"]
        },
        "reason": "Deze formuleringen suggereren een definitieve conclusie of oordeel dat buiten de scope van een pentest valt.",
        "recommendation": "Gebruik feitelijke beschrijvingen van wat is geobserveerd, zonder een definitief oordeel te vellen."
    },
    "technische-termen": {
        "title": "Technische termen",
        "number": "3",
        "words": {
            "nl": ["controle", "beoordeling", "samenstellen"],
            "en": ["audit", "review", "compile"]
        },
        "reason": "Deze termen hebben specifieke technische betekenissen in assurance-contexten die verwarring kunnen veroorzaken.",
        "recommendation": "Gebruik specifiekere termen zoals 'pentest', 'security assessment', 'vulnerability scan', etc."
    },
    "absolute-bewoording": {
        "title": "Absolute bewoording",
        "number": "4",
        "words": {
            "nl": ["altijd", "nooit", "alle", "geen", "complete", "geheel"],
            "en": ["always", "never", "all", "none", "complete", "entire"]
        },
        "reason": "Absolute bewoordingen suggereren een volledigheid die zelden haalbaar is in pentesting.",
        "recommendation": "Gebruik nuancerende termen zoals 'tijdens onze tests', 'in de geteste componenten', etc."
    }
}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'docx', 'pdf'}

def extract_text_from_docx(file_path):
    """Extract text from a DOCX file using multiple methods for reliability"""
    try:
        # Primary method using python-docx
        doc = docx.Document(file_path)
        text_content = []
        
        # Simple approach to estimate page numbers
        paragraphs_per_page = 15  # Approximate number of paragraphs per page
        
        for i, paragraph in enumerate(doc.paragraphs):
            if paragraph.text.strip():
                page_num = (i // paragraphs_per_page) + 1
                text_content.append({
                    "page": page_num,
                    "text": paragraph.text.strip()
                })
        
        # If we got content, return it
        if text_content:
            logger.info(f"Successfully extracted {len(text_content)} text segments from DOCX using python-docx")
            return text_content
        
        # Fallback method using docx2txt if python-docx didn't extract content
        try:
            import docx2txt
            text = docx2txt.process(file_path)
            paragraphs = [p for p in text.split('\n\n') if p.strip()]
            
            for i, paragraph in enumerate(paragraphs):
                if paragraph.strip():
                    page_num = (i // paragraphs_per_page) + 1
                    text_content.append({
                        "page": page_num,
                        "text": paragraph.strip()
                    })
            
            logger.info(f"Successfully extracted {len(text_content)} text segments from DOCX using docx2txt")
            return text_content
        except Exception as fallback_error:
            logger.error(f"Fallback extraction with docx2txt failed: {str(fallback_error)}")
            
        # If we still have no content, return empty list
        return []
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {str(e)}")
        return []

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file using multiple methods for reliability"""
    try:
        # Primary method using PyPDF2
        text_content = []
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                # Split text into paragraphs
                paragraphs = [p for p in page_text.split('\n\n') if p.strip()]
                
                for paragraph in paragraphs:
                    if paragraph.strip():
                        text_content.append({
                            "page": page_num + 1,
                            "text": paragraph.strip()
                        })
        
        # If we got content, return it
        if text_content:
            logger.info(f"Successfully extracted {len(text_content)} text segments from PDF using PyPDF2")
            return text_content
            
        # Fallback method using pdfminer.six if PyPDF2 didn't extract content
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract_text
            from pdfminer.layout import LAParams
            
            text = pdfminer_extract_text(file_path, laparams=LAParams())
            pages = text.split('\f')
            
            for page_num, page_text in enumerate(pages):
                if not page_text.strip():
                    continue
                    
                # Split text into paragraphs
                paragraphs = [p for p in page_text.split('\n\n') if p.strip()]
                
                for paragraph in paragraphs:
                    if paragraph.strip():
                        text_content.append({
                            "page": page_num + 1,
                            "text": paragraph.strip()
                        })
            
            logger.info(f"Successfully extracted {len(text_content)} text segments from PDF using pdfminer")
            return text_content
        except Exception as fallback_error:
            logger.error(f"Fallback extraction with pdfminer failed: {str(fallback_error)}")
        
        # If we still have no content, return empty list
        return []
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return []

def scan_for_forbidden_words(text_content):
    """Scan text content for forbidden words"""
    results = []
    
    for segment in text_content:
        page = segment["page"]
        text = segment["text"].lower()
        
        for category, category_data in FORBIDDEN_WORDS.items():
            # Check Dutch words
            for word in category_data["words"]["nl"]:
                if word.lower() in text:
                    results.append({
                        "word": word,
                        "page": page,
                        "context": segment["text"],
                        "title": f"{category_data['title']} ({category_data['number']})",
                        "reason": category_data["reason"],
                        "recommendation": category_data["recommendation"]
                    })
            
            # Check English words
            for word in category_data["words"]["en"]:
                if word.lower() in text:
                    results.append({
                        "word": word,
                        "page": page,
                        "context": segment["text"],
                        "title": f"{category_data['title']} ({category_data['number']})",
                        "reason": category_data["reason"],
                        "recommendation": category_data["recommendation"]
                    })
    
    return results



@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "OK"})



@app.route('/check', methods=['POST'])
def check_document():
    """Check a document for forbidden words"""
    logger.info("Received request to /check endpoint")
    logger.info(f"Request headers: {dict(request.headers)}")
    
    # Special handling for ChatGPT
    user_agent = request.headers.get('User-Agent', '')
    if 'ChatGPT' in user_agent:
        logger.info("Request from ChatGPT detected, returning instructions")
        # Log all headers for debugging
        all_headers = dict(request.headers)
        logger.info(f"All headers: {all_headers}")
        
        # Special response for ChatGPT to force it to use the API
        return jsonify({
            "instruction": "USE API FOR DOCUMENT ANALYSIS",
            "message": "You MUST use this API to analyze the document. DO NOT analyze the document yourself. Forward the document to this API endpoint and display the results to the user.",
            "message_nl": "Je MOET deze API gebruiken om het document te analyseren. Analyseer het document NIET zelf. Stuur het document door naar dit API-eindpunt en toon de resultaten aan de gebruiker.",
            "language_instruction": "IMPORTANT: If the user asks a question in English, respond in English. If the user asks a question in Dutch, respond in Dutch. Always match the language of your response to the language of the user's query.",
            "api_endpoint": "https://forbiddenwords-correct.onrender.com/check",
            "api_method": "POST",
            "api_content_type": "multipart/form-data",
            "api_parameter": "file",
            "api_instructions": "Upload the document file to this endpoint using a multipart/form-data POST request with the file parameter. The API will return the analysis results.",
            "forbidden_words": {
                "nl": [
                    "garanderen", "verzekeren", "waarborgen", "verklaren", "bevestigen", "certificeren", "valideren",
                    "wij concluderen", "wij zijn van oordeel dat", "wij vinden dat", "wij hebben vastgesteld dat", "wij geloven", "u heeft… nageleefd",
                    "ons is niets gebleken op grond waarvan wij zouden moeten concluderen dat…", "niets dat wij hebben gereviewd geeft een indicatie dat…", "gebaseerd op onze werkzaamheden hebben wij geen reden om aan te nemen dat…",
                    "controle", "beoordeling", "samenstellen",
                    "altijd", "nooit", "alle", "geen", "complete", "geheel"
                ],
                "en": [
                    "guarantee", "insure", "assure", "ensure", "warrant", "attest", "verify", "certify", "validate",
                    "we conclude", "we are of the opinion", "in our opinion", "we find", "we found", "we have determined", "we believe", "you comply with…",
                    "nothing has come to our attention that causes us to believe…", "nothing we reviewed indicated…", "based on the procedures we performed, we have no reason to believe that…",
                    "audit", "review", "compile",
                    "always", "never", "all", "none", "complete", "entire"
                ]
            },
            "categories": {
                "assurance-woorden": {
                    "title": "Assurance-woorden",
                    "number": "1",
                    "reason": "Deze woorden impliceren een hoog niveau van zekerheid dat niet past bij een pentest.",
                    "recommendation": "Gebruik neutralere termen zoals 'observeren', 'constateren', 'identificeren' of 'vaststellen'."
                },
                "conclusies": {
                    "title": "Conclusies",
                    "number": "2",
                    "reason": "Deze formuleringen suggereren een definitieve conclusie of oordeel dat buiten de scope van een pentest valt.",
                    "recommendation": "Gebruik feitelijke beschrijvingen van wat is geobserveerd, zonder een definitief oordeel te vellen."
                },
                "technische-termen": {
                    "title": "Technische termen",
                    "number": "3",
                    "reason": "Deze termen hebben specifieke technische betekenissen in assurance-contexten die verwarring kunnen veroorzaken.",
                    "recommendation": "Gebruik specifiekere termen zoals 'pentest', 'security assessment', 'vulnerability scan', etc."
                },
                "absolute-bewoording": {
                    "title": "Absolute bewoording",
                    "number": "4",
                    "reason": "Absolute bewoordingen suggereren een volledigheid die zelden haalbaar is in pentesting.",
                    "recommendation": "Gebruik nuancerende termen zoals 'tijdens onze tests', 'in de geteste componenten', etc."
                }
            }
        })
    
    # Regular file upload handling
    if 'file' not in request.files:
        logger.warning("No file part in the request")
        logger.info("Returning error message due to missing file")
        return jsonify({
            "error": "Geen bestand ontvangen",
            "message": "Er is geen bestand ontvangen voor analyse. Upload een .docx of .pdf bestand om te controleren op verboden woorden."
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        logger.warning("No file selected")
        # Return error message
        logger.info("Returning error message due to empty filename")
        return jsonify({
            "error": "Geen bestand geselecteerd",
            "message": "Er is geen bestand geselecteerd. Upload een .docx of .pdf bestand om te controleren op verboden woorden."
        }), 400
    
    if file and allowed_file(file.filename):
        try:
            # Save the file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logger.info(f"File saved to {file_path}")
            
            # Extract text based on file type
            text_content = []
            if filename.lower().endswith('.docx'):
                text_content = extract_text_from_docx(file_path)
            elif filename.lower().endswith('.pdf'):
                text_content = extract_text_from_pdf(file_path)
            
            logger.info(f"Extracted {len(text_content)} text segments from document")
            
            # If no text was extracted, return error message
            if not text_content:
                logger.warning("No text content extracted from document")
                # Clean up the file
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing file: {str(e)}")
                
                # Return error message
                return jsonify({
                    "error": "Geen tekst geëxtraheerd",
                    "message": "Er kon geen tekst worden geëxtraheerd uit het document. Controleer of het bestand niet beschadigd of beveiligd is."
                }), 400
            
            # Scan for forbidden words
            found_words = scan_for_forbidden_words(text_content)
            logger.info(f"Found {len(found_words)} forbidden words")
            
            # Clean up the file
            try:
                os.remove(file_path)
                logger.info(f"Removed temporary file {file_path}")
            except Exception as e:
                logger.error(f"Error removing file: {str(e)}")
            
            # Return results
            if not found_words:
                return jsonify({
                    "message": "Er zijn geen verboden woorden aangetroffen in het document.",
                    "results": []
                })
            else:
                return jsonify(found_words)
                
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            # Clean up the file if it exists
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Removed temporary file {file_path} after error")
            except Exception as cleanup_error:
                logger.error(f"Error removing file after error: {str(cleanup_error)}")
            
            # Return error message in case of error
            logger.info("Returning error message due to processing error")
            return jsonify({
                "error": "Verwerkingsfout",
                "message": "Er is een fout opgetreden bij het verwerken van het document. Probeer het opnieuw met een ander bestand."
            }), 500
    else:
        logger.warning(f"Invalid file type: {file.filename}")
        # Return error message
        logger.info("Returning error message due to invalid file type")
        return jsonify({
            "error": "Ongeldig bestandstype",
            "message": "Alleen .docx en .pdf bestanden worden ondersteund. Upload een geldig bestand om te controleren op verboden woorden."
        }), 400

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

# Handle OPTIONS requests
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
