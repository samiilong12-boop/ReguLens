$text = Get-Content 'reg_2019_2072.html' -Raw

$idx = $text.IndexOf('0810')
while ($idx -ge 0) {
    # Check if it has 0810...10
    $snippet = $text.Substring($idx, [Math]::Min(1000, $text.Length - $idx))
    if ($snippet -match '0810.*?10') {
        # Find the preceding Annex heading
        $prevText = $text.Substring([Math]::Max(0, $idx - 8000), [Math]::Min(8000, $idx))
        $annexMatches = [regex]::Matches($prevText, '(?i)(ANNEX\s+[IVXLCDM]+|PART\s+[A-Z])')
        Write-Output "=== PRECEDING HEADINGS ==="
        foreach ($am in $annexMatches) {
            Write-Output $am.Value
        }
        Write-Output "=== SNIPPET ==="
        $cleanSnippet = $snippet -replace '<[^>]+>', ' ' -replace '\s+', ' '
        Write-Output $cleanSnippet.Substring(0, [Math]::Min(400, $cleanSnippet.Length))
        break
    }
    $idx = $text.IndexOf('0810', $idx + 1)
}
