@echo off
echo Configuring Git...
git config user.name "Quran Reciter Developer"
git config user.email "developer@quranreciter.com"
echo.
echo Git configured successfully!
echo.
echo Now creating first commit...
git add .
git commit -m "Initial commit: Complete Quran Reciter ID with auto-build"
echo.
echo Done! Now you can push to GitHub.
pause
