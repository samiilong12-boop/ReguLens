$content = Get-Content "decision_1_2024.html" -Raw -Encoding UTF8

$regex = [regex]"(?i)<p[^>]*class=""(?:ti-art|title-article|normal)""[^>]*>(?:Article\s+\d+|TITLE\s+[IVXLCDM]+)[\s\S]*?</p>"
$m = $regex.Matches($content)
Write-Output "Found $($m.Count) matches"
for ($i = 0; $i -lt [Math]::Min(25, $m.Count); $i++) {
    $c = $m[$i].Value -replace "<[^>]+>", " "
    $c = $c -replace "\s+", " "
    Write-Output $c
}
