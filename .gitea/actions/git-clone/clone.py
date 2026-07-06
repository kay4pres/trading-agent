#!/usr/bin/env python3
"""Python-based git clone - works on any host with Python + git."""
import subprocess, os, sys, urllib.parse

repo = os.environ.get("GITHUB_REPOSITORY", "")
ref = os.environ.get("GITHUB_REF", "refs/heads/main")
workspace = os.environ.get("GITHUB_WORKSPACE", ".")
token = os.environ.get("GITHUB_TOKEN", "")
server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

if not repo:
    print("ERROR: GITHUB_REPOSITORY not set")
    sys.exit(1)

# Extract branch from ref
if ref.startswith("refs/heads/"):
    branch = ref[len("refs/heads/"):]
elif ref.startswith("refs/tags/"):
    branch = ref[len("refs/tags/"):]
else:
    branch = ref

# Construct clone URL
if token:
    if server == "https://github.com":
        clone_url = f"https://x-access-token:{token}@github.com/{repo}"
    else:
        clone_url = f"https://x-access-token:{token}@{server.replace('https://', '')}/{repo}"
else:
    clone_url = f"{server}/{repo}"

workspace = os.path.abspath(workspace)
os.makedirs(workspace, exist_ok=True)

print(f"Cloning {repo} ({branch}) into {workspace}")

# Use git init + fetch instead of clone to avoid nested .git
os.chdir(workspace)
subprocess.run(["git", "init"], check=True)
subprocess.run(["git", "remote", "add", "origin", clone_url], check=True)
subprocess.run(["git", "config", "--global", "init.defaultBranch", "main"], check=True)
subprocess.run(["git", "config", "--global", "user.email", "ci@local"], check=True)
subprocess.run(["git", "config", "--global", "user.name", "CI Bot"], check=True)
result = subprocess.run(["git", "fetch", "--depth=1", "origin", ref], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Fetch failed: {result.stderr.decode()}")
    sys.exit(1)
subprocess.run(["git", "checkout", "-f", ref], check=True)
print("Clone complete!")
print(subprocess.run(["ls", "-la"], capture_output=True).stdout.decode())
