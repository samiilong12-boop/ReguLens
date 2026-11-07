$text = Get-Content 'reg_2019_2072.html' -Raw
$idxAnnexXI = $text.LastIndexOf('ANNEX XI', 2071484)
$chunk = $text.Substring($idxAnnexXI, 2071484 - $idxAnnexXI)
$clean = $chunk -replace '<[^>]+>', "`n"
$lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
$partLines = $lines | Where-Object { $_ -match '^PART\s+[A-Z]' }
Write-Output "Part headings between ANNEX XI and Strawberries:"
$partLines
