# MellowTech: start the server so it works over ngrok, including sending real emails to any address.
# Put this file in the backend folder (next to app.py). Keep ngrok running in its own window first.

Set-Location $PSScriptRoot

# 1. find the ngrok address automatically
$tunnel = $null
try {
    $tunnel = (Invoke-RestMethod http://127.0.0.1:4040/api/tunnels).tunnels |
        Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
} catch { }
if (-not $tunnel) {
    Write-Host "ngrok is not running. Open another PowerShell window, run:  ngrok http 5000   then run this script again." -ForegroundColor Red
    exit 1
}
$env:MELLOWTECH_BASE_URL = $tunnel.public_url.TrimEnd("/")
Write-Host "Site address: $($env:MELLOWTECH_BASE_URL)" -ForegroundColor Green

# 2. email account used to send confirmation links
$gmail = Read-Host "Gmail address that will SEND the emails"
$secure = Read-Host "Gmail App password (16 letters; spaces are fine)" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = $gmail.Trim()
$env:SMTP_FROM = $gmail.Trim()
$env:SMTP_PASSWORD = ($plain -replace "\s", "")

# 3. check the email login works before starting
Write-Host "Sending a test email to $gmail ..."
python app.py test-email $gmail.Trim()
Write-Host ""
Write-Host "If the test email arrived, all good. If it printed an error, press Ctrl+C and send me the error." -ForegroundColor Yellow
Write-Host ""

# 4. start the server
python app.py