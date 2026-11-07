$text = Get-Content 'reg_2016_2031.html' -Raw
$idx = $text.IndexOf('Article 2')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(15000, $text.Length - $idx))
    if ($snippet -match 'Definitions') {
        $clean = $snippet -replace '<[^>]+>', "`n"
        $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
        $lines[20..90] -join "`n" | Out-File 'scratch/art2_part2.txt' -Encoding utf8
        break
    }
    $idx = $text.IndexOf('Article 2', $idx + 1)
}
Get-Content 'scratch/art2_part2.txt'
