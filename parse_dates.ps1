$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
$matched = $lines | Select-String -Pattern "Article 2|shall enter into force|shall apply from"
foreach ($m in $matched) {
    $lineNum = $m.LineNumber
    $start = [Math]::Max(0, $lineNum - 2)
    $sub = $lines[$start..($start + 6)] -join " "
    $clean = $sub -replace "<[^>]+>", " "
    $clean = $clean -replace "\s+", " "
    Write-Output "Line $lineNum : $clean"
}
