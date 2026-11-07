$html = Get-Content -Path "reg_2026_194.html" -Raw
$annexPos = $html.IndexOf('ANNEX I')
$annexText = $html.Substring($annexPos)

$sbPos = $annexText.IndexOf('Strawberries')
$beforeSb = $annexText.Substring(0, $sbPos)

# Let's search for all country patterns before Strawberries
$countryMatches = [regex]::Matches($beforeSb, '(?s)<td[^>]*rowspan="\d+"[^>]*>\s*<p class="oj-tbl-txt">\s*<span class="oj-bold">([^<]+)</span>')
foreach ($c in $countryMatches) {
    Write-Output "Country found: $($c.Groups[1].Value)"
}
