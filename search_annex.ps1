$lines = Get-Content "decision_1_2024.html" -Encoding UTF8

function Search-Annex($query) {
    Write-Output "=== QUERY: $query ==="
    for ($i = 5007; $i -lt 9581; $i++) {
        if ($lines[$i] -match $query) {
            $snippet = $lines[$i..([Math]::Min(9581, $i + 15))] -join " "
            $clean = $snippet -replace "<[^>]+>", " "
            $clean = $clean -replace "\s+", " "
            Write-Output "Line $i : $clean"
            Write-Output "----------------------------------------"
        }
    }
}

Search-Annex "Chapter\s*8\b"
Search-Annex "0805"
Search-Annex "0811"
Search-Annex "Chapter\s*61\b"
Search-Annex "Chapter\s*62\b"
Search-Annex "Chapter\s*52\b"
