# Apply CORS policy to S3 bucket
$bucketName = "assessment-drafting-engine"
$corsFile = ".\s3-cors.json"

# Set AWS credentials from environment or config
Write-Host "Applying CORS policy to bucket: $bucketName"

try {
    aws s3api put-bucket-cors `
        --bucket $bucketName `
        --cors-configuration file://$corsFile `
        --region ap-south-1
    
    Write-Host "✓ CORS policy applied successfully!" -ForegroundColor Green
    
    # Verify
    Write-Host "`nVerifying CORS configuration..."
    aws s3api get-bucket-cors --bucket $bucketName --region ap-south-1 | ConvertFrom-Json | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "✗ Error applying CORS policy: $_" -ForegroundColor Red
    Write-Host "Make sure AWS CLI is installed and credentials are configured."
    exit 1
}
