param (
    [string]$WorkflowId = "mNnJ3JL47Qn4sVkM"
)

$headers = @{
    "X-N8N-API-KEY" = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
}
$url = "http://181.115.47.107:5678/api/v1/workflows/$WorkflowId"

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 20 | Out-File -FilePath "d:\Apps\energia\energy\target_workflow.json" -Encoding utf8
    Write-Output "Successfully fetched workflow $WorkflowId from public IP"
} catch {
    Write-Error "Failed to fetch workflow from public IP: $_"
}
