$text = Get-Content 'reg_2019_2072.html' -Raw
$idxAnnexXI = $text.LastIndexOf('ANNEX XI', 2071484)
$chunk = $text.Substring($idxAnnexXI, 2071484 - $idxAnnexXI)
$clean = $chunk -replace '<[^>]+>', "`n"
$lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
$lines[580..627] -join "`n"
