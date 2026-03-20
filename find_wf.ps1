$json = Get-Content "d:\Apps\energia\energy\live_workflows.json" -Raw | ConvertFrom-Json
$wf = $json | Where-Object { $_.name -like "*Sin Loop*" -or $_.name -like "*Corregido*" }
if ($wf) {
    $wf | Select-Object name, id | ConvertTo-Json
} else {
    Write-Output "No workflow found with 'Sin Loop' or 'Corregido' in the name."
}
