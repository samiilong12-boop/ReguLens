$content = Get-Content "decision_1_2024.html" -Raw -Encoding UTF8

$matches = [regex]::Matches($content, "(?i)TITLE V[\s\S]{1,4000}?Article 21")
if ($matches.Count -gt 0) {
    $clean = $matches[0].Value -replace "<[^>]+>", " "
    $clean = $clean -replace "\s+", " "
    Write-Output $clean
} else {
    Write-Output "TITLE V regex not matched"
}
