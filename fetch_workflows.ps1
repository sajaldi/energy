$headers = @{
    "X-N8N-API-KEY" = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
}
$url = "http://localhost:5678/api/v1/workflows"
try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response.data | ConvertTo-Json -Depth 10 | Out-File -FilePath "d:\Apps\energia\energy\live_workflows.json" -Encoding utf8
    Write-Output "Successfully saved workflows to live_workflows.json"
} catch {
    Write-Error "Failed to fetch workflows: $_"
}
