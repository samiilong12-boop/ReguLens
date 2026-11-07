$content = Get-Content "decision_1_2024.html" -Raw -Encoding UTF8

# Find Article 17
$pos = $content.IndexOf("General requirements")
if ($pos -ge 0) {
    $snippet = $content.Substring($pos, [Math]::Min(3000, $content.Length - $pos))
    $clean = $snippet -replace "<[^>]+>", " "
    $clean = $clean -replace "\s+", " "
    Write-Output "=== GENERAL REQUIREMENTS & PROOF OF ORIGIN ==="
    Write-Output $clean
}
