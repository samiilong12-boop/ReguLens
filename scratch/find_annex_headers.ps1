$html = Get-Content -Path "reg_2026_194.html" -Raw
$annexPos = $html.IndexOf('ANNEX I')
$sub = $html.Substring($annexPos, 5000)
# Extract table headers <th> or first <tr>
$thMatches = [regex]::Matches($sub, '(?s)<th[^>]*>.*?</th>')
if ($thMatches.Count -gt 0) {
    foreach ($th in $thMatches) {
        $clean = [regex]::Replace($th.Value, '<[^>]+>', ' ')
        $clean = [regex]::Replace($clean, '\s+', ' ').Trim()
        Write-Output "HEADER: $clean"
    }
} else {
    # check first <tr>
    $firstTr = [regex]::Match($sub, '(?s)<tr[^>]*>.*?</tr>')
    $clean = [regex]::Replace($firstTr.Value, '<[^>]+>', ' ')
    $clean = [regex]::Replace($clean, '\s+', ' ').Trim()
    Write-Output "FIRST TR: $clean"
    Write-Output "RAW FIRST TR: $($firstTr.Value)"
}
