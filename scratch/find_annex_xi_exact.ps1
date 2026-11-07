$text = Get-Content 'reg_2019_2072.html' -Raw

# Search for regex "ANNEX XI\b"
$matches = [regex]::Matches($text, '(?s)<p[^>]*class="oj-doc-ti"[^>]*>.*?(?:ANNEX\s+XI|Annex\s+XI).*?</p>')
Write-Output "Matches count: $($matches.Count)"
foreach ($m in $matches) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}

# Also search for CN code 0810 10 and 0811
Write-Output "--- SEARCHING 0810 10 ---"
$m0810 = [regex]::Matches($text, '(?s).{0,100}0810\s*10.{0,100}')
Write-Output "0810 10 count: $($m0810.Count)"
foreach ($m in ($m0810 | Select-Object -First 5)) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}

Write-Output "--- SEARCHING 0811 ---"
$m0811 = [regex]::Matches($text, '(?s).{0,100}0811.{0,100}')
Write-Output "0811 count: $($m0811.Count)"
foreach ($m in ($m0811 | Select-Object -First 5)) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}
