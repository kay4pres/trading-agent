# Add NAS Registry Credentials as Gitea Actions Secrets
# Usage:
#   1. Set NAS_REGISTRY_USER:
#      dot-source this script with -SecretName "NAS_REGISTRY_USER" -SecretValue "admin"
#   2. Set NAS_REGISTRY_PASS:
#      dot-source this script with -SecretName "NAS_REGISTRY_PASS" -SecretValue "your-password"
#
# Or run interactively — script will prompt for both username and password.

param(
    [string]$SecretName  = "",
    [string]$SecretValue = ""
)

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class CredReader {
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredRead(string target, int type, int flags, out IntPtr credential);
    [DllImport("advapi32.dll")]
    public static extern void CredFree(IntPtr buffer);
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public int Flags, Type;
        public string TargetName, Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public int CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int Persist, AttributeCount;
        public IntPtr Attributes, TargetAlias, UserName;
    }
    public static string GetPassword(string target) {
        IntPtr credPtr;
        if (CredRead(target, 1, 0, out credPtr)) {
            try {
                var cred = (CREDENTIAL)Marshal.PtrToStructure(credPtr, typeof(CREDENTIAL));
                if (cred.CredentialBlobSize > 0)
                    return Marshal.PtrToStringUni(cred.CredentialBlob, cred.CredentialBlobSize / 2);
            } finally { CredFree(credPtr); }
        }
        return null;
    }
}
"@

$GiteaToken = [CredReader]::GetPassword("gitea:http://10.8.0.10:3000")
if (-not $GiteaToken) {
    Write-Host "ERROR: No Gitea token in Credential Manager." -ForegroundColor Red
    Write-Host "Run: .\scripts\gitea-store-token.ps1 first." -ForegroundColor Yellow
    exit 1
}

$GITEA   = "http://10.8.0.10:3000"
$Headers = @{
    "Authorization" = "token $GiteaToken"
    "Accept"        = "application/json"
}
$Repo = "trading/trading-agent"

# ── Interactive prompts if no args ──────────────────────────────────────────
if (-not $SecretName) {
    Write-Host ""
    Write-Host "=== Gitea Actions Secrets Setup ===" -ForegroundColor Cyan
    Write-Host "Available secrets: NAS_REGISTRY_USER, NAS_REGISTRY_PASS, GITEA_RUNNER_TOKEN"
    Write-Host ""
    $SecretName = Read-Host "Secret name (NAS_REGISTRY_USER / NAS_REGISTRY_PASS / GITEA_RUNNER_TOKEN)"
}

if (-not $SecretValue) {
    $Secure = Read-Host -AsSecureString "Secret value for '$SecretName'"
    $SecretValue = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    )
}

if (-not $SecretName -or -not $SecretValue) {
    Write-Host "Usage: .\$($MyInvocation.MyCommand.Name) -SecretName 'NAME' -SecretValue 'VALUE'"
    exit 1
}

# ── Step 1: Get Gitea's public key for this repo ─────────────────────────────
Write-Host "Fetching Gitea public key..." -ForegroundColor Gray
try {
    $pk = Invoke-RestMethod "$GITEA/api/v1/repos/$Repo/actions/secrets/public-key" `
        -Headers $Headers -TimeoutSec 15
} catch {
    Write-Host "Failed to get public key. Is Gitea Actions enabled?" -ForegroundColor Red
    Write-Host "Enable: Site Admin → Actions → Enable Local Runner" -ForegroundColor Yellow
    exit 1
}

$PubKey = $pk.public_key
$KeyId  = $pk.key_id
Write-Host "  Got key id=$KeyId" -ForegroundColor Gray

# ── Step 2: Encrypt secret with RSA-OAEP ─────────────────────────────────────
Write-Host "Encrypting secret..." -ForegroundColor Gray
Add-Type -AssemblyName System.Security

$keyBytes  = [System.Text.Encoding]::UTF8.GetBytes($PubKey)
$rsa       = [System.Security.Cryptography.RSA]::Create()
$rsa.ImportFromOpenSSHPublicKey($keyBytes)
$encrypted = $rsa.Encrypt([System.Text.Encoding]::UTF8.GetBytes($SecretValue),
                           [System.Security.Cryptography.RSAEncryptionPadding]::OaepSHA256)
$EncryptedB64 = [Convert]::ToBase64String($encrypted)

# ── Step 3: PUT the encrypted secret ─────────────────────────────────────────
$Body = @{ encrypted_value = $EncryptedB64; key_id = $KeyId } | ConvertTo-Json

try {
    Invoke-RestMethod "$GITEA/api/v1/repos/$Repo/actions/secrets/$SecretName" `
        -Method PUT -Headers $Headers -Body $Body -TimeoutSec 15 | Out-Null
} catch {
    Write-Host "Failed to set secret: $_" -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: '$SecretName' stored in $Repo" -ForegroundColor Green
Write-Host "Gitea Actions workflow can now use it as " -ForegroundColor Green -NoNewline
Write-Host "`${{ secrets.$SecretName }}" -ForegroundColor White
