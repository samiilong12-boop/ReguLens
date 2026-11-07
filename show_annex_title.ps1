$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
$snippet = $lines[1190..1225] -join "`n"
$clean = $snippet -replace "<[^>]+>", " "
Write-Output $clean
