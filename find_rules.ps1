$lines = Get-Content "decision_1_2024.html" -Encoding UTF8

function Find-Annex-Rule($chapter) {
    Write-Output "=== RULE FOR $chapter ==="
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match "(?:Chapter\s+$chapter|ex\s+Chapter\s+$chapter)" -and $lines[$i] -match "oj-table") {
            $snippet = $lines[$i..([Math]::Min($lines.Length - 1, $i + 15))] -join " "
            $clean = $snippet -replace "<[^>]+>", " "
            $clean = $clean -replace "\s+", " "
            Write-Output $clean
            break
        }
    }
}

Find-Annex-Rule "8"
Find-Annex-Rule "61"
Find-Annex-Rule "62"
Find-Annex-Rule "50"
Find-Annex-Rule "52"
