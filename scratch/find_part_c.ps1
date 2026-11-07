$text = Get-Content 'reg_2019_2072.html' -Raw
$idxPartC = $text.IndexOf('PART C', 2194489)
if ($idxPartC -ge 0) {
    Write-Output "Found PART C at index $idxPartC"
    $chunk = $text.Substring($idxPartC, [Math]::Min(5000, $text.Length - $idxPartC))
    $clean = $chunk -replace '<[^>]+>', "`n"
    $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $lines[0..40] -join "`n"
} else {
    Write-Output "PART C not found after 2194489"
}
