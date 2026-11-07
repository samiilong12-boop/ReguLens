$html = Get-Content -Path "reg_2026_194.html" -Raw
# Find the position of ANNEX I
$annexPos = $html.IndexOf('ANNEX I')
$annexText = $html.Substring($annexPos)

# Let's extract table headers and table rows for Egypt
$egMatches = [regex]::Matches($annexText, '(?s)<tr[^>]*>.*?</tr>')
Write-Output "Total rows in Annex: $($egMatches.Count)"

$found = 0
foreach ($m in $egMatches) {
    if ($m.Value -match 'Oranges|Strawberr' -and $m.Value -match 'Egypt|0805|0810|0811') {
        $clean = [regex]::Replace($m.Value, '<[^>]+>', ' ')
        $clean = [regex]::Replace($clean, '\s+', ' ').Trim()
        Write-Output "ROW: $clean"
        Write-Output "HTML:"
        Write-Output $m.Value
        Write-Output "========================================"
        $found++
    }
}
Write-Output "Found matching rows: $found"
