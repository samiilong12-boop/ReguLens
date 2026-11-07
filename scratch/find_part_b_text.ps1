$text = Get-Content 'reg_2019_2072.html' -Raw
$idxPartB = $text.IndexOf('PART B', 2071484)
if ($idxPartB -ge 0) {
    Write-Output "Found PART B at index $idxPartB"
    $chunk = $text.Substring($idxPartB, [Math]::Min(10000, $text.Length - $idxPartB))
    $clean = $chunk -replace '<[^>]+>', "`n"
    $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $lines[0..60] -join "`n"
} else {
    Write-Output "PART B not found after 2071484"
}
