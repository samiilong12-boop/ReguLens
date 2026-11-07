$lines = Get-Content "decision_1_2024.html" -Encoding UTF8

function Find-Context($pattern, $label) {
    Write-Output "=== $label ==="
    $matched = $lines | Select-String -Pattern $pattern
    foreach ($m in $matched | Select-Object -First 5) {
        $lineNum = $m.LineNumber
        $sub = $lines[($lineNum - 1)..($lineNum + 4)] -join " "
        $clean = $sub -replace "<[^>]+>", " "
        $clean = $clean -replace "\s+", " "
        Write-Output "Line $lineNum : $clean"
    }
}

Find-Context "EUR.1" "EUR.1 mentions"
Find-Context "origin declaration" "Origin Declaration mentions"
Find-Context "6 000" "6000 EUR threshold"
Find-Context "customs authorities" "Customs authorities issuing"
Find-Context "Chapter 61" "Chapter 61 rules"
Find-Context "Chapter 62" "Chapter 62 rules"
Find-Context "Chapter 8" "Chapter 8 rules"
