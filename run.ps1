$runner = Join-Path $PSScriptRoot 'run.py'

if (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
    & py -3 --version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        & py -3 $runner @args
        exit $LASTEXITCODE
    }
}

if (Get-Command uv -CommandType Application -ErrorAction SilentlyContinue) {
    & uv run --offline --python 3.11 $runner @args
    exit $LASTEXITCODE
}

Write-Error 'Install Python 3.10 or newer with the Windows Python launcher, or install Python 3.11 through uv.'
exit 1
