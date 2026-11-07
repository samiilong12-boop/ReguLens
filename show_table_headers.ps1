$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
$sub = $lines[1300..1400] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
Write-Output $sub
