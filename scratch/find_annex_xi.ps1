$text = Get-Content 'reg_2019_2072.html' -Raw

$idx = $text.IndexOf('ANNEX XI')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(15000, $text.Length - $idx))
    $clean = $snippet -replace '<[^>]+>', "`n"
    $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $lines[0..60] -join "`n" | Out-File 'scratch/annex_xi_head.txt' -Encoding utf8
    break
}
Get-Content 'scratch/annex_xi_head.txt'
