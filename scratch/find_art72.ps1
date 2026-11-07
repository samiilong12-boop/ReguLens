$text = Get-Content 'reg_2016_2031.html' -Raw
$idx = $text.IndexOf('Article 72')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(10000, $text.Length - $idx))
    if ($snippet -match 'Phytosanitary certificate') {
        $clean = $snippet -replace '<[^>]+>', "`n"
        $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
        $lines[0..80] -join "`n" | Out-File 'scratch/art72_73.txt' -Encoding utf8
        break
    }
    $idx = $text.IndexOf('Article 72', $idx + 1)
}
Get-Content 'scratch/art72_73.txt'
