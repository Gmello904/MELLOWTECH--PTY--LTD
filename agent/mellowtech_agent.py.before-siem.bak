#!/usr/bin/env python3
"""MellowTech Agent: watches one computer (Windows, Mac or Linux) and reports to the MellowTech platform.

Install   (as Administrator on Windows, or with sudo on Mac and Linux):
    python mellowtech_agent.py install --server https://YOUR-SERVER --key mtk_xxxxxxxx
Remove:
    python mellowtech_agent.py uninstall
Other:
    python mellowtech_agent.py status      show what this computer is reporting
    python mellowtech_agent.py run         run in the foreground (the installed service does this by itself)

It only talks to the server you give it. It never opens a port, and it only does the actions your
administrator sends from the dashboard (virus scan, protection update, block an address, isolate, USB control).
"""
import argparse
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VERSION = "0.3.0"
SYSTEM = platform.system()                       # "Windows", "Darwin" (Mac) or "Linux"
FAMILY = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(SYSTEM, "other")
SERVICE_NAME = "MellowTech Agent"
FROZEN = bool(getattr(sys, "frozen", False))     # True when built into MellowTechAgent.exe

try:
    import psutil
except ImportError:                              # Mac and Linux still work without it
    psutil = None

if SYSTEM == "Windows":
    DATA_DIR = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "MellowTech")
    PROGRAM_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "MellowTech")
elif SYSTEM == "Darwin":
    DATA_DIR, PROGRAM_DIR = "/Library/Application Support/MellowTech", "/Library/MellowTech"
else:
    DATA_DIR, PROGRAM_DIR = "/etc/mellowtech", "/opt/mellowtech"
