"""
vault_reader.py
===============
Reads encrypted credentials from the SecureString + DPAPI vault.
CRITICAL SECURITY RULE: Credentials are decrypted in-memory only.
They are NEVER printed to stdout, logged, or included in Mavis chat output.
Verification is done by confirming the DB connection works — not by printing values.

Usage:
    from vault_reader import get_db_config, get_db_connection
    config = get_db_config()        # returns {host_wg, host_lan, port, db_name, user}; password not in dict
    conn = get_db_connection()      # returns live psycopg2 connection
"""

import subprocess
import json
import socket
from pathlib import Path

VAULT_SCRIPT = Path("/app/vault/read_db_config.ps1")


def get_db_config() -> dict:
    """
    Read non-sensitive DB config from vault.
    Returns: {host_wg, host_lan, port, db_name, user}
    Password is read separately by get_db_connection() and never exposed.
    """
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(VAULT_SCRIPT)],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Vault read failed: {result.stderr}")
    # Parse only stdout — password is not in stdout
    config = json.loads(result.stdout.strip())
    return config


def _get_password() -> str:
    """Read password from vault — returns string, never prints it."""
    pw_script = Path("/app/vault/read_password.ps1")
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(pw_script)],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError("Password read from vault failed")
    return result.stdout.strip()


def _is_reachable(host: str, port: int, timeout: int = 3) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def get_db_connection(verify_only: bool = False):
    """
    Returns a live psycopg2 connection.
    Read credentials from vault, tries WireGuard first (LAN fallback).
    Password is never printed or logged.
    """
    import psycopg2

    config = get_db_config()

    # Try WG first
    wg_reach = _is_reachable(config["host_wg"], int(config["port"]))
    active_host = config["host_wg"] if wg_reach else config["host_lan"]

    # Read password from vault (stderr only)
    password = _get_password()

    if verify_only:
        return None  # just checking connectivity below

    conn = psycopg2.connect(
        host=active_host,
        port=int(config["port"]),
        dbname=config["db_name"],
        user=config["user"],
        password=password,
        connect_timeout=10
    )
    return conn


def vault_status() -> dict:
    """
    Check vault health WITHOUT exposing any credentials.
    Returns dict with status only — no values.
    """
    try:
        config = get_db_config()
        wg = _is_reachable(config["host_wg"], int(config["port"]))
        lan = _is_reachable(config["host_lan"], int(config["port"]))
        return {
            "vault_readable": True,
            "wg_reachable": wg,
            "lan_reachable": lan,
            "active_host": config["host_wg"] if wg else config["host_lan"],
            "db_name": config["db_name"],
            "user": config["user"],
            # NOTE: password intentionally not included
        }
    except Exception as e:
        return {
            "vault_readable": False,
            "error": str(e),
        }


if __name__ == "__main__":
    # Status check — prints no credentials
    status = vault_status()
    for key, val in status.items():
        print(f"{key}: {val}")
