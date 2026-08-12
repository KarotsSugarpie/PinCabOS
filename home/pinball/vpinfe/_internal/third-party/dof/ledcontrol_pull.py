#!/usr/bin/env python3
import argparse
import os
import sys
import tempfile
import platform
import subprocess
import re
import requests
import zipfile


def _default_base_path() -> str:
    """Return the platform-specific default VPinballX 10.8 directoutputconfig directory."""
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', home)
        return os.path.join(appdata, 'VPinballX', '10.8', 'directoutputconfig')
    elif sys.platform == 'darwin':
        return os.path.join(home, 'Library', 'Application Support', 'VPinballX', '10.8', 'directoutputconfig')
    else:  # Linux / other POSIX
        return os.path.join(home, '.local', 'share', 'VPinballX', '10.8', 'directoutputconfig')

VERSION = "2.0"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36",
    "Accept": "application/zip,application/octet-stream,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Referer": "https://configtool.vpuniverse.com/app/",
    "Origin": "https://configtool.vpuniverse.com",
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def iif(cond, a, b):
    return a if cond else b


def ensure_ini(file_path: str) -> None:
    """Create the INI with a zero version marker if it does not exist."""
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write('[version]\nversion=0\n')


def read_ini(file_path, section, key):
    """
    Compatible with VBS ReadIni behavior
    """
    if not os.path.exists(file_path):
        return ""

    section = section.lower()
    key = key.lower()

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    in_section = False
    for line in lines:
        line = line.strip()

        if line.lower() == f"[{section}]":
            in_section = True
            continue

        if in_section:
            if line.startswith("["):
                break

            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip().lower() == key:
                    v = v.strip()
                    return v if v else " "

    return ""


# -------------------------------------------------
# Argument parsing
# -------------------------------------------------
parser = argparse.ArgumentParser(description="VPUniverse DOF Config Pull Utility")

parser.add_argument("-A", "--apikey", default="")
parser.add_argument("-F", "--file", default="directoutputconfig.zip")
parser.add_argument("-T", "--target", default="")
parser.add_argument("-V", "--verbose", action="store_true")
parser.add_argument("-L", "--log", action="store_true")
parser.add_argument("-Y", "--overwrite", action="store_true")
parser.add_argument("-D", "--debug", action="store_true")
parser.add_argument("--force", action="store_true")

args = parser.parse_args()

param_apikey = args.apikey
param_savefile = args.file
param_directoutputconfigpath = args.target
param_verbose = args.verbose
param_log = args.log
param_overwrite = 2 if args.overwrite else 1
param_debug = args.debug
param_forceupdate = args.force

if not param_directoutputconfigpath:
    param_directoutputconfigpath = _default_base_path()


def status(message: str) -> None:
    """Always-visible status output for key pull stages."""
    print(message)


def debug(message: str) -> None:
    if param_debug:
        print(message)


def _sanitize_headers(headers_map):
    """Return headers with sensitive values masked for debug output."""
    sanitized = {}
    for k, v in headers_map.items():
        if k.lower() in ("authorization", "cookie", "set-cookie"):
            sanitized[k] = "<masked>"
        else:
            sanitized[k] = v
    return sanitized


def _response_preview(response: requests.Response, limit: int = 300) -> str:
    try:
        body = response.text
    except Exception as e:
        return f"<unable to decode response body: {e}>"

    body = body.replace("\r", "\\r").replace("\n", "\\n")
    if len(body) > limit:
        return body[:limit] + "...(truncated)"
    return body


def debug_http_response(label: str, response: requests.Response) -> None:
    debug(f"** HTTP DEBUG [{label}]")
    debug(f"request.method = {response.request.method}")
    debug(f"request.url = {response.request.url}")
    debug(f"request.headers = {_sanitize_headers(dict(response.request.headers))}")
    debug(f"response.url = {response.url}")
    debug(f"response.status = {response.status_code} {response.reason}")
    debug(f"response.elapsed_ms = {int(response.elapsed.total_seconds() * 1000)}")
    debug(f"response.headers = {_sanitize_headers(dict(response.headers))}")
    debug(f"response.history_count = {len(response.history)}")
    for idx, h in enumerate(response.history, start=1):
        debug(f"response.history[{idx}] = {h.status_code} {h.reason} -> {h.url}")
    debug(f"response.body.preview = {_response_preview(response)}")


