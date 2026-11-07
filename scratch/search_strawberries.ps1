# Search 2016/2031 once downloaded
if (Test-Path 'scratch/reg_2016_2031.html') {
    $text = Get-Content 'scratch/reg_2016_2031.html' -Raw
    # Find Article 2
    $idx2 = $text.IndexOf('Article 2')
    if ($idx2 -ge 0) {
        $sub = $text.Substring($idx2, [Math]::Min(5000, $text.Length - $idx2))
        $clean = $sub -replace '<[^>]+>', ' '
        $clean | Out-File 'scratch/art2_extracted.txt' -Encoding utf8
        Write-Output "Article 2 extracted"
    }

    # Find Article 72
    $idx72 = $text.IndexOf('Article 72')
    if ($idx72 -ge 0) {
        $sub = $text.Substring($idx72, [Math]::Min(5000, $text.Length - $idx72))
        $clean = $sub -replace '<[^>]+>', ' '
        $clean | Out-File 'scratch/art72_extracted.txt' -Encoding utf8
        Write-Output "Article 72 extracted"
    }

    # Find Article 73
    $idx73 = $text.IndexOf('Article 73')
    if ($idx73 -ge 0) {
        $sub = $text.Substring($idx73, [Math]::Min(5000, $text.Length - $idx73))
        $clean = $sub -replace '<[^>]+>', ' '
        $clean | Out-File 'scratch/art73_extracted.txt' -Encoding utf8
        Write-Output "Article 73 extracted"
    }
} else {
    Write-Output "scratch/reg_2016_2031.html not found yet"
}