CONFIG_FILE = os.path.join(DATA_DIR, "agent.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(*parts):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *parts, flush=True)


def is_admin():
    if SYSTEM == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def run(cmd, timeout=60, shell_text=None):
    """Run a command without a shell. Returns (return code, output). Never raises."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                              errors="replace")
        return done.returncode, ((done.stdout or "") + (done.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "command not found: " + str(cmd[0])
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except Exception as exc:
        return 1, str(exc)


def powershell(script, timeout=60):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)


def valid_ip(text):
    try:
        return str(ipaddress.ip_address(str(text).strip()))
    except ValueError:
        return None


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ files
def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path, data, secret=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    if secret and SYSTEM != "Windows":
        os.chmod(temp, 0o600)
    os.replace(temp, path)


def load_state():
    state = read_json(STATE_FILE, {})
    state.setdefault("blocks", {})               # ip -> true
    state.setdefault("isolated_until", None)
    state.setdefault("last_scan", None)
    state.setdefault("threats_found", 0)
    return state


# ------------------------------------------------------------------ talking to the server
class Gone(Exception):
    """The server says this device was removed."""


def call(server, path, body, token=None, timeout=30):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "MellowTechAgent/" + VERSION}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(server.rstrip("/") + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            message = json.loads(text).get("error", text)
        except Exception:
            message = text[:200]
        if exc.code == 401 and token:
            raise Gone(message)
        raise RuntimeError(f"{exc.code}: {message}")


# ------------------------------------------------------------------ facts about this computer
def os_label():
    try:
        if SYSTEM == "Windows":
            return f"Windows {platform.release()} ({platform.version()})"
        if SYSTEM == "Darwin":
            return f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
        if os.path.exists("/etc/os-release"):
            for line in open("/etc/os-release", encoding="utf-8", errors="replace"):
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        return "Linux " + platform.release()
    except Exception:
        return SYSTEM


def local_ip():
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("203.0.113.1", 9))        # no traffic is sent; it only picks the right network card
        address = probe.getsockname()[0]
        probe.close()
        return address
    except Exception:
        return ""


def read_cpu_times():
    with open("/proc/stat", encoding="utf-8") as handle:
        parts = [int(x) for x in handle.readline().split()[1:]]
    return sum(parts), parts[3] + (parts[4] if len(parts) > 4 else 0)


def metrics():
    """CPU, memory and disk use in percent."""
    cpu = memory = disk = 0.0
    try:
        root = os.environ.get("SystemDrive", "C:") + "\\" if SYSTEM == "Windows" else "/"
        usage = shutil.disk_usage(root)
        disk = usage.used * 100.0 / usage.total
    except Exception:
        pass
    if psutil:
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
        except Exception:
            pass
        return cpu, memory, disk
    try:
        if SYSTEM == "Linux":
            total_a, idle_a = read_cpu_times()
            time.sleep(1)
            total_b, idle_b = read_cpu_times()
            cpu = 100.0 * (1 - (idle_b - idle_a) / max(1, total_b - total_a))
            info = {}
            for line in open("/proc/meminfo", encoding="utf-8"):
                key, value = line.split(":", 1)
                info[key] = int(value.split()[0])
            memory = 100.0 * (1 - info.get("MemAvailable", 0) / max(1, info.get("MemTotal", 1)))
        elif SYSTEM == "Darwin":
            code, text = run(["top", "-l", "2", "-n", "0", "-s", "1"], 20)
            match = re.findall(r"CPU usage:\s*([\d.]+)% user,\s*([\d.]+)% sys", text)
            if match:
                cpu = float(match[-1][0]) + float(match[-1][1])
            code, total = run(["sysctl", "-n", "hw.memsize"], 5)
            code, vm = run(["vm_stat"], 5)
            page = int(re.search(r"page size of (\d+)", vm).group(1)) if re.search(r"page size of (\d+)", vm) else 4096
            free = sum(int(re.search(name + r":\s+(\d+)", vm).group(1)) for name in ("Pages free", "Pages inactive", "Pages speculative")
                       if re.search(name + r":\s+(\d+)", vm))
            memory = 100.0 * (1 - free * page / max(1, int(total)))
    except Exception:
        pass
    return max(0.0, min(100.0, cpu)), max(0.0, min(100.0, memory)), disk


# ------------------------------------------------------------------ security status ("posture")
def days_since(timestamp):
    return max(0, int((time.time() - timestamp) / 86400))


def windows_posture(state, slow):
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$r = @{}
try { $s = Get-MpComputerStatus -ErrorAction Stop
  $r.av = @{ on = [bool]($s.AntivirusEnabled -and $s.RealTimeProtectionEnabled); sig = [int]$s.AntivirusSignatureAge; scan = [double]$s.QuickScanAge } } catch {}
try { $r.other = (Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -ErrorAction Stop |
  Where-Object { $_.displayName -notlike '*Defender*' } | Select-Object -First 1).displayName } catch {}
try { $r.th_total = @(Get-MpThreatDetection -ErrorAction Stop).Count } catch {}
try { $r.th_active = @(Get-MpThreat -ErrorAction Stop | Where-Object { $_.IsActive }).Count } catch {}
try { $r.fw = @(Get-NetFirewallProfile -ErrorAction Stop | ForEach-Object { [bool]$_.Enabled }) } catch {}
try { $r.bl = [int](Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop).ProtectionStatus } catch {}
try { $r.np = [int](Get-MpPreference -ErrorAction Stop).EnableNetworkProtection } catch {}
try { $h = Get-HotFix | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending | Select-Object -First 1
  if ($h) { $r.last_update_days = [int]((Get-Date) - $h.InstalledOn).TotalDays } } catch {}
$r.reboot = [bool]((Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or
  (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'))
try { $r.usb = [int](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -ErrorAction Stop).Start } catch {}
$r | ConvertTo-Json -Compress
"""
    code, text = powershell(script, 90)
    try:
        raw = json.loads(text[text.index("{"):])
    except Exception:
        raw = {}
    posture = {}
    av = raw.get("av")
    other = raw.get("other")
    defender = {"state": "unknown"}
    if av and av.get("on"):
        defender["state"] = "on"
    elif other:
        defender.update(state="other", other_av=other)
    elif av:
        defender["state"] = "off"
    if av:
        if av.get("sig") is not None and av["sig"] < 100000:
            defender["definitions_age_days"] = av["sig"]
        if av.get("scan") is not None and av["scan"] < 100000:
            defender["quick_scan_age_days"] = int(av["scan"])
    if raw.get("th_active") is not None:
        defender["threats_active"] = raw["th_active"]
    if raw.get("th_total") is not None:
        defender["threats_total"] = raw["th_total"]
    posture["defender"] = defender
    fw = raw.get("fw")
    if isinstance(fw, bool):
        fw = [fw]
    posture["firewall"] = "unknown" if not fw else "on" if all(fw) else "partial" if any(fw) else "off"
    posture["disk_encryption"] = {1: "on", 0: "off"}.get(raw.get("bl"), "unknown")
    posture["web_protection"] = {1: "on", 2: "audit", 0: "off"}.get(raw.get("np"), "unknown")
    updates = {"reboot_required": bool(raw.get("reboot"))}
    if raw.get("last_update_days") is not None:
        updates["last_update_days"] = raw["last_update_days"]
    updates["pending"] = state.get("pending_updates") if state.get("pending_updates") is not None else None
    posture["updates"] = {k: v for k, v in updates.items() if v is not None}
    posture["usb_storage"] = "blocked" if raw.get("usb") == 4 else "allowed" if raw.get("usb") in (3, 0, 1, 2) else "unknown"
    posture["signin_monitoring"] = "ok" if is_admin() else "needs_admin"
    return posture


def windows_pending_updates():
    code, text = powershell(
        "try { $s = New-Object -ComObject Microsoft.Update.Session; $q = $s.CreateUpdateSearcher().Search('IsInstalled=0 and IsHidden=0');"
        " $q.Updates.Count } catch { 'x' }", 150)
    try:
        return int(text.strip().splitlines()[-1])
    except Exception:
        return None


def mac_posture(state, slow):
    posture = {"defender": {"state": "other", "other_av": "macOS XProtect (built in)"}}
    code, text = run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"], 10)
    posture["firewall"] = "on" if "enabled" in text.lower() else "off" if code == 0 else "unknown"
    code, text = run(["fdesetup", "status"], 10)
    posture["disk_encryption"] = "on" if "is on" in text.lower() else "off" if "is off" in text.lower() else "unknown"
    posture["web_protection"] = "unknown"
    updates = {}
    if state.get("pending_updates") is not None:
        updates["pending"] = state["pending_updates"]
    posture["updates"] = updates
    posture["usb_storage"] = "unknown"
    posture["signin_monitoring"] = "unavailable"
    add_scan_info(posture, state)
    return posture


def mac_pending_updates():
    code, text = run(["softwareupdate", "-l"], 180)
    if code != 0 and "No new software" not in text:
        return None
    return len(re.findall(r"^\s*\*\s", text, re.M))


def linux_posture(state, slow):
    posture = {}
    clam = shutil.which("clamscan")
    defender = {"state": "other", "other_av": "ClamAV"} if clam else {"state": "unknown"}
    for path in ("/var/lib/clamav/daily.cvd", "/var/lib/clamav/daily.cld"):
        if clam and os.path.exists(path):
            defender["definitions_age_days"] = days_since(os.path.getmtime(path))
            break
    posture["defender"] = defender
    firewall = "unknown"
    if shutil.which("ufw"):
        code, text = run(["ufw", "status"], 10)
        firewall = "on" if "Status: active" in text else "off" if code == 0 else "unknown"
    elif shutil.which("firewall-cmd"):
        code, text = run(["firewall-cmd", "--state"], 10)
        firewall = "on" if text.strip() == "running" else "off"
    elif shutil.which("iptables"):
        code, text = run(["iptables", "-S"], 10)
        if code == 0:
            firewall = "on" if ("-P INPUT DROP" in text or len([l for l in text.splitlines() if l.startswith("-A")]) > 0) else "off"
    posture["firewall"] = firewall
    code, text = run(["lsblk", "-rno", "TYPE"], 10)
    posture["disk_encryption"] = ("on" if "crypt" in text.split() else "off") if code == 0 else "unknown"
    posture["web_protection"] = "unknown"
    updates = {"reboot_required": os.path.exists("/var/run/reboot-required")}
    if state.get("pending_updates") is not None:
        updates["pending"] = state["pending_updates"]
    for path in ("/var/log/apt/history.log", "/var/log/dnf.log", "/var/log/yum.log", "/var/log/pacman.log"):
        if os.path.exists(path):
            updates["last_update_days"] = days_since(os.path.getmtime(path))
            break
    posture["updates"] = updates
    posture["usb_storage"] = "blocked" if os.path.exists("/etc/modprobe.d/mellowtech-usb.conf") else "allowed"
    posture["signin_monitoring"] = "ok" if (os.path.exists("/var/log/auth.log") or os.path.exists("/var/log/secure")
                                           or shutil.which("journalctl")) and is_admin() else "needs_admin"
    add_scan_info(posture, state)
    return posture


def linux_pending_updates():
    if shutil.which("apt-get"):
        code, text = run(["apt-get", "-s", "upgrade"], 120)
        return len(re.findall(r"^Inst ", text, re.M)) if code == 0 else None
    if shutil.which("dnf"):
        code, text = run(["dnf", "-q", "check-update"], 180)
        if code == 0:
            return 0
        return len([l for l in text.splitlines() if l.strip() and not l.startswith(" ") and "." in l.split()[0]]) if code == 100 else None
    return None


def add_scan_info(posture, state):
    if state.get("last_scan"):
        posture["defender"]["quick_scan_age_days"] = days_since(state["last_scan"])
    posture["defender"]["threats_active"] = int(state.get("threats_found") or 0)


def collect_posture(state):
    """Posture is rebuilt every 5 minutes; the slow 'pending updates' count only every 6 hours."""
    if state.get("pending_checked", 0) < time.time() - 6 * 3600:
        counter = {"windows": windows_pending_updates, "macos": mac_pending_updates, "linux": linux_pending_updates}.get(FAMILY)
        if counter:
            try:
                state["pending_updates"] = counter()
            except Exception:
                state["pending_updates"] = None
        state["pending_checked"] = time.time()
    builder = {"windows": windows_posture, "macos": mac_posture, "linux": linux_posture}.get(FAMILY)
    posture = builder(state, False) if builder else {"platform": FAMILY}
    posture["os_family"] = FAMILY
    posture["isolated"] = bool(state.get("isolated_until"))
    return posture


# ------------------------------------------------------------------ alerts: repeated failed sign-ins
def failed_signins(minutes=10):
    """Returns {ip: count} for failed sign-in attempts in the last few minutes."""
    found = {}
    try:
        if SYSTEM == "Windows":
            query = f"*[System[(EventID=4625) and TimeCreated[timediff(@SystemTime) <= {minutes * 60000}]]]"
            code, text = run(["wevtutil", "qe", "Security", "/q:" + query, "/f:xml", "/c:300"], 40)
            for ip in re.findall(r"<Data Name='IpAddress'>([^<]+)</Data>", text):
                if valid_ip(ip) and ip not in ("127.0.0.1", "::1"):
                    found[ip] = found.get(ip, 0) + 1
        elif SYSTEM == "Linux":
            lines = ""
            if shutil.which("journalctl"):
                code, lines = run(["journalctl", "--since", f"{minutes} minutes ago", "--no-pager", "-q"], 30)
            for path in ("/var/log/auth.log", "/var/log/secure"):
                if not lines.strip() and os.path.exists(path):
                    lines = "".join(open(path, encoding="utf-8", errors="replace").readlines()[-800:])
            for ip in re.findall(r"Failed password .* from (\S+)", lines):
                if valid_ip(ip):
                    found[ip] = found.get(ip, 0) + 1
    except Exception:
        pass
    return found


def make_alerts(state):
    alerts = []
    seen = state.setdefault("alerted", {})
    for ip, count in failed_signins().items():
        if count >= 5 and seen.get(ip, 0) < time.time() - 600:
            seen[ip] = time.time()
            alerts.append({"type": "Repeated failed sign-ins", "severity": "High" if count >= 20 else "Medium",
                           "description": f"{count} failed sign-in attempts from {ip} in the last 10 minutes.", "source_ip": ip})
    for ip in [k for k, v in seen.items() if v < time.time() - 3600]:
        del seen[ip]
    return alerts


# ------------------------------------------------------------------ actions the dashboard can send
def server_addresses(server):
    host = urllib.parse.urlparse(server).hostname or ""
    found = set()
    try:
        for item in socket.getaddrinfo(host, None):
            ip = valid_ip(item[4][0])
            if ip:
                found.add(ip)
    except Exception:
        pass
    return sorted(found)


def need_admin():
    if not is_admin():
        raise RuntimeError("The agent needs administrator rights to do this.")


def block_ip(ip, on):
    ip = valid_ip(ip)
    if not ip:
        raise RuntimeError("That is not a valid address.")
    need_admin()
    if SYSTEM == "Windows":
        name = "MellowTech block " + ip
        run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"], 30)
        if on:
            for direction in ("in", "out"):
                code, text = run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", f"dir={direction}",
                                  "action=block", f"remoteip={ip}"], 30)
                if code != 0:
                    raise RuntimeError("Windows Firewall refused: " + text[:150])
    elif SYSTEM == "Linux":
        tool = "ip6tables" if ":" in ip else "iptables"
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} is not installed on this computer.")
        run([tool, "-N", "MELLOWTECH"], 10)
        for parent in ("INPUT", "OUTPUT"):
            if run([tool, "-C", parent, "-j", "MELLOWTECH"], 10)[0] != 0:
                run([tool, "-I", parent, "1", "-j", "MELLOWTECH"], 10)
        for flag, direction in (("-s", "INPUT"), ("-d", "OUTPUT")):
            while run([tool, "-D", "MELLOWTECH", flag, ip, "-j", "DROP"], 10)[0] == 0:
                pass
        if on:
            for flag in ("-s", "-d"):
                code, text = run([tool, "-A", "MELLOWTECH", flag, ip, "-j", "DROP"], 10)
                if code != 0:
                    raise RuntimeError("The firewall refused: " + text[:150])
    elif SYSTEM == "Darwin":
        apply_mac_pf()
    else:
        raise RuntimeError("Blocking is not supported on this system.")


