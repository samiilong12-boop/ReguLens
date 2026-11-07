$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
$snippet = $lines[7880..7990] -join "`n"
$clean = $snippet -replace "<[^>]+>", " "
Write-Output $clean
