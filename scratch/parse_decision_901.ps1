$html = Get-Content 'scratch/decision_2026_901.html' -Raw
Write-Output "--- Search 14682 in Decision 2026/901 ---"
[regex]::Matches($html, '(?i).{0,100}14682.{0,100}') | ForEach-Object { $_.Value -replace '<[^>]+>', ' ' }

Write-Output "--- Search 17394 in Decision 2026/901 ---"
[regex]::Matches($html, '(?i).{0,100}17394.{0,100}') | ForEach-Object { $_.Value -replace '<[^>]+>', ' ' }

Write-Output "--- All standards listed in Annex I of Decision 2026/901 ---"
[regex]::Matches($html, '(?i)EN\s+[0-9]+[A-Za-z0-9\-:]*') | Select-Object -Unique | ForEach-Object { $_.Value }
