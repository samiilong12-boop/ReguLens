$text = Get-Content 'reg_2016_2031.html' -Raw

# Search for "Article 2" and "Definitions"
$idx = $text.IndexOf('Article 2')
while ($idx -ge 0) {
    $snippet = $text.Substring($idx, [Math]::Min(3000, $text.Length - $idx))
    if ($snippet -match 'Definitions') {
        $clean = $snippet -replace '<[^>]+>', ' ' -replace '\s+', ' '
        Write-Output "FOUND ARTICLE 2:"
        Write-Output $clean.Substring(0, [Math]::Min(2000, $clean.Length))
        break
    }
    $idx = $text.IndexOf('Article 2', $idx + 1)
}
