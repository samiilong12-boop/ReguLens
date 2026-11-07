$html = Get-Content 'scratch/decision_2026_901.html' -Raw
$idx = $html.IndexOf('EN 14682:2014')
if ($idx -ge 0) {
    $start = [Math]::Max(0, $idx - 500)
    $snippet = $html.Substring($start, [Math]::Min(1500, $html.Length - $start))
    Write-Output "=== EN 14682:2014 IN DECISION 2026/901 ==="
    $clean = $snippet -replace '<[^>]+>', "`n" -replace '&nbsp;', ' '
    $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_.Trim() }
}
