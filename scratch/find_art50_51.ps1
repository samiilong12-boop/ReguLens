$t = Get-Content 'reg_2023_988.html' -Raw
$idx50 = $t.IndexOf('ArticleA50')
if ($idx50 -lt 0) { $idx50 = $t.IndexOf('Article 50') }
if ($idx50 -ge 0) {
    $chunk = $t.Substring($idx50, [Math]::Min(4000, $t.Length - $idx50))
    $clean = $chunk -replace '<[^>]+>', "`n" -replace '&nbsp;', ' ' -replace 'A', ' '
    $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $lines[0..40] -join "`n"
} else {
    Write-Output "Not found"
}
