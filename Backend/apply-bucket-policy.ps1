# Apply bucket policy to S3 bucket for public read access
$bucketName = "assessment-drafting-engine"
$policyFile = ".\s3-bucket-policy.json"

Write-Host "Applying bucket policy to: $bucketName" -ForegroundColor Cyan

try {
    aws s3api put-bucket-policy `
        --bucket $bucketName `
        --policy file://$policyFile `
        --region ap-south-1
    
    Write-Host "✓ Bucket policy applied successfully!" -ForegroundColor Green
    
    # Verify
    Write-Host "`nVerifying bucket policy..." -ForegroundColor Cyan
    $policy = aws s3api get-bucket-policy --bucket $bucketName --region ap-south-1 | ConvertFrom-Json
    Write-Host ($policy | ConvertTo-Json -Depth 10) -ForegroundColor Green
}
catch {
    Write-Host "✗ Error applying bucket policy: $_" -ForegroundColor Red
    exit 1
}
