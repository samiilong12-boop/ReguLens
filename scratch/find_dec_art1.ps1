$html = Get-Content 'scratch/decision_2026_901.html' -Raw
$idx = $html.IndexOf('Article 1')
if ($idx -lt 0) { $idx = $html.IndexOf('ArticleA 1') }
$chunk = $html.Substring($idx, [Math]::Min(3000, $html.Length - $idx))
$clean = $chunk -replace '<[^>]+>', "`n" -replace '&nbsp;', ' '
$clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_.Trim() }
