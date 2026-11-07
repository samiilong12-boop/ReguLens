$t = Get-Content 'reg_2023_988.html' -Raw
$matches = [regex]::Matches($t, '(?i)article\s*[0-9]+')
Write-Output "Found $($matches.Count) matches:"
foreach ($m in ($matches | Select-Object -First 20)) {
    Write-Output $m.Value
}

# Look for Article 7 specifically
$idx = $t.IndexOf('Article 7')
if ($idx -lt 0) { $idx = $t.IndexOf('ArticleA 7') }
if ($idx -lt 0) {
    # Search with regex
    $m7 = [regex]::Match($t, '(?s)Article[^0-9]{1,10}7\b.{0,1500}')
    if ($m7.Success) {
        Write-Output "=== FOUND ARTICLE 7 ==="
        Write-Output ($m7.Value -replace '<[^>]+>', "`n")
    }
} else {
    Write-Output "Found at $idx"
}
