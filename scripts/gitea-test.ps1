# Test Gitea connection
# Reads token from Windows Credential Manager via CredRead API

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class CredReader {
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredRead(string target, int type, int flags, out IntPtr credential);

    [DllImport("advapi32.dll")]
    public static extern void CredFree(IntPtr buffer);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public int    Flags;
        public int    Type;
        public string TargetName;
        public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public int    CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int    Persist;
        public int    AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    public static string GetPassword(string target) {
        IntPtr credPtr;
        if (CredRead(target, 1, 0, out credPtr)) {
            try {
                CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(credPtr, typeof(CREDENTIAL));
                if (cred.CredentialBlobSize > 0) {
                    return Marshal.PtrToStringUni(cred.CredentialBlob, cred.CredentialBlobSize / 2);
                }
            } finally { CredFree(credPtr); }
        }
        return null;
    }
}
"@

$Target = "gitea:http://10.8.0.10:3000"
$Token  = [CredReader]::GetPassword($Target)

if (-not $Token) {
    Write-Host "No Gitea credential found. Run gitea-store-token.ps1 first." -ForegroundColor Red
    exit 1
}

$GITEA   = "http://10.8.0.10:3000"
$Headers = @{
    "Authorization" = "token $Token"
    "Content-Type" = "application/json"
    "Accept"       = "application/json"
}

Write-Host "Testing Gitea connection..." -ForegroundColor Yellow
try {
    $ver = Invoke-RestMethod "$GITEA/api/v1/version" -Headers $Headers -TimeoutSec 10
    Write-Host "Connected to Gitea $($ver.version) - token is valid" -ForegroundColor Green
} catch {
    Write-Host "Failed: $_" -ForegroundColor Red
    exit 1
}
