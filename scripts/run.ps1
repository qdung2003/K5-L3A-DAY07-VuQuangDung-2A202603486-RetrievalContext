param([ValidateSet('dev', 'select', 'test', 'verify', 'cost')][string]$Stage = 'verify',
      [string]$ResultsRoot = 'results')
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Stage -eq 'verify') {
        python -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
        python scripts/verify_submission.py --results-root $ResultsRoot
    } elseif ($Stage -eq 'select') {
        python scripts/experiment.py select --resume --results-root $ResultsRoot
    } elseif ($Stage -eq 'cost') {
        python scripts/cost_report.py --results-root $ResultsRoot
    } else {
        python scripts/experiment.py $Stage --resume --results-root $ResultsRoot
    }
    if ($LASTEXITCODE -ne 0) { throw 'Pipeline command failed' }
} finally {
    Pop-Location
}
