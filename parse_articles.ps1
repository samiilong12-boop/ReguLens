$lines = Get-Content "decision_1_2024.html" -Encoding UTF8

function Show-Range($startPattern, $endPattern, $maxLines) {
    $startIdx = ($lines | Select-String -Pattern $startPattern | Select-Object -First 1).LineNumber
    if ($startIdx) {
        Write-Output "Found $startPattern at line $startIdx"
        $sub = $lines[($startIdx - 1)..($startIdx + $maxLines)] -join "`n"
        $clean = $sub -replace "<[^>]+>", " "
        $clean = $clean -replace "[ \t]+", " "
        Write-Output $clean
    }
}

Show-Range "Article 17" "Article 18" 40
Show-Range "Article 18" "Article 19" 40
Show-Range "ex Chapter 61" "Chapter 62" 50
Show-Range "ex Chapter 62" "Chapter 63" 50
Show-Range "Chapter 8" "Chapter 9" 30
