# Installing Tesseract OCR on Windows

Tesseract is required for local OCR in the registration verification system.

## Quick Install (recommended)

### Option 1: Using Chocolatey (fastest)
```powershell
# Install Chocolatey if not already installed
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Tesseract
choco install tesseract -y

# Verify installation
tesseract --version
```

### Option 2: Manual Download
1. Download the Windows installer from: https://github.com/UB-Mannheim/tesseract/wiki
   - Direct link (64-bit): https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe
2. Run the installer and follow prompts
3. During installation, note the install path (default: `C:\Program Files\Tesseract-OCR`)
4. Add Tesseract to PATH:
   ```powershell
   # Add to PATH for current session
   $env:Path += ";C:\Program Files\Tesseract-OCR"
   
   # Add to PATH permanently (requires admin)
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\Tesseract-OCR", [EnvironmentVariableTarget]::Machine)
   ```
5. Open a new PowerShell window and verify:
   ```powershell
   tesseract --version
   ```

## After Installation

Once Tesseract is installed and on PATH, re-run the detection sweep:

```powershell
python .\scripts\inference_summary_review.py
```

The OCR preview column in `models/detections_review.csv` should now contain extracted text tokens.
