$html = Get-Content -Path "reg_2026_194.html" -Raw
$annexPos = $html.IndexOf('ANNEX I')
$annexText = $html.Substring($annexPos)

$egPos = $annexText.IndexOf('Egypt (EG)')
# Let's find the next country after Egypt
$afterEg = $annexText.Substring($egPos + 50)
$nextCountryMatch = [regex]::Match($afterEg, '(?s)<td[^>]*rowspan="\d+"[^>]*>\s*<p class="oj-tbl-txt">\s*<span class="oj-bold">([^<]+)</span>')
$nextCountryPos = $nextCountryMatch.Index

$egBlock = $afterEg.Substring(0, $nextCountryPos)
Write-Output "NEXT COUNTRY: $($nextCountryMatch.Groups[1].Value)"
Write-Output "--- EG BLOCK RAW ---"

# Let's extract all rows in the Egypt block
$rows = [regex]::Matches($egBlock, '(?s)<tr[^>]*>.*?</tr>')
Write-Output "Total rows under Egypt: $($rows.Count)"
foreach ($r in $rows) {
    $clean = [regex]::Replace($r.Value, '<[^>]+>', ' ')
    $clean = [regex]::Replace($clean, '\s+', ' ').Trim()
    Write-Output "ROW: $clean"
}
