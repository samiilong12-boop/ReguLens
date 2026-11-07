$content = Get-Content "decision_1_2024.html" -Raw -Encoding UTF8
$clean = $content.Substring(0, 3000) -replace "<[^>]+>", " "
$clean = $clean -replace "\s+", " "
Write-Output $clean
