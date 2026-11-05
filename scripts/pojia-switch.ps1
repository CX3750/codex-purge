# pojia-switch.ps1
# Toggle the jailbreak prompt for the DESKTOP app (which does not accept -p).
# Only one line of config.toml is rewritten; everything else is untouched.
#
#   .\pojia-switch.ps1 -On       point model_instructions_file at the jailbreak prompt
#   .\pojia-switch.ps1 -Off      point it back at the original value
#   .\pojia-switch.ps1 -Status   show current state

param(
    [switch]$On,
    [switch]$Off,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'

$cfg     = Join-Path $env:USERPROFILE '.codex\config.toml'
$stage   = Join-Path $env:USERPROFILE '.codex\pojia'
$prompt  = Join-Path $stage 'codex-base.md'
$stateFn = Join-Path $stage 'desktop-switch.json'
$bakDir  = Join-Path $stage 'desktop-backup'

function Get-InstrLine {
    foreach ($l in Get-Content $cfg) {
        if ($l -match '^\s*model_instructions_file\s*=\s*(.+?)\s*$') {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Set-InstrLine([string]$value) {
    $lines = @(Get-Content $cfg)
    $hit = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*model_instructions_file\s*=') {
            $lines[$i] = 'model_instructions_file = ' + $value
            $hit = $true
        }
    }
    if (-not $hit) { throw 'model_instructions_file line not found in config.toml' }
    Set-Content -Path $cfg -Value $lines -Encoding UTF8
}

if ($Status -or (-not $On -and -not $Off)) {
    $cur = Get-InstrLine
    Write-Host "config.toml : $cfg"
    Write-Host "current     : $cur"
    if (Test-Path $stateFn) {
        Write-Host "--- desktop-switch.json ---"
        Get-Content $stateFn -Raw
    }
    if ($cur -and $cur -match 'pojia') {
        Write-Host ">>> JAILBREAK ON" -ForegroundColor Green
    } else {
        Write-Host ">>> JAILBREAK OFF" -ForegroundColor Yellow
    }
    return
}

if (-not (Test-Path $prompt)) {
    Write-Host "[x] prompt missing: $prompt" -ForegroundColor Red
    Write-Host "    run: python `"$stage\install.py`"" -ForegroundColor Red
    return
}

$old = Get-InstrLine
if (-not $old) {
    Write-Host "[x] no model_instructions_file line to anchor on" -ForegroundColor Red
    return
}

if (-not (Test-Path $bakDir)) { New-Item -ItemType Directory -Force -Path $bakDir | Out-Null }

# Back up the main config once, never overwrite an existing backup
if (-not (Test-Path $stateFn)) {
    $bak = Join-Path $bakDir ("config.toml.before-pojia-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Copy-Item $cfg $bak -Force
    [ordered]@{
        original   = $old
        backup     = $bak
        touched_at = (Get-Date).ToString('s')
    } | ConvertTo-Json | Set-Content $stateFn -Encoding UTF8
    Write-Host "[bak] $bak"
}

if ($On) {
    if ($old -match 'pojia') {
        Write-Host "already on" -ForegroundColor Yellow
        return
    }
    $newVal = '"' + ($prompt -replace '\\', '/') + '"'
    Set-InstrLine $newVal
    Write-Host "[ok] JAILBREAK ON  (restart the desktop app)" -ForegroundColor Green
    Write-Host "     $old"
    Write-Host "  -> $newVal"
}
elseif ($Off) {
    $orig = $old
    if (Test-Path $stateFn) {
        $st = Get-Content $stateFn -Raw | ConvertFrom-Json
        if ($st.original) { $orig = $st.original }
    }
    if ($orig -match 'pojia') {
        Write-Host "[x] cannot determine original value; edit manually: $cfg" -ForegroundColor Red
        return
    }
    Set-InstrLine $orig
    Write-Host "[ok] restored  (restart the desktop app)" -ForegroundColor Green
    Write-Host "     $old"
    Write-Host "  -> $orig"
}
