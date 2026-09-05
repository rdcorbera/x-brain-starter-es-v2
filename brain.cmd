@echo off
rem X-Brain launcher for cmd.exe and PowerShell. The sh version is `brain`,
rem and it is the one CI exercises (Git Bash on windows-latest).
rem
rem `py` first: it is the Windows launcher (PEP 397), it lives in C:\Windows,
rem and it works even when Python was installed without adding it to PATH.
rem `python3` is NOT tried here on purpose -- the python.org installer never
rem creates it, and Windows 10+ aliases that name to a Microsoft Store stub
rem that opens a store instead of failing.
rem
rem A first argument ending in .py runs that script instead of brain.py,
rem because every other script here has the same problem.
setlocal EnableDelayedExpansion
set "SCRIPT=%~dp0kernel\bin\brain.py"
if /i "%~x1"==".py" goto :ownscript
goto :collect

:ownscript
set "SCRIPT=%~f1"
shift

rem `%*` ignores `shift`, so the arguments are rebuilt one by one. Each is
rem re-quoted, which is what survives a path with spaces.
:collect
set "ARGS="
:next
if "%~1"=="" goto :run
set "ARGS=!ARGS! "%~1""
shift
goto :next

:run
py -3 -c "" >nul 2>&1
if not errorlevel 1 (
    py -3 "%SCRIPT%" !ARGS!
    exit /b !errorlevel!
)

where python >nul 2>&1
if not errorlevel 1 (
    python "%SCRIPT%" !ARGS!
    exit /b !errorlevel!
)

echo brain: no encuentro un Python. Hace falta 3.11 o superior.>&2
echo        winget install Python.Python.3.14>&2
exit /b 1
