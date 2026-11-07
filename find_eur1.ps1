$lines = Get-Content "decision_1_2024.html" -Encoding UTF8
for ($i = 0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match "movement certificate EUR\.1" -and $lines[$i] -match "shall be issued by") {
        Write-Output "Line $i : $($lines[$i])"
    }
    if ($lines[$i] -match "origin declaration may be made out") {
        Write-Output "Line $i : $($lines[$i])"
    }
}
