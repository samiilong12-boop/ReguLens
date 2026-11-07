$text = Get-Content 'reg_2016_2031.html' -Raw
$idx = $text.IndexOf('Article 73')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(10000, $text.Length - $idx))
    if ($snippet -match 'Other plants') {
        $clean = $snippet -replace '<[^>]+>', "`n"
        $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
        $lines[0..60] -join "`n" | Out-File 'scratch/art73_full.txt' -Encoding utf8
        break
    }
    $idx = $text.IndexOf('Article 73', $idx + 1)
}
Get-Content 'scratch/art73_full.txt'
