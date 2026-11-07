$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
for ($i = 0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match "0805 10") {
        Write-Output "Line $i has 0805 10"
        $sub = $lines[($i-5)..($i+15)] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
        Write-Output $sub
    }
}
