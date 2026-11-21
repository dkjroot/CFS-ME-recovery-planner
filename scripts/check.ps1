$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$localPaths = @('AGENTS.md', 'DEVELOPMENT.md', 'agent_docs/', 'local_data/', '.env', '.env.local')
$ignoreProbes = @('AGENTS.md', 'DEVELOPMENT.md', 'agent_docs/reference.pdf', 'local_data/sample.json', '.env', '.env.local')

try {
    git -C $repository diff --check HEAD
    if ($LASTEXITCODE -ne 0) {
        throw 'git diff --check failed. See Git output above.'
    }

    $tracked = git -C $repository ls-files -- $localPaths
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not check the Git index for local files.'
    }
    if ($tracked) {
        throw 'Git is tracking files reserved for local use. Check the Git index.'
    }

    foreach ($path in $ignoreProbes) {
        git -C $repository check-ignore --quiet -- $path
        if ($LASTEXITCODE -ne 0) {
            throw "Expected Git to ignore $path. Check .gitignore."
        }
    }

    Write-Output 'Repository checks passed (whitespace, Git ignores, and local paths).'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