def apply_mac_pf(isolate_ips=None):
    """macOS: one pf anchor (com.apple/mellowtech) holds every rule we add. Apple's default rules already read it."""
    state = load_state()
    rules = []
    if isolate_ips is not None:
        for ip in isolate_ips:
            rules.append(f"pass out quick to {ip}")
            rules.append(f"pass in quick from {ip}")
        rules += ["pass out quick proto { udp tcp } to any port 53", "block drop quick all"]
    for ip in state["blocks"]:
        rules += [f"block drop quick from {ip} to any", f"block drop quick from any to {ip}"]
    path = os.path.join(DATA_DIR, "pf-mellowtech.conf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rules) + "\n")
    run(["pfctl", "-E"], 10)
    code, text = run(["pfctl", "-a", "com.apple/mellowtech", "-f", path], 20)
    if code != 0:
        raise RuntimeError("pf refused the rules: " + text[:150])


def isolate(minutes, server):
    need_admin()
    addresses = server_addresses(server)
    if not addresses:
        raise RuntimeError("Could not find the server's address, so isolating would cut this computer off for good.")
    state = load_state()
    if SYSTEM == "Windows":
        run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=MellowTech isolate"], 30)
        for direction in ("in", "out"):
            run(["netsh", "advfirewall", "firewall", "add", "rule", "name=MellowTech isolate", f"dir={direction}", "action=allow",
                 "remoteip=" + ",".join(addresses)], 30)
        run(["netsh", "advfirewall", "firewall", "add", "rule", "name=MellowTech isolate", "dir=out", "action=allow",
             "protocol=UDP", "remoteport=53"], 30)
        code, text = run(["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,blockoutbound"], 30)
        if code != 0:
            raise RuntimeError("Windows Firewall refused: " + text[:150])
    elif SYSTEM == "Linux":
        tool = "iptables"
        if not shutil.which(tool):
            raise RuntimeError("iptables is not installed on this computer.")
        release_isolation_linux()
        run([tool, "-N", "MELLOWTECH_ISOLATE"], 10)
        rules = [["-i", "lo", "-j", "ACCEPT"], ["-o", "lo", "-j", "ACCEPT"],
                 ["-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
                 ["-p", "udp", "--dport", "53", "-j", "ACCEPT"], ["-p", "tcp", "--dport", "53", "-j", "ACCEPT"]]
        for ip in addresses:
            if ":" not in ip:
                rules += [["-d", ip, "-j", "ACCEPT"], ["-s", ip, "-j", "ACCEPT"]]
        rules.append(["-j", "DROP"])
        for rule in rules:
            run([tool, "-A", "MELLOWTECH_ISOLATE"] + rule, 10)
        for parent in ("INPUT", "OUTPUT"):
            run([tool, "-I", parent, "1", "-j", "MELLOWTECH_ISOLATE"], 10)
    elif SYSTEM == "Darwin":
        apply_mac_pf([ip for ip in addresses if ":" not in ip])
    else:
        raise RuntimeError("Isolating is not supported on this system.")
    state["isolated_until"] = time.time() + 60 * int(minutes or 60)
    save_state(state)


def release_isolation_linux():
    for parent in ("INPUT", "OUTPUT"):
        while run(["iptables", "-D", parent, "-j", "MELLOWTECH_ISOLATE"], 10)[0] == 0:
            pass
    run(["iptables", "-F", "MELLOWTECH_ISOLATE"], 10)
    run(["iptables", "-X", "MELLOWTECH_ISOLATE"], 10)


def release():
    need_admin()
    state = load_state()
    if SYSTEM == "Windows":
        run(["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,allowoutbound"], 30)
        run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=MellowTech isolate"], 30)
    elif SYSTEM == "Linux":
        release_isolation_linux()
    elif SYSTEM == "Darwin":
        apply_mac_pf()
    state["isolated_until"] = None
    save_state(state)


def usb(block):
    need_admin()
    if SYSTEM == "Windows":
        code, text = powershell(
            "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR' -Name Start -Value %d -ErrorAction Stop" % (4 if block else 3), 30)
        if code != 0:
            raise RuntimeError("Windows refused: " + text[:150])
    elif SYSTEM == "Linux":
        path = "/etc/modprobe.d/mellowtech-usb.conf"
        if block:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("blacklist usb-storage\ninstall usb-storage /bin/false\n")
            run(["modprobe", "-r", "usb_storage"], 20)
        elif os.path.exists(path):
            os.remove(path)
    else:
        raise RuntimeError("Blocking USB storage is not supported on a Mac yet.")


def scan(state):
    need_admin()
    if SYSTEM == "Windows":
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Start-MpScan -ScanType QuickScan"],
                         creationflags=NO_WINDOW)
        state["last_scan"] = time.time()
        return "Virus scan started with Microsoft Defender."
    clam = shutil.which("clamscan")
    if not clam:
        hint = "brew install clamav" if SYSTEM == "Darwin" else "sudo apt install clamav (or: sudo dnf install clamav)"
        raise RuntimeError("Virus scanning needs ClamAV, which is not installed here. Install it with: " + hint)
    folders = [p for p in (["/Users", "/tmp"] if SYSTEM == "Darwin" else ["/home", "/tmp", "/var/tmp"]) if os.path.isdir(p)]
    code, text = run([clam, "-r", "--infected", "--no-summary", "--max-filesize=50M"] + folders, 1500)
    state["last_scan"] = time.time()
    if code == 1:
        found = [line for line in text.splitlines() if line.endswith("FOUND")]
        state["threats_found"] = len(found)
        raise RuntimeError(f"Scan finished: {len(found)} infected file(s) found, for example " + "; ".join(found[:2])[:200])
    if code not in (0, 1):
        raise RuntimeError("The scan could not finish: " + text[-150:])
    state["threats_found"] = 0
    return "Scan finished. No threats found."


def update_protection():
    need_admin()
    if SYSTEM == "Windows":
        code, text = powershell("Update-MpSignature -ErrorAction Stop", 300)
        if code != 0:
            raise RuntimeError("Could not update Defender: " + text[:150])
        return "Defender definitions updated."
    fresh = shutil.which("freshclam")
    if not fresh:
        raise RuntimeError("Protection updates need ClamAV (freshclam), which is not installed here.")
    code, text = run([fresh], 300)
    if code != 0:
        raise RuntimeError("freshclam failed: " + text[-150:])
    return "Virus definitions updated."


def do_command(command, config, state):
    action, ip, param = command.get("action"), command.get("ip"), command.get("param")
    if action == "block":
        ip = valid_ip(ip)
        if not ip:
            raise RuntimeError("Invalid address.")
        state["blocks"][ip] = True
        save_state(state)
        block_ip(ip, True)
        return f"Blocked {ip}."
    if action == "unblock":
        ip = valid_ip(ip)
        state["blocks"].pop(ip or "", None)
        save_state(state)
        if ip:
            block_ip(ip, False)
        return f"Unblocked {ip}."
    if action == "scan":
        return scan(state)
    if action == "update_protection":
        return update_protection()
    if action == "isolate":
        isolate(param, config["server"])
        return f"Isolated for {param or 60} minutes."
    if action == "release":
        release()
        return "Released. Normal network access is back."
    if action == "usb_block":
        usb(True)
        return "USB storage blocked."
    if action == "usb_allow":
        usb(False)
        return "USB storage allowed."
    raise RuntimeError("Unknown action: " + str(action))


def save_state(state):
    keep = {k: state.get(k) for k in ("blocks", "isolated_until", "last_scan", "threats_found", "pending_updates",
                                      "pending_checked", "alerted")}
    write_json(STATE_FILE, keep)


def reapply(state):
    """After a restart: put saved blocks back, and end an isolation whose time has run out."""
    try:
        for ip in list(state["blocks"]):
            block_ip(ip, True)
    except Exception as exc:
        log("Could not re-apply blocks:", exc)
    if state.get("isolated_until") and state["isolated_until"] < time.time():
        try:
            release()
        except Exception as exc:
            log("Could not end isolation:", exc)


# ------------------------------------------------------------------ the main loop
def heartbeat(config, state, posture, alerts):
    cpu, memory, disk = metrics()
    body = {"name": socket.gethostname(), "os": os_label(), "ip": local_ip(), "cpu": cpu, "memory": memory, "disk": disk,
            "version": VERSION, "posture": posture, "alerts": alerts}
    return call(config["server"], "/api/agent/heartbeat", body, config["token"])


def acknowledge(config, results):
    if results:
        call(config["server"], "/api/agent/ack", {"results": results}, config["token"])


def loop(once=False):
    config = read_json(CONFIG_FILE, None)
    if not config:
        sys.exit("This computer is not connected yet. Run the install command first.")
    state = load_state()
    reapply(state)
    posture, posture_at, interval, gone = None, 0, 15, 0
    while True:
        try:
            if state.get("isolated_until") and state["isolated_until"] < time.time():
                release()
                posture_at = 0
            if posture is None or time.time() - posture_at > 300:
                posture, posture_at = collect_posture(state), time.time()
                save_state(state)
            reply = heartbeat(config, state, posture, make_alerts(state))
            gone = 0
            interval = max(5, int(reply.get("interval") or 15))
            results = []
            for command in reply.get("commands") or []:
                try:
                    message = do_command(command, config, state)
                    results.append({"id": command["id"], "ok": True, "message": message})
                except Exception as exc:
                    results.append({"id": command["id"], "ok": False, "message": str(exc)[:280]})
                log("command", command.get("action"), "->", results[-1]["message"])
                posture_at = 0                      # show the effect on the next report
            acknowledge(config, results)
            save_state(state)
        except Gone as exc:
            gone += 1
            log("The server does not know this computer:", exc)
            if gone >= 3:
                log("This computer was removed in the dashboard. Disconnecting.")
                uninstall(quiet=True)
                return
        except Exception as exc:
            log("Could not reach the server, will retry:", exc)
            interval = min(120, max(interval, 15) * 2)
        if once:
            return
        time.sleep(interval)


# ------------------------------------------------------------------ install and remove
def program_command():
    """The command that starts the agent: the .exe itself, or python plus this script."""
    if FROZEN:
        return [os.path.join(PROGRAM_DIR, os.path.basename(sys.executable))]
    return [sys.executable, os.path.join(PROGRAM_DIR, "mellowtech_agent.py")]


def copy_program():
    os.makedirs(PROGRAM_DIR, exist_ok=True)
    source = sys.executable if FROZEN else os.path.abspath(__file__)
    target = program_command()[-1]
    if os.path.abspath(source) != os.path.abspath(target):
        shutil.copy2(source, target)


def register_autostart():
    cmd = program_command() + ["run"]
    if SYSTEM == "Windows":
        text = " ".join('"%s"' % part for part in cmd)
        code, out = run(["schtasks", "/Create", "/TN", SERVICE_NAME, "/TR", text, "/SC", "ONSTART", "/RU", "SYSTEM",
                         "/RL", "HIGHEST", "/F"], 60)
        if code != 0:
            raise RuntimeError("Could not set up automatic start: " + out[:200])
        run(["schtasks", "/Run", "/TN", SERVICE_NAME], 30)
    elif SYSTEM == "Darwin":
        plist = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
                 "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n<plist version=\"1.0\"><dict>\n"
                 "<key>Label</key><string>com.mellowtech.agent</string>\n<key>ProgramArguments</key><array>"
                 + "".join("<string>%s</string>" % part for part in cmd) +
                 "</array>\n<key>RunAtLoad</key><true/>\n<key>KeepAlive</key><true/>\n"
                 "<key>StandardOutPath</key><string>/var/log/mellowtech-agent.log</string>\n"
                 "<key>StandardErrorPath</key><string>/var/log/mellowtech-agent.log</string>\n</dict></plist>\n")
        path = "/Library/LaunchDaemons/com.mellowtech.agent.plist"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(plist)
        os.chmod(path, 0o644)
        run(["launchctl", "bootout", "system/com.mellowtech.agent"], 20)
        code, out = run(["launchctl", "bootstrap", "system", path], 30)
        if code != 0:
            code, out = run(["launchctl", "load", "-w", path], 30)
            if code != 0:
                raise RuntimeError("Could not set up automatic start: " + out[:200])
    else:
        unit = ("[Unit]\nDescription=MellowTech Agent\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\n"
                "ExecStart=" + " ".join(cmd) + "\nRestart=always\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target\n")
        with open("/etc/systemd/system/mellowtech-agent.service", "w", encoding="utf-8") as handle:
            handle.write(unit)
        run(["systemctl", "daemon-reload"], 30)
        code, out = run(["systemctl", "enable", "--now", "mellowtech-agent"], 60)
        if code != 0:
            raise RuntimeError("Could not set up automatic start: " + out[:200])


