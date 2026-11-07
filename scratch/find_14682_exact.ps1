$html = Get-Content -Path "scratch/decision_2026_901.html" -Raw
$pos14682 = $html.IndexOf('14682')
if ($pos14682 -gt 0) {
    $snippet = $html.Substring($pos14682 - 300, 700)
    Write-Output "--- 14682 SNIPPET ---"
    Write-Output $snippet
    $clean = [regex]::Replace($snippet, '<[^>]+>', ' ')
    $clean = [regex]::Replace($clean, '\s+', ' ').Trim()
    Write-Output "--- CLEAN ---"
    Write-Output $clean
} else {
    Write-Output "14682 not found"
}
