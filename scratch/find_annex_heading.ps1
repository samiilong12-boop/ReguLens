$text = Get-Content 'reg_2019_2072.html' -Raw
$idx = 2071484
$prev = $text.Substring(0, $idx)
$lastAnnex = [regex]::Matches($prev, '(?s)<p[^>]*class="oj-doc-ti"[^>]*>.*?(?:ANNEX|PART).*?</p>')
Write-Output "Total headings before 2071484: $($lastAnnex.Count)"
foreach ($h in ($lastAnnex | Select-Object -Last 5)) {
    Write-Output ($h.Value -replace '<[^>]+>', ' ')
}

# Also find any table header or introductory text for this section
$prevChunk = $prev.Substring([Math]::Max(0, $prev.Length - 10000))
$cleanChunk = $prevChunk -replace '<[^>]+>', "`n"
$lines = $cleanChunk -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
$headers = $lines | Where-Object { $_ -match 'PART\b|ANNEX\b|List of|Article\b' }
Write-Output "=== HEADERS IN CHUNK ==="
$headers
