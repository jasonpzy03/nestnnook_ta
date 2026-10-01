$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $projectPython -c 'import fastapi, uvicorn, lxml, pymupdf' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $projectPython -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies.' }
}
if (-not (Test-Path '.local/auth.json')) {
    & $projectPython -m backend.setup_access
    if ($LASTEXITCODE -ne 0) { throw 'Staff password setup failed.' }
}
Push-Location frontend
try {
    if (-not (Test-Path node_modules)) {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Could not install frontend dependencies.' }
    }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Nest & Nook is available at http://localhost:8000'
Write-Host 'On your phone, use this computer''s IPv4 address and port 8000 on the same Wi-Fi.'
& $projectPython -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
