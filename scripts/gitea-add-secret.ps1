# Add GitHub PAT as Gitea Actions Secret (PowerShell)
# Reads Gitea token from Credential Manager, asks for GitHub PAT at prompt

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
    Write-Host "ERROR: No Gitea token in Credential Manager. Run gitea-store-token.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Paste your GitHub PAT and press Enter:" -ForegroundColor Yellow
$Pat = Read-Host -AsSecureString
$PlainPat = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Pat)
)

$GITEA   = "http://10.8.0.10:3000"
$Headers = @{
    "Authorization" = "token $GiteaToken"
    "Accept"       = "application/json"
}
$Repo = "trading/trading-agent"
$SecretName = "GITHUB_PAT"

# Step 1: Get Gitea's public key for this repo
Write-Host "Fetching Gitea Actions public key..." -ForegroundColor Cyan
$pk = Invoke-RestMethod "$GITEA/api/v1/repos/$Repo/actions/secrets/public-key" `
    -Headers $Headers -TimeoutSec 15

$PubKey = $pk.public_key
$KeyId  = $pk.key_id
Write-Host "  Got key (id=$KeyId)" -ForegroundColor Gray

# Step 2: Encrypt PAT using RSA-OAEP with the public key
Write-Host "Encrypting PAT..." -ForegroundColor Cyan
Add-Type -AssemblyName System.Security

$keyBytes = [System.Text.Encoding]::UTF8.GetBytes($PubKey)
$rsa = [System.Security.Cryptography.RSA]::Create()
$rsa.ImportFromOpenSSHPublicKey($keyBytes)
$encrypted = $rsa.Encrypt($PlainPat, [System.Security.Cryptography.RSAEncryptionPadding]::OaepSHA256)
$EncryptedB64 = [Convert]::ToBase64String($encrypted)

# Step 3: PUT the encrypted secret
Write-Host "Storing encrypted secret..." -ForegroundColor Cyan
$Body = @{ encrypted_value = $EncryptedB64; key_id = $KeyId } | ConvertTo-Json

try {
    Invoke-RestMethod "$GITEA/api/v1/repos/$Repo/actions/secrets/$SecretName" `
        -Method PUT -Headers $Headers -Body $Body -TimeoutSec 15 | Out-Null
} catch {
    Write-Host "Failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "SUCCESS: '$SecretName' added to $Repo" -ForegroundColor Green
Write-Host "Gitea will now mirror main -> GitHub on every push to main." -ForegroundColor Green
