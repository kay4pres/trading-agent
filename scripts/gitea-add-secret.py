# Add GitHub PAT as Gitea Actions Secret
# Reads GitHub PAT from GITUB_PAT env var, Gitea token from Credential Manager
# Handles RSA-OAEP encryption via Python cryptography

import ctypes, json, base64, urllib.request, os, sys

def cred_read(target):
    class CRED(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_int64), ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", ctypes.c_uint32), ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]
    advapi32 = ctypes.windll.advapi32
    cred_read = advapi32.CredReadW
    cred_read.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    cred_read.restype = ctypes.c_bool
    cred_free = advapi32.CredFree
    cred_free.argtypes = [ctypes.c_void_p]
    ptr = ctypes.c_void_p()
    if cred_read(target, 1, 0, ctypes.byref(ptr)):
        cred = ctypes.cast(ptr, ctypes.POINTER(CRED)).contents
        blob = bytes(cred.CredentialBlob[:cred.CredentialBlobSize])
        cred_free(ptr)
        return blob.decode("utf-16-le", errors="replace")
    return None

GITEA_TOKEN = cred_read("gitea:http://10.8.0.10:3000")
GITHUB_PAT  = os.environ.get("GITHUB_PAT", "")

if not GITEA_TOKEN:
    print("ERROR: No Gitea token in Credential Manager.")
    print("Run: powershell -ExecutionPolicy Bypass -File scripts/gitea-store-token.ps1")
    sys.exit(1)

if not GITHUB_PAT:
    print("ERROR: Set $env:GITHUB_PAT='your-token' first (PowerShell, one line).")
    print("Example: $env:GITHUB_PAT='ghp_xxxxxxxxxxxx'")
    sys.exit(1)

GITEA = "http://10.8.0.10:3000"
HEADERS = {"Authorization": f"token {GITEA_TOKEN}", "Accept": "application/json"}
REPO = "trading/trading-agent"

# Step 1: Get Gitea's Actions public key
req = urllib.request.Request(
    f"{GITEA}/api/v1/repos/{REPO}/actions/secrets/public-key",
    headers=HEADERS
)
with urllib.request.urlopen(req, timeout=15) as r:
    pk = json.loads(r.read())

pub_key_pem = pk["public_key"]
key_id = pk["key_id"]
print(f"Got public key (id={key_id})")

# Step 2: RSA-OAEP encrypt GitHub PAT
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

pub_key = serialization.load_ssh_public_key(pub_key_pem.encode(), backend=default_backend())
encrypted = pub_key.encrypt(
    GITHUB_PAT.encode(),
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)
encrypted_b64 = base64.b64encode(encrypted).decode()
print("PAT encrypted")

# Step 3: PUT the encrypted secret
req = urllib.request.Request(
    f"{GITEA}/api/v1/repos/{REPO}/actions/secrets/GITHUB_PAT",
    data=json.dumps({"encrypted_value": encrypted_b64, "key_id": key_id}).encode(),
    headers={**HEADERS, "Content-Type": "application/json"},
    method="PUT"
)
with urllib.request.urlopen(req, timeout=15) as r:
    r.read()

print()
print("SUCCESS: GITHUB_PAT stored in Gitea Actions secrets")
print("Gitea will now mirror main -> GitHub on every push to main.")
