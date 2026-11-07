$html = Get-Content 'scratch/decision_2026_901.html' -Raw
$idx = $html.IndexOf('ANNEX II')
if ($idx -ge 0) {
    $chunk = $html.Substring($idx)
    $clean = $chunk -replace '<[^>]+>', "`n" -replace '&nbsp;', ' '
    Write-Output "=== ANNEX II OF DECISION 2026/901 ==="
    $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_.Trim() }
}
