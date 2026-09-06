@echo off
setlocal enabledelayedexpansion
title CrowdFlow - Push to GitHub

cd /d "%~dp0"
echo ============================================
echo    CrowdFlow - Update GitHub Repository
echo ============================================
echo Folder: %CD%
echo.

rem ---------- Locate git ----------
set "GIT=git"
where git >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles%\Git\cmd\git.exe" (
    set "GIT=%ProgramFiles%\Git\cmd\git.exe"
  ) else (
    echo [ERROR] Git was not found on this PC.
    echo Install it from https://git-scm.com then double-click again.
    echo.
    pause
    exit /b 1
  )
)

rem ---------- Clean timestamp for the commit message ----------
set "TS="
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "TS=%%i"

rem ---------- Stage everything ----------
echo [1/3] Staging changes...
"%GIT%" add -A
if errorlevel 1 goto :error

rem ---------- Commit (if anything changed) ----------
set "FILES="
for /f "delims=" %%f in ('"%GIT%" status --short') do set "FILES=!FILES! %%f"
if not defined FILES (
  echo Nothing new to commit - working tree is clean.
  echo Still checking for unpushed commits...
  goto :push
)

echo [2/3] Committing:
"%GIT%" status --short
echo.
"%GIT%" commit -m "CrowdFlow update !TS!" -m "Files:!FILES!"
if errorlevel 1 (
  echo.
  echo [WARN] Commit was skipped - maybe an auto-sync already saved it.
)
echo.

:push
echo [3/3] Pushing to GitHub...
"%GIT%" push origin main
if errorlevel 1 goto :error

echo.
echo ============================================
echo    SUCCESS - your code is on GitHub!
echo    https://github.com/ziamominx/Crowd-Flow
echo ============================================
pause
exit /b 0

:error
echo.
echo [ERROR] Something went wrong - see the message above.
pause
exit /b 1
