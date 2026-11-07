$text = Get-Content 'reg_2019_2072.html' -Raw

# Replace any non-breaking space or special chars with normal space
$clean = $text -replace '\s+', ' ' -replace '&nbsp;', ' ' -replace '&#160;', ' '

Write-Output "--- SEARCHING FOR FRAGARIA ---"
$matchesFrag = [regex]::Matches($clean, '(?i)(.{0,80}Fragaria.{0,80})')
Write-Output "Fragaria count: $($matchesFrag.Count)"
foreach ($m in ($matchesFrag | Select-Object -First 15)) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}

Write-Output "--- SEARCHING FOR 0810 ---"
$matches0810 = [regex]::Matches($clean, '(?i)(.{0,80}0810.{0,80})')
Write-Output "0810 count: $($matches0810.Count)"
foreach ($m in ($matches0810 | Select-Object -First 15)) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}

Write-Output "--- SEARCHING FOR 0811 ---"
$matches0811 = [regex]::Matches($clean, '(?i)(.{0,80}0811.{0,80})')
Write-Output "0811 count: $($matches0811.Count)"
foreach ($m in ($matches0811 | Select-Object -First 15)) {
    Write-Output ($m.Value -replace '<[^>]+>', ' ')
}
