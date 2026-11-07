$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
for ($i = 0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match "ANNEX II" -or $lines[$i] -match "ANNEX 2") {
        Write-Output "Line $i : $($lines[$i])"
    }
}
