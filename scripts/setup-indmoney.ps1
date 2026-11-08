# Create a local encryption key without displaying it or replacing existing settings.
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $projectDirectory '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath (Join-Path $projectDirectory '.env.example') -Destination $environmentPath
}
$environmentText = [System.IO.File]::ReadAllText($environmentPath)
if ($environmentText -notmatch '(?m)^INDMONEY_TOKEN_KEY=.+\S\r?$') {
    $keyBytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($keyBytes) } finally { $generator.Dispose() }
    $tokenKey = [Convert]::ToBase64String($keyBytes).Replace('+', '-').Replace('/', '_')
    if ($environmentText -match '(?m)^INDMONEY_TOKEN_KEY=.*$') {
        $environmentText = [regex]::Replace($environmentText, '(?m)^INDMONEY_TOKEN_KEY=.*$', "INDMONEY_TOKEN_KEY=$tokenKey")
    } else {
        $environmentText += "`r`nINDMONEY_TOKEN_KEY=$tokenKey`r`n"
    }
    [System.IO.File]::WriteAllText($environmentPath, $environmentText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output 'Created the private INDmoney encryption key in .env.'
} else {
    Write-Output 'Kept the existing INDmoney encryption key.'
}
