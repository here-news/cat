import json
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend

def generate_key_pair():
    """Generates an Ed25519 key pair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key

def sign_ticket(ticket, private_key):
    """Signs the ticket using the provided private key."""
    # Create a deterministic string representation of the ticket
    ticket_data = json.dumps(ticket, sort_keys=True, separators=(',', ':')).encode()
    
    # Sign the ticket data
    signature = private_key.sign(ticket_data)
    
    # Encode signature to base64
    signature_b64 = base64.b64encode(signature).decode()
    
    return signature_b64

def create_ticket(resource, chunk, pubkey_str, private_key):
    """Creates a CAT ticket and signs it."""
    timestamp = int(time.time())
    expiration = timestamp + 300  # Valid for 5 minutes
    
    ticket = {
        "resource": resource,
        "ts": timestamp,
        "exp": expiration,
        "chunk": str(chunk),
        "pubkey": pubkey_str
    }
    
    # Sign the ticket
    signature = sign_ticket(ticket, private_key)
    ticket["sig"] = signature
    
    return ticket

def encode_public_key(public_key):
    """Encodes the public key to a hex string."""
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return public_key_bytes.hex()

if __name__ == '__main__':
    # Generate a key pair
    private_key, public_key = generate_key_pair()
    
    # Encode the public key
    public_key_hex = encode_public_key(public_key)
    
    # Example usage:
    resource_url = "https://example.com/article/abc123"
    chunk_id = 1
    
    # Create a ticket
    ticket = create_ticket(resource_url, chunk_id, "npub1test", private_key)
    
    # Base64 encode the ticket
    ticket_json = json.dumps(ticket)
    ticket_b64 = base64.b64encode(ticket_json.encode()).decode()
    
    print("Public Key (Hex):", public_key_hex)
    print("Base64 Encoded Ticket:", ticket_b64)
    print("\nTo use this ticket, pass it as a query parameter to the /content endpoint:")
    print(f"http://localhost:8000/content?ticket={ticket_b64}")
