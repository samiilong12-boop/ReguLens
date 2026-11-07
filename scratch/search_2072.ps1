$text = Get-Content 'reg_2019_2072.html' -Raw

# Search for Article 11
$idx = $text.IndexOf('Article 11')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(3000, $text.Length - $idx))
    $clean = $snippet -replace '<[^>]+>', "`n"
    $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $lines[0..30] -join "`n" | Out-File 'scratch/art11_2072.txt' -Encoding utf8
    break
}
Get-Content 'scratch/art11_2072.txt'

# Search for occurrences of Fragaria or strawberr or 0810 or 0811
Write-Output "--- SEARCHING FOR STRAWBERRY / FRAGARIA / 0810 / 0811 ---"
$matches1 = [regex]::Matches($text, '(?i)(Fragaria|strawberr|0810\s*10|0811\s*10)[^<]{0,150}')
foreach ($m in ($matches1 | Select-Object -First 10)) {
    Write-Output $m.Value
}
