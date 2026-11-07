$text = Get-Content 'reg_2023_988.html' -Raw

$matches7 = [regex]::Matches($text, '(?s)(Article\s+7\b.{0,500})')
Write-Output "Article 7 matches: $($matches7.Count)"
foreach ($m in $matches7) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ' -replace '\s+', ' ')
}

$matches50 = [regex]::Matches($text, '(?s)(Article\s+5[0-2]\b.{0,500})')
Write-Output "Article 50-52 matches: $($matches50.Count)"
foreach ($m in $matches50) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ' -replace '\s+', ' ')
}
