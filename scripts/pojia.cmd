@echo off
REM ===========================================================
REM  Launch Codex with the "pojia" instruction layer.
REM  Mechanism: codex -p pojia  loads  %USERPROFILE%\.codex\pojia.config.toml
REM  Rollback : close this window. The main config.toml is never modified.
REM ===========================================================
setlocal

if not defined CODEX_HOME set "CODEX_HOME=%USERPROFILE%\.codex"

REM --- locate codex.exe ---
REM 1) explicit override
REM 2) on PATH
REM 3) the standard per-user install path (hash dir varies by version)
set "CODEX_EXE=%CODEX_EXE_OVERRIDE%"
if defined CODEX_EXE goto found

for %%I in (codex.exe) do if not "%%~$PATH:I"=="" set "CODEX_EXE=%%~$PATH:I"
if defined CODEX_EXE goto found

for /d %%D in ("%LOCALAPPDATA%\OpenAI\Codex\bin\*") do (
  if exist "%%D\codex.exe" set "CODEX_EXE=%%D\codex.exe"
)
if defined CODEX_EXE goto found

echo [x] codex.exe not found.
echo     Set CODEX_EXE_OVERRIDE to its full path, or put codex on PATH.
pause
exit /b 1

:found
if not exist "%CODEX_HOME%\pojia.config.toml" (
  echo [x] profile layer missing: %CODEX_HOME%\pojia.config.toml
  echo     Run: python install.py
  pause
  exit /b 1
)

REM Extra args are forwarded to codex as-is.
REM Example:  pojia.cmd exec "write a port scanner"
"%CODEX_EXE%" -p pojia %*
endlocal
