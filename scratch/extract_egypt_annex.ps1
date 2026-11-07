$html = Get-Content -Path "reg_2026_194.html" -Raw
$matches = [regex]::Matches($html, '(?s)<tr[^>]*>.*?Egypt \(EG\).*?</tr>')
foreach ($m in $matches) {
    if ($m.Value -match 'Orange|Strawberr') {
        $clean = [regex]::Replace($m.Value, '<[^>]+>', ' ')
        $clean = [regex]::Replace($clean, '\s+', ' ')
        Write-Output "CLEAN: $clean"
        Write-Output "RAW:"
        Write-Output $m.Value
        Write-Output "----------------------------------------"
    }
}
