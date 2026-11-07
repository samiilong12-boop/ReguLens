$lines = Get-Content "reg_2026_194.html" -Encoding UTF8

Write-Output "=== RECITAL 7 (ORANGES) ==="
for ($i = 150; $i -lt 170; $i++) {
    if ($lines[$i] -match "Oranges from Egypt") {
        $sub = $lines[$i..($i+5)] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
        Write-Output $sub
    }
}

Write-Output "=== ANNEX I HEADERS ==="
for ($i = 1200; $i -lt 1400; $i++) {
    if ($lines[$i] -match "Frequency of") {
        $sub = $lines[($i-2)..($i+10)] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
        Write-Output $sub
    }
}

Write-Output "=== EGYPT ORANGES ROW IN TABLE ==="
for ($i = 2060; $i -lt 2110; $i++) {
    if ($lines[$i] -match "0805 10") {
        $sub = $lines[($i-10)..($i+15)] -join " " -replace "<[^>]+>", " " -replace "\s+", " "
        Write-Output $sub
    }
}
