$html = Get-Content -Path "reg_2026_194.html" -Raw
$annexPos = $html.IndexOf('ANNEX I')
$annexText = $html.Substring($annexPos)

# Let's inspect where Egypt is in Annex I table
$egPos = $annexText.IndexOf('Egypt (EG)')
$snippet = $annexText.Substring($egPos - 200, 8000)
# clean tags except tr and td
$snippetClean = [regex]::Replace($snippet, '<td[^>]*>', ' | ')
$snippetClean = [regex]::Replace($snippetClean, '</td>', '')
$snippetClean = [regex]::Replace($snippetClean, '<tr[^>]*>', "`nROW: ")
$snippetClean = [regex]::Replace($snippetClean, '</tr>', '')
$snippetClean = [regex]::Replace($snippetClean, '<[^>]+>', ' ')
$snippetClean = [regex]::Replace($snippetClean, '[ \t]+', ' ')
Write-Output $snippetClean
