# Building from source

## Requirements

- Windows x64
- No Man's Sky installed next to this repository
- Python 3.13 x64
- Visual Studio 2019 or 2022 Build Tools with MSVC x64 and Windows 10 SDK
- `python-3.13.15-embed-amd64.zip` from python.org

## Build

Open PowerShell in the repository folder:

```powershell
.\scripts\setup.ps1 -PythonExe "C:\full\path\to\python.exe"
.\scripts\build-autoload.ps1
$env:PYTEST_VERSION = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:PYTEST_VERSION
.\scripts\build-release.ps1 -Version 1.1.0 `
  -EmbeddablePython "C:\full\path\to\python-3.13.15-embed-amd64.zip"
```

The finished package is written to
`dist\Planetary-Surveyor-v1.1.0.zip`.

Native code is in `autoload\native`. Scanner code is in `src`. The build does
not download anything at runtime or modify the game executable.

One test checks signatures against the installed `NMS.exe`. A game update still
needs a real test with a backed-up save.
