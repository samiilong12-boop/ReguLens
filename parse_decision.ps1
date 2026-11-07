$lines = Get-Content "decision_search.html" -Encoding UTF8
$matched = $lines | Select-String -Pattern "Decision No 1/2024|Protocol 4|rules of origin"
foreach ($m in $matched) {
    $lineNum = $m.LineNumber
    $sub = $lines[($lineNum - 1)..($lineNum + 3)] -join " "
    $clean = $sub -replace "<[^>]+>", " "
    $clean = $clean -replace "\s+", " "
    Write-Output "Line $lineNum : $clean"
}
