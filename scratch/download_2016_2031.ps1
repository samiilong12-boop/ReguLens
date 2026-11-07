$url = 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R2031'
curl.exe -s -L --max-time 30 $url -o scratch/reg_2016_2031.html
Write-Output "Downloaded size: $((Get-Item scratch/reg_2016_2031.html).Length)"
