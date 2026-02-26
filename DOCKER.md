# Docker Build

## Cloud build

```bash
docker build -t fastcode:test .
```

## Local build (behind corporate SSL proxy)

```bash
just build-local-macos
```

Or manually:

### Step 1 — extract the corporate CA

```bash
# Search all keychains (covers MDM-distributed corporate CAs)
security find-certificate -a -p > /tmp/corp-ca.pem
```

### Step 2 — build

```bash
docker build \
  --build-arg CERT=1 \
  --secret id=corporate_ca,src=/tmp/corp-ca.pem \
  -t fastcode:test .
```

Keep `--build-arg CERT=1 --secret ...` on every local build.
Re-run Step 1 only if the corporate CA rotates.