def _windows_vbs_helper_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledcontrol_pull_win.vbs")


def _run_windows_vbs_helper(mode: str, apikey: str = "", zip_file: str = "") -> tuple[str, str]:
    helper = _windows_vbs_helper_path()
    if not os.path.isfile(helper):
        raise RuntimeError(f"Windows helper script not found: {helper}")

    cmd = ["cscript", "//nologo", helper, f"/M={mode}"]
    if apikey:
        cmd.append(f"/A={apikey}")
    if zip_file:
        cmd.append(f"/F={zip_file}")
    if param_debug:
        cmd.append("/D")

    debug(f"** Windows helper command = {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, capture_output=True, text=False, check=False)
    except OSError as e:
        raise RuntimeError(f"Unable to run cscript/VBS helper: {e}")

    def _decode_output(raw: bytes) -> str:
        if not raw:
            return ""
        for enc in ("utf-8", "utf-16-le", "utf-16", "mbcs", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("latin-1", errors="replace")

    stdout_text = _decode_output(p.stdout).replace("\x00", "")
    stderr_text = _decode_output(p.stderr).replace("\x00", "")

    if param_debug:
        debug(f"** Windows helper exit code = {p.returncode}")
        if stdout_text.strip():
            debug(f"** Windows helper stdout:\n{stdout_text.rstrip()}")
        if stderr_text.strip():
            debug(f"** Windows helper stderr:\n{stderr_text.rstrip()}")

    if p.returncode != 0:
        err_text = stderr_text.strip() or stdout_text.strip() or "no output"
        raise RuntimeError(f"Windows helper failed (exit {p.returncode}): {err_text}")

    return stdout_text, stderr_text


def _windows_get_online_version(apikey: str) -> int:
    stdout_text, stderr_text = _run_windows_vbs_helper("version", apikey=apikey)
    combined = "\n".join(part for part in (stdout_text, stderr_text) if part)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.isdigit():
            return int(line)
    m = re.search(r"\b(\d+)\b", combined)
    if m:
        return int(m.group(1))
    raise RuntimeError(
        "Windows helper did not return a numeric version. "
        f"stdout=[{stdout_text.strip()}] stderr=[{stderr_text.strip()}]"
    )


def _windows_download_zip(apikey: str, zip_file: str) -> None:
    _run_windows_vbs_helper("download", apikey=apikey, zip_file=zip_file)


# -------------------------------------------------
# Banner
# -------------------------------------------------
if param_verbose:
    print(f"**** VPUniverse DOF Config Tool Pull Utility (v{VERSION})")
    print("")


if param_debug:
    print("** Debug Parameters")
    print("apikey =", param_apikey)
    print("savefile =", param_savefile)
    print("target =", param_directoutputconfigpath)
    print("platform =", platform.platform())
    print("python =", sys.version.replace("\n", " "))
    print("requests =", requests.__version__)


# -------------------------------------------------
# URLs
# -------------------------------------------------
version_url = "https://configtool.vpuniverse.com/api.php?query=version"
download_url = f"https://configtool.vpuniverse.com/api.php?query=getconfig&apikey={param_apikey}"
site_root_url = "https://configtool.vpuniverse.com/"


# -------------------------------------------------
# Validate / create target folder
# -------------------------------------------------
if not os.path.isdir(param_directoutputconfigpath):
    try:
        os.makedirs(param_directoutputconfigpath, exist_ok=True)
    except OSError as e:
        print(f"** Error: Could not create destination path [{param_directoutputconfigpath}]: {e}")
        sys.exit(1)


# -------------------------------------------------
# Always fetch the online version (needed for INI update after download too)
# -------------------------------------------------
status("Retrieving online version...")
session = None
if sys.platform == "win32":
    try:
        online_version = _windows_get_online_version(param_apikey)
        status(f"Online version retrieved: {online_version}")
    except Exception as e:
        print(f"** Failed to retrieve online version: {e}")
        sys.exit(1)
else:
    session = requests.Session()
    session.headers.update(headers)

    # Preflight homepage hit to establish any bot/WAF cookies before API calls.
    try:
        preflight = session.get(site_root_url, timeout=20)
        debug_http_response("preflight", preflight)
    except requests.RequestException as e:
        debug(f"** Preflight request failed: {type(e).__name__}: {e}")

    try:
        r = session.get(version_url, timeout=20)
    except requests.RequestException as e:
        print(f"** Failed to retrieve online version: {type(e).__name__}: {e}")
        sys.exit(1)

    debug_http_response("version", r)

    if r.status_code == 200 and r.text.strip().isdigit():
        online_version = int(r.text.strip())
        status(f"Online version retrieved: {online_version}")
    else:
        print("** Failed to retrieve online version.")
        print(f"   HTTP status: {r.status_code} {r.reason}")
        print(f"   Response preview: {_response_preview(r, limit=200)}")
        sys.exit(1)

if param_debug or param_verbose:
    print("Online Version =", online_version)


# -------------------------------------------------
# Version check
# -------------------------------------------------
ini_file = os.path.join(os.path.dirname(param_directoutputconfigpath), "dofconfigversion.ini")
ensure_ini(ini_file)

bDoDownload = False

if param_forceupdate:
    bDoDownload = True
else:
    if param_debug or param_verbose:
        print("**** Checking INI Version ****")

    ini_version = read_ini(ini_file, "version", "version")
    try:
        ini_version = int(ini_version)
    except:
        print("** Warning: Version not found in ini file. Updating regardless.")
        ini_version = -1

    if param_debug or param_verbose:
        print("INI Version =", ini_version)

    bDoDownload = online_version > ini_version

    if not bDoDownload:
        if online_version < ini_version:
            print(f"** Warning: Local version ({ini_version}) newer than online ({online_version})")
        else:
            print(f"** Version ({online_version}) is current.")


# -------------------------------------------------
# Download
# -------------------------------------------------
if bDoDownload:
    status("Retrieving config archive...")

    tmp_fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix="dofconfig_")
    os.close(tmp_fd)

    try:
        if sys.platform == "win32":
            try:
                _windows_download_zip(param_apikey, zip_path)
                status("Successful download.")
            except Exception as e:
                print(f"** Failed download: {e}")
                sys.exit(1)
        else:
            try:
                r = session.get(download_url, stream=True, timeout=40)
            except requests.RequestException as e:
                print(f"** Failed download: {type(e).__name__}: {e}")
                sys.exit(1)

            debug_http_response("download", r)

            if r.status_code == 200:
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                status("Successful download.")
            else:
                print(f"** Failed download (HTTP {r.status_code}).")
                print(f"   Response preview: {_response_preview(r, limit=200)}")
                sys.exit(1)

        if not os.path.exists(zip_path):
            print("** Failed download: archive file was not created.")
            sys.exit(1)

        zip_size = os.path.getsize(zip_path)
        debug(f"** Downloaded archive size: {zip_size} bytes")
        if zip_size <= 0:
            print("** Failed download: archive file is empty.")
            sys.exit(1)

        if not zipfile.is_zipfile(zip_path):
            print("** Failed download: response is not a valid ZIP archive.")
            if param_debug:
                try:
                    with open(zip_path, "rb") as f:
                        sample = f.read(240)
                    sample_text = sample.decode("utf-8", errors="replace").replace("\r", "\\r").replace("\n", "\\n")
                    debug(f"** Archive preview (decoded): {sample_text}")
                except Exception as e:
                    debug(f"** Could not read archive preview: {e}")
            sys.exit(1)

        status("Extracting files...")
        if param_debug or param_verbose:
            print("From:", zip_path)
            print("To:", param_directoutputconfigpath)

        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.infolist():
                dest = os.path.join(param_directoutputconfigpath, member.filename)
                if member.is_dir():
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(member) as src, open(dest, "wb") as out:
                        out.write(src.read())
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    # Update stored version in INI
    with open(ini_file, 'w') as f:
        f.write(f'[version]\nversion={online_version}\n')

    status(f"Done: config updated to v{online_version}.")
else:
    status("No download needed: local configuration is already up to date.")
