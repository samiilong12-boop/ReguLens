$html = Get-Content 'scratch/gpsr_standards_page.html' -Raw
# Search for mentions of 14682, 17394, or SummaryList
Write-Output "--- Mentions of 14682 ---"
[regex]::Matches($html, '(?i).{0,100}14682.{0,100}') | ForEach-Object { $_.Value -replace '<[^>]+>', ' ' }

Write-Output "--- Mentions of 17394 ---"
[regex]::Matches($html, '(?i).{0,100}17394.{0,100}') | ForEach-Object { $_.Value -replace '<[^>]+>', ' ' }

Write-Output "--- Mentions of PDF or Summary ---"
[regex]::Matches($html, '(?i).{0,100}(?:summary|pdf|implementing).{0,100}') | Select-Object -First 10 | ForEach-Object { $_.Value -replace '<[^>]+>', ' ' }
