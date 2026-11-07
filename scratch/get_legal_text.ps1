$url = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R2031'
$html = curl.exe -s -L --max-time 25 $url
$pattern = '(?s)Article 2\s*<[^>]+>\s*Definitions.*?Article 3\b'
if ($html -match $pattern) {
    $matches[0] -replace '<[^>]+>', ' ' | Out-File -FilePath 'scratch/art2_clean.txt' -Encoding utf8
} else {
    Write-Output "Pattern not matched"
}
Get-Content 'scratch/art2_clean.txt' -TotalCount 50
