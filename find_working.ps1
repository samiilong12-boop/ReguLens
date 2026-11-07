$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
$matched = $lines | Select-String -Pattern "working or processing"
foreach ($m in $matched | Select-Object -First 10) {
    Write-Output "Line $($m.LineNumber): $($m.Line)"
}
