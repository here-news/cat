from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json
import time
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Mock database of trusted issuers (public keys)
TRUSTED_ISSUERS = {
    "npub1test": "710e354519c02461ceaf78e4febe6a0f01c422ca07d42a1be063ce13abdf9739",
    "npub1abc123": "710e354519c02461ceaf78e4febe6a0f01c422ca07d42a1be063ce13abdf9739",
    "npub1xyz789": "45af934456456456456456456456456456456456456456456456456456456456",
    # Add more trusted issuers as needed
}

# Mock content database
CONTENT_DB = {
    "https://example.com/article/abc123": {
        "1": {
            "en": "This is the first chunk of premium content from article abc123 (English).",
            "fr": "Ceci est le premier morceau de contenu premium de l'article abc123 (French).",
            "de": "Dies ist der erste Teil des Premium-Inhalts aus Artikel abc123 (German)."
        },
        "2": {
            "en": "This is the second chunk of premium content from article abc123 (English).",
            "fr": "Ceci est le deuxième morceau de contenu premium de l'article abc123 (French).",
            "de": "Dies ist der zweite Teil des Premium-Inhalts aus Artikel abc123 (German)."
        },
        "full": {
            "en": "This is the complete premium content from article abc123 (English).",
            "fr": "Ceci est le contenu premium complet de l'article abc123 (French).",
            "de": "Dies ist der vollständige Premium-Inhalt aus Artikel abc123 (German)."
        }
    },
    "https://example.com/book/xyz789": {
        "1": {
            "en": "Chapter 1: Introduction to CAT Protocol (English)",
            "fr": "Chapitre 1 : Introduction au protocole CAT (French)",
            "de": "Kapitel 1: Einführung in das CAT-Protokoll (German)"
        },
        "2": {
            "en": "Chapter 2: Technical Implementation (English)",
            "fr": "Chapitre 2 : Mise en œuvre technique (French)",
            "de": "Kapitel 2: Technische Implementierung (German)"
        },
        "3": {
            "en": "Chapter 3: Future Directions (English)",
            "fr": "Chapitre 3 : Orientations futures (French)",
            "de": "Kapitel 3: Zukünftige Richtungen (German)"
        },
        "full": {
            "en": "Complete book content about CAT Protocol (English)",
            "fr": "Contenu complet du livre sur le protocole CAT (French)",
            "de": "Vollständiger Buchinhalt über das CAT-Protokoll (German)"
        }
    }
}

def decode_public_key(pubkey_str):
    """Convert a Bech32 public key to raw format for verification"""
    # In a real implementation, you would decode the Bech32/base58/base64 key
    # Here we just use our mock database
    pubkey_hex = TRUSTED_ISSUERS.get(pubkey_str)
    if not pubkey_hex:
        return None
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        return public_key
    except ValueError:
        return None

def verify_signature(ticket):
    """Verify the ticket signature using the issuer's public key"""
    try:
        # 1. Get the raw form of the public key
        public_key = decode_public_key(ticket["pubkey"])
        if not public_key:
            return False, "Unknown issuer"
        
        # 2. Create a copy of the ticket without the signature
        ticket_copy = ticket.copy()
        signature_b64 = ticket_copy.pop("sig")
        signature_bytes = base64.b64decode(signature_b64)
        
        # 3. Create a deterministic string representation of the ticket
        ticket_data = json.dumps(ticket_copy, sort_keys=True, separators=(',', ':')).encode()
        
        # 4. Verify the signature
        public_key.verify(signature_bytes, ticket_data)
        
        return True, "Signature valid"
    except InvalidSignature:
        return False, "Invalid signature"
    except Exception as e:
        return False, f"Verification error: {str(e)}"

def verify_expiration(ticket):
    """Verify that the ticket has not expired"""
    current_time = int(time.time())
    if current_time > ticket.get("exp", 0):
        return False, "Ticket expired"
    return True, "Ticket valid"

def verify_ticket(ticket):
    """Verify all aspects of the ticket"""
    # Check expiration
    exp_valid, exp_msg = verify_expiration(ticket)
    if not exp_valid:
        return False, exp_msg
    
    # Check signature
    sig_valid, sig_msg = verify_signature(ticket)
    if not sig_valid:
        return False, sig_msg
    
    return True, "Ticket valid"

@app.get('/content')
async def get_content(ticket: str, lang: str = "en"):
    """Endpoint to get content using a CAT ticket"""
    try:
        # Decode and parse the ticket
        ticket_json = base64.b64decode(ticket).decode('utf-8')
        ticket = json.loads(ticket_json)
        
        # Verify the ticket
        valid, message = verify_ticket(ticket)
        if not valid:
            raise HTTPException(status_code=403, detail=message)
        
        # Get the requested content
        resource = ticket.get("resource")
        chunk_id = ticket.get("chunk", "full")
        
        if resource not in CONTENT_DB:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if chunk_id not in CONTENT_DB[resource]:
            raise HTTPException(status_code=404, detail="Content chunk not found")
        
        content_versions = CONTENT_DB[resource][chunk_id]
        if lang not in content_versions:
            lang = "en" # Fallback to English if the requested language is not available
        content = content_versions[lang]
        
        # Log the redemption (in a real system, this would be saved for royalty accounting)
        logging.info(f"Ticket redeemed: {ticket['pubkey']} accessed {resource} chunk {chunk_id}")
        
        # Return the content
        return {
            "status": "success",
            "resource": resource,
            "chunk": chunk_id,
            "lang": lang,
            "content": content
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid ticket format")
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logging.error(f"Error processing ticket: {str(e)}")
        raise HTTPException(status_code=500, detail="Server error processing ticket")

@app.get('/health')
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "CAT Content Provider"}

# Usage Instructions:
# 1. Install dependencies: pip install fastapi uvicorn cryptography
# 2. Run the service: uvicorn content_service:app --reload
# 3. Create a CAT ticket (JSON), base64 encode it, and pass it as a query parameter.
#
# Example Ticket:
# {
#   "resource": "https://example.com/article/abc123",
#   "ts": 1711180800,
#   "exp": 1799740800,
#   "chunk": "1",
#   "pubkey": "npub1abc123",
#   "sig": "mock_signature"
# }
#
# 4. Base64 encode the ticket:
#    python -c 'import json, base64; ticket = {"resource": "https://example.com/article/abc123", "ts": 1711180800, "exp": 1799740800, "chunk": "1", "pubkey": "npub1abc123", "sig": "mock_signature"}; print(base64.b64encode(json.dumps(ticket).encode()).decode())'
#
# 5. Use the output in the request:
#    GET http://localhost:8000/content?ticket=<base64_encoded_ticket>&lang=fr
#
# Ticket Verification Process:
# - Decoding: The base64 encoded ticket is decoded.
# - JSON Parsing: The decoded ticket is parsed as a JSON object.
# - Expiration Check: The service checks if the current time is past the expiration time (`exp`) in the ticket.
# - Signature Verification:
#   - The service retrieves the public key of the issuer from its trusted issuers database using the `pubkey` field.
#   - It reconstructs the signed payload by creating a stringified JSON representation of the ticket (excluding the `sig` field), with keys sorted alphabetically.
#   - It verifies the signature using the issuer's public key and the reconstructed payload.
# - Content Retrieval: If the ticket is valid, the service retrieves the content chunk specified in the ticket.
#
# Health Check:
# GET http://localhost:8000/health
