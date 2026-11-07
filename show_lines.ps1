$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
$sub = $lines[2050..2120] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
Write-Output $sub
