Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('scratch/gpsr_summary.xlsx')
$sharedStringsEntry = $zip.GetEntry('xl/sharedStrings.xml')
$reader = New-Object System.IO.StreamReader($sharedStringsEntry.Open())
$sharedXml = [xml]$reader.ReadToEnd()
$reader.Close()
$zip.Dispose()

$strings = @()
foreach ($si in $sharedXml.sst.si) {
    if ($si.t) { $strings += $si.t }
    elseif ($si.r) {
        $strings += ($si.r | ForEach-Object { $_.t }) -join ""
    }
}

Write-Output "Total shared strings: $($strings.Count)"
Write-Output "--- Search for 14682 ---"
$strings | Where-Object { $_ -match '14682' }

Write-Output "--- Search for 17394 ---"
$strings | Where-Object { $_ -match '17394' }

Write-Output "--- Search for clothing / textile / children ---"
$strings | Where-Object { $_ -match 'clothing|children|cord|drawstring' } | Select-Object -First 10
