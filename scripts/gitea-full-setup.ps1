# Gitea Full Setup - Kay's Self-Hosted Git
# Reads token from Windows Credential Manager

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
$Headers = @{
    "Authorization" = "token $Token"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
}

function call($method, $path, $body) {
    $params = @{ Method = $method; Headers = $Headers; TimeoutSec = 30 }
    if ($body) { $params.Body = $body | ConvertTo-Json -Depth 3 }
    Invoke-RestMethod "$GITEA$path" @params
}

function create($method, $path, $body) {
    try {
        $result = call $method $path $body
        Write-Host "  Created: $($result.full_name)" -ForegroundColor Green
        return $result
    } catch {
        $code = [int]$_.Exception.Response.StatusCode
        if ($code -eq 409) {
            Write-Host "  Already exists - skipping" -ForegroundColor DarkGray
        } else {
            Write-Host "  Error $code : $_" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "=== 1. Create 'trading' org ===" -ForegroundColor Yellow
create POST "/api/v1/orgs" @{
    username    = "trading"
    description = "Day trading automation, data, and research"
    visibility  = "private"
}

Write-Host ""
Write-Host "=== 2. Create trading org repos ===" -ForegroundColor Yellow
create POST "/api/v1/orgs/trading/repos" @{ name="trading-agent";   description="AI day trading agent - Ross Cameron strategy"; private=$true; auto_init=$false; default_branch="main" }
create POST "/api/v1/orgs/trading/repos" @{ name="trading-data";    description="CSV datasets, backtest results, watchlists";       private=$true; auto_init=$false; default_branch="main" }
create POST "/api/v1/orgs/trading/repos" @{ name="trading-journal"; description="Trade log, performance tracking, journal";        private=$true; auto_init=$false; default_branch="main" }

Write-Host ""
Write-Host "=== 3. Create kay user repos ===" -ForegroundColor Yellow
create POST "/api/v1/user/repos" @{ name="ai-brain";  description="Personal knowledge system, notes, research";  private=$true; auto_init=$false; default_branch="main" }
create POST "/api/v1/user/repos" @{ name="dotfiles";  description="Terminal config, PowerShell profiles";       private=$true; auto_init=$false; default_branch="main" }
create POST "/api/v1/user/repos" @{ name="notes";     description="Screenshots, snippets, misc notes";          private=$true; auto_init=$false; default_branch="main" }

Write-Host ""
Write-Host "=== 4. Migrate trading/trading-agent from GitHub as mirror ===" -ForegroundColor Yellow
create POST "/api/v1/repos/migrate" @{
    clone_addr  = "https://github.com/kay4pres/trading-agent.git"
    repo_name   = "trading-agent"
    repo_owner  = "trading"
    service     = "git"
    wiki        = $false
    issues      = $false
    milestones  = $false
    labels      = $false
    comments    = $false
    releases    = $false
    pulls       = $false
    private     = $true
    mirror      = $true
    description = "AI day trading agent - Ross Cameron strategy"
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Check repos at: $GITEA" -ForegroundColor Green
