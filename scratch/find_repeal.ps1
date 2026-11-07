$t = Get-Content 'reg_2023_988.html' -Raw
$matches2001 = [regex]::Matches($t, '(?s)2001/95/EC.{0,1000}')
Write-Output "Found $($matches2001.Count) mentions of 2001/95/EC"
foreach ($m in ($matches2001 | Select-Object -Last 5)) {
    Write-Output "----------------------------------"
    Write-Output ($m.Value -replace '<[^>]+>', "`n" -replace '&nbsp;', ' ')
}
