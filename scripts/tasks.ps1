<#
.SYNOPSIS
  Project task runner for Windows (PowerShell). Mirrors the Makefile targets.
.EXAMPLE
  ./scripts/tasks.ps1 setup
  ./scripts/tasks.ps1 import-sample
  ./scripts/tasks.ps1 backend     # terminal 1
  ./scripts/tasks.ps1 frontend    # terminal 2
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('setup', 'migrate', 'generate-sample', 'import-sample', 'backend', 'frontend', 'test', 'lint', 'build', 'check')]
  [string]$Task
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

function Invoke-In($dir, [scriptblock]$block) {
  Push-Location $dir
  try {
    & $block
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
  } finally { Pop-Location }
}

switch ($Task) {
  'setup' {
    Invoke-In $Backend { uv sync }
    Invoke-In $Frontend { npm install }
    Invoke-In $Backend { uv run python -m app.cli migrate }
  }
  'migrate' { Invoke-In $Backend { uv run python -m app.cli migrate } }
  'generate-sample' { Invoke-In $Backend { uv run python ../data/generate_sample.py } }
  'import-sample' { Invoke-In $Backend { uv run python -m app.cli import ../data/sample_reviews.csv --source synthetic } }
  'backend' { Invoke-In $Backend { uv run uvicorn app.main:app --reload --port 8000 } }
  'frontend' { Invoke-In $Frontend { npm run dev } }
  'test' {
    Invoke-In $Backend { uv run pytest }
    Invoke-In $Frontend { npm test }
  }
  'lint' {
    Invoke-In $Backend { uv run ruff check . }
    Invoke-In $Backend { uv run ruff format --check . }
    Invoke-In $Backend { uv run mypy app }
    Invoke-In $Frontend { npm run lint }
    Invoke-In $Frontend { npm run typecheck }
  }
  'build' { Invoke-In $Frontend { npm run build } }
  'check' {
    & $PSCommandPath lint
    & $PSCommandPath test
    & $PSCommandPath build
  }
}
