$t = Get-Content 'reg_2023_988.html' -Raw
$m = [regex]::Match($t, '(?s)Article[^<]{0,10}50\b.{0,3000}')
if ($m.Success) {
    Write-Output ($m.Value -replace '<[^>]+>', "`n")
} else {
    Write-Output "Regex not matched"
}
