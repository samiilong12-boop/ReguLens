$t = Get-Content 'reg_2023_988.html' -Raw
# Replace non-breaking spaces and clean HTML tags
$clean = $t -replace '&nbsp;', ' ' -replace '&#160;', ' ' -replace '\u00A0', ' ' -replace 'A', ' '

Write-Output "--- SEARCHING FOR PRESUMPTION OF CONFORMITY ---"
$mPresump = [regex]::Match($clean, '(?s)Presumption of conformity.{0,2500}')
if ($mPresump.Success) {
    Write-Output ($mPresump.Value -replace '<[^>]+>', "`n")
} else {
    Write-Output "Presumption not matched"
}

Write-Output "--- SEARCHING FOR REPEAL / TRANSITIONAL ---"
$mTrans = [regex]::Match($clean, '(?s)(?:Repeal|Transitional provisions).{0,2500}')
if ($mTrans.Success) {
    Write-Output ($mTrans.Value -replace '<[^>]+>', "`n")
} else {
    Write-Output "Repeal not matched"
}
