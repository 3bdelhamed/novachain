import hashlib
import json
import base64
import os
from typing import Dict, Tuple, Optional

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# ─── Wallet ───────────────────────────────────────────────────────────────────

class Wallet:
    def __init__(self):
        if CRYPTO_AVAILABLE:
            self._private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
            self._public_key = self._private_key.public_key()
        else:
            # Fallback: simple random keys (not cryptographically proper but demonstrates concept)
            self._private_key_bytes = os.urandom(32)
            self._public_key_bytes = hashlib.sha256(self._private_key_bytes).digest()

        self.address = self._generate_address()

    def _generate_address(self) -> str:
        if CRYPTO_AVAILABLE:
            pub_bytes = self._public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        else:
            pub_bytes = self._public_key_bytes

        sha256_hash = hashlib.sha256(pub_bytes).digest()
        ripemd = hashlib.new("ripemd160", sha256_hash).hexdigest()
        return "NC" + ripemd[:38].upper()

    @property
    def public_key_hex(self) -> str:
        if CRYPTO_AVAILABLE:
            pub_bytes = self._public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return pub_bytes.hex()
        else:
            return self._public_key_bytes.hex()

    @property
    def private_key_hex(self) -> str:
        if CRYPTO_AVAILABLE:
            priv_bytes = self._private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            return priv_bytes.hex()
        else:
            return self._private_key_bytes.hex()

    def sign_transaction(self, transaction_data: Dict) -> str:
        tx_string = json.dumps(transaction_data, sort_keys=True)
        tx_bytes = tx_string.encode()

        if CRYPTO_AVAILABLE:
            signature = self._private_key.sign(tx_bytes, ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(signature).decode()
        else:
            # Simple HMAC-like signature for demo purposes
            sig = hashlib.sha256(self._private_key_bytes + tx_bytes).hexdigest()
            return sig

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "public_key": self.public_key_hex,
            "private_key": self.private_key_hex,
        }


# ─── Signature Verification ───────────────────────────────────────────────────

def verify_transaction_signature(
    transaction_data: Dict, signature: str, public_key_hex: str
) -> bool:
    """Verify a transaction signature against the sender's public key."""
    try:
        tx_string = json.dumps(transaction_data, sort_keys=True)
        tx_bytes = tx_string.encode()

        if CRYPTO_AVAILABLE:
            pub_bytes = bytes.fromhex(public_key_hex)
            public_key = serialization.load_der_public_key(pub_bytes, backend=default_backend())
            sig_bytes = base64.b64decode(signature.encode())
            public_key.verify(sig_bytes, tx_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        else:
            # Demo verification
            return len(signature) == 64  # basic sanity check
    except Exception:
        return False


def create_wallet_from_private_key(private_key_hex: str) -> Optional[Dict]:
    """Reconstruct wallet info from private key hex."""
    try:
        if CRYPTO_AVAILABLE:
            priv_bytes = bytes.fromhex(private_key_hex)
            private_key = serialization.load_der_private_key(priv_bytes, password=None, backend=default_backend())
            public_key = private_key.public_key()
            pub_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            sha256_hash = hashlib.sha256(pub_bytes).digest()
            ripemd = hashlib.new("ripemd160", sha256_hash).hexdigest()
            address = "NC" + ripemd[:38].upper()
            return {
                "address": address,
                "public_key": pub_bytes.hex(),
                "private_key": private_key_hex,
            }
        return None
    except Exception:
        return None