def install(server, key, service=True):
    if not is_admin():
        sys.exit("Please run this as Administrator." if SYSTEM == "Windows" else "Please run this with sudo.")
    server = server.rstrip("/")
    log("Connecting to", server)
    try:
        reply = call(server, "/api/agent/enroll", {"key": key, "name": socket.gethostname(), "os": os_label()})
    except Exception as exc:
        sys.exit("Could not connect: " + str(exc))
    write_json(CONFIG_FILE, {"server": server, "token": reply["token"], "device_id": reply.get("device_id")}, secret=True)
    if service:
        copy_program()
        register_autostart()
        log("Installed. This computer will show up in your dashboard within a minute.")
    else:
        log("Connected. Start it with:  python mellowtech_agent.py run")


def uninstall(quiet=False):
    try:
        if SYSTEM == "Windows":
            run(["schtasks", "/End", "/TN", SERVICE_NAME], 30)
            run(["schtasks", "/Delete", "/TN", SERVICE_NAME, "/F"], 30)
        elif SYSTEM == "Darwin":
            run(["launchctl", "bootout", "system/com.mellowtech.agent"], 20)
            if os.path.exists("/Library/LaunchDaemons/com.mellowtech.agent.plist"):
                os.remove("/Library/LaunchDaemons/com.mellowtech.agent.plist")
        else:
            run(["systemctl", "disable", "--now", "mellowtech-agent"], 30)
            if os.path.exists("/etc/systemd/system/mellowtech-agent.service"):
                os.remove("/etc/systemd/system/mellowtech-agent.service")
            run(["systemctl", "daemon-reload"], 30)
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
    except Exception as exc:
        log("Could not remove everything:", exc)
    if not quiet:
        log("MellowTech Agent removed from this computer.")


def status():
    config = read_json(CONFIG_FILE, None)
    print("MellowTech Agent", VERSION, "on", os_label())
    print("Connected to:", config["server"] if config else "nothing (not installed)")
    if config:
        print(json.dumps(collect_posture(load_state()), indent=2))


def main():
    parser = argparse.ArgumentParser(description="MellowTech Agent")
    sub = parser.add_subparsers(dest="cmd")
    inst = sub.add_parser("install")
    inst.add_argument("--server", required=True)
    inst.add_argument("--key", required=True)
    inst.add_argument("--no-service", action="store_true", help="connect only; do not set up automatic start")
    sub.add_parser("uninstall")
    sub.add_parser("status")
    runner = sub.add_parser("run")
    runner.add_argument("--once", action="store_true", help="send one report and stop")
    args = parser.parse_args()
    if args.cmd == "install":
        install(args.server, args.key, not args.no_service)
    elif args.cmd == "uninstall":
        uninstall()
    elif args.cmd == "status":
        status()
    elif args.cmd == "run":
        loop(args.once)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()