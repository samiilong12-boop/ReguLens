$content = Get-Content "decision_1_2024.html" -Raw -Encoding UTF8

function Extract-Chapter($chPattern) {
    Write-Output "========================================"
    Write-Output "SEARCH FOR $chPattern"
    Write-Output "========================================"
    $regex = [regex]"(?s)(<tr[^>]*>[\s\S]*?$chPattern[\s\S]*?</tr>)"
    $m = $regex.Matches($content)
    foreach ($match in $m | Select-Object -First 3) {
        $c = $match.Value -replace "<[^>]+>", " "
        $c = $c -replace "\s+", " "
        Write-Output $c
    }
}

Extract-Chapter "Chapter\s+8\b"
Extract-Chapter "Chapter\s+61\b"
Extract-Chapter "Chapter\s+62\b"
Extract-Chapter "Chapter\s+52\b"
