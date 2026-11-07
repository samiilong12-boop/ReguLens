$text = Get-Content 'reg_2019_2072.html' -Raw

$idx = $text.IndexOf('Strawberries, fresh or chilled')
if ($idx -ge 0) {
    Write-Output "Found 'Strawberries, fresh or chilled' at index $idx"
    # Find preceding 15000 characters
    $prev = $text.Substring([Math]::Max(0, $idx - 15000), [Math]::Min(15000, $idx))
    $cleanPrev = $prev -replace '<[^>]+>', "`n"
    $lines = $cleanPrev -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    Write-Output "=== LAST 30 LINES BEFORE STRAWBERRIES ==="
    $lines[-30..-1] -join "`n"

    Write-Output "=== FOLLOWING 20 LINES AFTER STRAWBERRIES ==="
    $next = $text.Substring($idx, [Math]::Min(3000, $text.Length - $idx))
    $cleanNext = $next -replace '<[^>]+>', "`n"
    $nextLines = $cleanNext -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
    $nextLines[0..20] -join "`n"
} else {
    Write-Output "Not found"
}
