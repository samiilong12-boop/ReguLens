$text = Get-Content 'reg_2023_988.html' -Raw

# Search for Article 7
$idx7 = $text.IndexOf('Article 7')
while ($idx7 -ge 0) {
    $snippet = $text.Substring($idx7, [Math]::Min(4000, $text.Length - $idx7))
    if ($snippet -match 'Presumption of conformity') {
        $clean = $snippet -replace '<[^>]+>', "`n"
        $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
        Write-Output "=== ARTICLE 7 OF GPSR ==="
        $lines[0..35] -join "`n"
        break
    }
    $idx7 = $text.IndexOf('Article 7', $idx7 + 1)
}

# Search for Article 50, 51, 52 (Transitional provisions / Repeal)
$idx50 = $text.IndexOf('Article 50')
while ($idx50 -ge 0) {
    $snippet = $text.Substring($idx50, [Math]::Min(6000, $text.Length - $idx50))
    if ($snippet -match 'Repeal|Transitional') {
        $clean = $snippet -replace '<[^>]+>', "`n"
        $lines = $clean -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
        Write-Output "=== ARTICLES 50-52 OF GPSR ==="
        $lines[0..50] -join "`n"
        break
    }
    $idx50 = $text.IndexOf('Article 50', $idx50 + 1)
}
