# 在当前 PowerShell 会话设置长桥凭证（示例）
# 请把下面三行替换为你在长桥开发者中心拿到的真实值

$env:LONGPORT_APP_KEY = "your_app_key"
$env:LONGPORT_APP_SECRET = "your_app_secret"
$env:LONGPORT_ACCESS_TOKEN = "your_access_token"

Write-Host "LONGPORT 环境变量已设置（当前会话）"
