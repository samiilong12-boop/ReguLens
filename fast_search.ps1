$lines = Get-Content "decision_1_2024.html" -Encoding UTF8

for ($i = 0; $i -lt $lines.Length; $i++) {
    $line = $lines[$i]
    if ($line -match "oj-table" -or $line -match "<td") {
        if ($line -match "Chapter 8\b" -or $line -match "Chapter 61\b" -or $line -match "Chapter 62\b" -or $line -match "Chapter 52\b") {
            Write-Output "--- FOUND at line $i ---"
            $sub = $lines[$i..([Math]::Min($lines.Length-1, $i+12))] -join " "
            $clean = $sub -replace "<[^>]+>", " "
            $clean = $clean -replace "\s+", " "
            Write-Output $clean
        }
    }
}
