# List existing Gitea repos for mavis-agent user

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

$Token   = [CredReader]::GetPassword("gitea:http://10.8.0.10:3000")
$GITEA   = "http://10.8.0.10:3000"
$Headers = @{ "Authorization" = "token $Token"; "Accept" = "application/json" }

Write-Host "=== mavis-agent repos ===" -ForegroundColor Yellow
try {
    $userRepos = Invoke-RestMethod "$GITEA/api/v1/user/repos" -Headers $Headers -TimeoutSec 15
    foreach ($r in $userRepos) {
        $vis = if ($r.private) { "private" } else { "public" }
        Write-Host "  $($r.full_name) [$vis]"
    }
    if (-not $userRepos) { Write-Host "  (none)" -ForegroundColor DarkGray }
} catch { Write-Host "  Error: $_" -ForegroundColor Red }

Write-Host ""
Write-Host "=== trading org repos ===" -ForegroundColor Yellow
try {
    $orgRepos = Invoke-RestMethod "$GITEA/api/v1/orgs/trading/repos" -Headers $Headers -TimeoutSec 15
    foreach ($r in $orgRepos) {
        $vis = if ($r.private) { "private" } else { "public" }
        Write-Host "  $($r.full_name) [$vis]"
    }
    if (-not $orgRepos) { Write-Host "  (none)" -ForegroundColor DarkGray }
} catch { Write-Host "  trading org not found or no access" -ForegroundColor DarkGray }
