$html = Get-Content -Path "reg_2026_194.html" -Raw
$annexPos = $html.IndexOf('ANNEX I')
$annexText = $html.Substring($annexPos)

# Let's search for Strawberries in Annex I and find which country row it belongs to
$sbPos = $annexText.IndexOf('Strawberries')
$beforeSb = $annexText.Substring(0, $sbPos)
$lastCountryPos = $beforeSb.LastIndexOf('span class="oj-bold">')
Write-Output "Country preceding strawberries:"
Write-Output $beforeSb.Substring($lastCountryPos, 150)

$sbSnippet = $annexText.Substring($sbPos - 100, 1000)
$clean = [regex]::Replace($sbSnippet, '<td[^>]*>', ' | ')
$clean = [regex]::Replace($clean, '</td>', '')
$clean = [regex]::Replace($clean, '<tr[^>]*>', "`nROW: ")
$clean = [regex]::Replace($clean, '</tr>', '')
$clean = [regex]::Replace($clean, '<[^>]+>', ' ')
$clean = [regex]::Replace($clean, '[ \t]+', ' ')
Write-Output "`nSTRAWBERRY ROW:"
Write-Output $clean
