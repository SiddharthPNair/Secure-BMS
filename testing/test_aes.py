
import os
import base64
import json
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

key = base64.b64decode(
    os.environ["AES128_KEY_B64"],
    validate=True,
)

topic = "secure-bms/telemetry"
nonce = secrets.token_bytes(12)

telemetry = {
    "temperature_c": 29.5,
    "state": "NORMAL",
    "alert_events": 0,
}

plaintext = json.dumps(
    telemetry, separators=(",", ":")
).encode("utf-8")

ciphertext = AESGCM(key).encrypt(
    nonce, plaintext, topic.encode("utf-8")
)

decrypted = AESGCM(key).decrypt(
    nonce, ciphertext, topic.encode("utf-8")
)

assert json.loads(decrypted.decode("utf-8")) == telemetry

print("AES-128-GCM round trip: PASS")

try:
    AESGCM(key).decrypt(
        nonce, ciphertext, b"wrong/topic"
    )
    raise AssertionError("Wrong topic was unexpectedly accepted")
except Exception as exc:
    from cryptography.exceptions import InvalidTag
    if not isinstance(exc, InvalidTag):
        raise

print("Wrong-topic authentication test: PASS")
