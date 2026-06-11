@echo off
rem bootstrap.bat — Windows entry point for Project R.E.M. setup
rem
rem Requires Git Bash. If you don't have it, install Git for Windows:
rem   https://git-scm.com/download/win
rem
rem This script locates Git Bash and delegates to bootstrap.sh.

setlocal

set BASH_CANDIDATES=^
    "C:\Program Files\Git\bin\bash.exe" ^
    "C:\Program Files (x86)\Git\bin\bash.exe"

set BASH=

for %%b in (%BASH_CANDIDATES%) do (
    if exist %%b (
        set BASH=%%b
        goto :found
    )
)

echo.
echo  Git Bash not found. Please install Git for Windows:
echo    https://git-scm.com/download/win
echo.
echo  Alternatively, run in WSL:
echo    bash bootstrap.sh
echo.
pause
exit /b 1

:found
echo Found Git Bash: %BASH%
echo Running bootstrap.sh...
echo.
%BASH% -c "cd '%~dp0' && bash bootstrap.sh %*"
