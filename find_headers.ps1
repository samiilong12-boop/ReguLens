$lines = Get-Content "reg_2026_194.html" -Encoding UTF8
for ($i = 500; $i -lt 1300; $i++) {
    if ($lines[$i] -match "Hazard" -or $lines[$i] -match "Country of origin" -or $lines[$i] -match "CN code") {
        Write-Output "Line $i : $($lines[$i])"
    }
}
