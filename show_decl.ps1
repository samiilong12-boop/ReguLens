$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
$snippet = $lines[2730..2765] -join " "
$clean = $snippet -replace "<[^>]+>", " "
$clean = $clean -replace "\s+", " "
Write-Output $clean
