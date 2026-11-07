param([Parameter(ValueFromRemainingArguments = $true)][string[]]$BraceArgs)
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
& python -m brace_msi @BraceArgs
exit $LASTEXITCODE
