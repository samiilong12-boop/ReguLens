$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
$matched = $lines | Select-String -Pattern "Egypt|strawberr|orange|citrus|0811|0805|entry into force|shall apply"
foreach ($m in $matched) {
    $lineNum = $m.LineNumber
    $start = [Math]::Max(0, $lineNum - 2)
    $count = 5
    $sub = $lines[$start..($start + $count)] -join " "
    $clean = $sub -replace "<[^>]+>", " "
    $clean = $clean -replace "\s+", " "
    Write-Output "Line $lineNum : $clean"
}
