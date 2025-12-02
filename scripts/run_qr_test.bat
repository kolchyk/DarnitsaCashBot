@echo off
echo Installing dependencies...
python -m pip install pyzbar beautifulsoup4 lxml
echo.
echo Running QR test...
python scripts\test_qr_scraping.py 5292124673841762126.jpg
pause

