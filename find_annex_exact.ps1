$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
$matched = $lines | Select-String -Pattern "Annex II\b|Annex 2\b"
foreach ($m in $matched | Select-Object -First 10) {
    Write-Output "Line $($m.LineNumber): $($m.Line)"
}
