$html = Get-Content 'scratch/decision_2026_901.html' -Raw
$m = [regex]::Match($html, '(?s)HAS ADOPTED THIS DECISION:.{0,2000}')
if ($m.Success) {
    $clean = $m.Value -replace '<[^>]+>', "`n" -replace '&nbsp;', ' '
    $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_.Trim() }
}
