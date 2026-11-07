$html = Get-Content -Path "scratch/decision_2026_901.html" -Raw

# Article 1
$art1Match = [regex]::Match($html, '(?s)<div class="eli-subdivision" id="art_1">.*?</div>')
Write-Output "--- ARTICLE 1 ---"
$art1Clean = [regex]::Replace($art1Match.Value, '<[^>]+>', ' ')
$art1Clean = [regex]::Replace($art1Clean, '\s+', ' ').Trim()
Write-Output $art1Clean

# Annex I Entry 37
$entry37Match = [regex]::Match($html, '(?s)<tr[^>]*>.*?<p[^>]*>37</p>.*?</tr>')
Write-Output "--- ENTRY 37 ---"
$entry37Clean = [regex]::Replace($entry37Match.Value, '<[^>]+>', ' ')
$entry37Clean = [regex]::Replace($entry37Clean, '\s+', ' ').Trim()
Write-Output $entry37Clean
Write-Output "--- ENTRY 37 RAW HTML ---"
Write-Output $entry37Match.Value

# Article 2
$art2Match = [regex]::Match($html, '(?s)<div class="eli-subdivision" id="art_2">.*?</div>')
Write-Output "--- ARTICLE 2 ---"
$art2Clean = [regex]::Replace($art2Match.Value, '<[^>]+>', ' ')
$art2Clean = [regex]::Replace($art2Clean, '\s+', ' ').Trim()
Write-Output $art2Clean

# Annex II text / table headers / first rows
$annex2Pos = $html.IndexOf('id="anx_II"')
if ($annex2Pos -gt 0) {
    $annex2Text = $html.Substring($annex2Pos, 3000)
    $clean2 = [regex]::Replace($annex2Text, '<[^>]+>', ' ')
    $clean2 = [regex]::Replace($clean2, '\s+', ' ').Trim()
    Write-Output "--- ANNEX II SNIPPET ---"
    Write-Output $clean2
}
