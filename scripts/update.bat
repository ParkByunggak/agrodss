@echo off
rem update.bat - pull the latest code without getting stuck on data\parcels.json (U-18).
rem  The old registry file was tracked by git and runtime writes (geocode coords) modified it locally.
rem  If it is still modified, git pull stops with "commit or stash". Its values now live in
rem  data\parcels_local.json (git-ignored), so discarding the local edit loses nothing.
rem  ASCII only, no parentheses inside redirect blocks (cmd rules, see CLAUDE.md).
setlocal
cd /d "%~dp0.."
git diff --quiet -- data/parcels.json
if errorlevel 1 git checkout -- data/parcels.json
git pull origin main
echo update done - the screen server restarts itself when HEAD changed.
endlocal
