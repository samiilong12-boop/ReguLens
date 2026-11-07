$html = Get-Content 'scratch/decision_2026_901.html' -Raw
$clean = $html -replace '<[^>]+>', "`n" -replace '&nbsp;', ' '
$lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
$lines[0..60] | ForEach-Object { $_.Trim() }
