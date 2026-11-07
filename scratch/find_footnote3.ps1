$html = Get-Content -Path "reg_2026_194.html" -Raw
$fn3Match = [regex]::Match($html, '(?s)<a id="ntr3-L_202600194EN\.000602-E0003"[^>]*>.*?</div>')
if (-not $fn3Match.Success) {
    $fn3Match = [regex]::Match($html, '(?s)<div[^>]*id="ntr3-L_202600194EN[^>]*>.*?</div>')
}
Write-Output "FOOTNOTE 3:"
Write-Output $fn3Match.Value
