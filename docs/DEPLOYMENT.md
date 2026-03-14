# Vaultrix Deployment Guide

Complete guide for deploying Vaultrix to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Docker Deployment](#local-docker-deployment)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Provider Deployments](#cloud-provider-deployments)
6. [Security Considerations](#security-considerations)
7. [Monitoring & Logging](#monitoring--logging)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Docker**: 20.10 or higher
- **Docker Compose**: 2.0 or higher (for compose deployment)
- **Kubernetes**: 1.24+ (for k8s deployment)
- **Python**: 3.10+ (for local development)

### System Requirements

**Minimum** (Single Instance):
- 2 CPU cores
- 2GB RAM
- 20GB disk space
- Linux kernel 3.10+ (for Docker)

**Recommended** (Production):
- 4+ CPU cores
- 8GB+ RAM
- 100GB+ disk space (for sandbox images)
- Load balancer for multiple instances

---

## Local Docker Deployment

### 1. Build the Docker Image

```bash
cd vaultrix
docker build -t vaultrix:latest .
```

### 2. Run the Container

```bash
docker run -d \
  --name vaultrix \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/workspace:/workspace \
  -e VAULTRIX_ENV=production \
  vaultrix:latest
```

### 3. Verify Deployment

```bash
# Check container status
docker ps | grep vaultrix

# View logs
docker logs vaultrix

# Test the application
docker exec vaultrix vaultrix info
```

---

## Docker Compose Deployment

### 1. Configure Environment

Create `.env` file:

```bash
VAULTRIX_ENV=production
VAULTRIX_LOG_LEVEL=INFO
DOCKER_REGISTRY=ghcr.io/yourusername
```

### 2. Deploy with Compose

```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f vaultrix

# Stop services
docker-compose down
```

### 3. Update Deployment

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d
```

---

## Kubernetes Deployment

### 1. Prerequisites

- kubectl configured and connected to cluster
- Sufficient cluster resources
- Container registry access

### 2. Deploy to Kubernetes

```bash
# Create namespace and deploy
kubectl apply -f kubernetes/deployment.yaml

# Check deployment status
kubectl get pods -n vaultrix

# Check services
kubectl get svc -n vaultrix

# View logs
kubectl logs -n vaultrix -l app=vaultrix --tail=100 -f
```

### 3. Scaling

```bash
# Manual scaling
kubectl scale deployment vaultrix -n vaultrix --replicas=5

# Check autoscaler
kubectl get hpa -n vaultrix
```

### 4. Update Deployment

```bash
# Update image
kubectl set image deployment/vaultrix \
  vaultrix=ghcr.io/yourusername/vaultrix:v0.2.0 \
  -n vaultrix

# Check rollout status
kubectl rollout status deployment/vaultrix -n vaultrix

# Rollback if needed
kubectl rollout undo deployment/vaultrix -n vaultrix
```

---

## Cloud Provider Deployments

### AWS ECS

```bash
# 1. Build and push image to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker tag vaultrix:latest <account>.dkr.ecr.us-east-1.amazonaws.com/vaultrix:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/vaultrix:latest

# 2. Create ECS task definition
# See aws/ecs-task-definition.json

# 3. Create ECS service
aws ecs create-service \
  --cluster vaultrix-cluster \
  --service-name vaultrix \
  --task-definition vaultrix:1 \
  --desired-count 3
```

### Google Cloud Run

```bash
# 1. Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT-ID/vaultrix

# 2. Deploy to Cloud Run
gcloud run deploy vaultrix \
  --image gcr.io/PROJECT-ID/vaultrix \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2
```

### Azure Container Instances

```bash
# 1. Push to ACR
az acr build --registry <registry-name> --image vaultrix:latest .

# 2. Deploy to ACI
az container create \
  --resource-group vaultrix-rg \
  --name vaultrix \
  --image <registry-name>.azurecr.io/vaultrix:latest \
  --cpu 2 \
  --memory 2
```

---

## Security Considerations

### 1. Image Security

**Scan for vulnerabilities**:

```bash
# Using Trivy
trivy image vaultrix:latest

# Using Docker Scout
docker scout cves vaultrix:latest
```

**Best practices**:
- ✅ Use specific version tags (not `latest` in production)
- ✅ Run containers as non-root user
- ✅ Use read-only root filesystem where possible
- ✅ Drop unnecessary capabilities
- ✅ Enable security scanning in CI/CD

### 2. Network Security

**Firewall rules**:
```bash
# Only allow necessary ports
- 8080: Application (if web UI enabled)
- Block all other inbound traffic
```

**Network policies** (Kubernetes):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: vaultrix-netpol
  namespace: vaultrix
spec:
  podSelector:
    matchLabels:
      app: vaultrix
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 53  # DNS
        - protocol: UDP
          port: 53  # DNS
```

### 3. Secrets Management

**Do NOT hardcode secrets!**

Use environment variables or secret managers:

```bash
# Kubernetes Secrets
kubectl create secret generic vaultrix-secrets \
  --from-literal=api-key=your-api-key \
  -n vaultrix

# AWS Secrets Manager
aws secretsmanager create-secret \
  --name vaultrix/api-keys \
  --secret-string '{"anthropic":"key123"}'
```

### 4. Access Control

**RBAC for Kubernetes**:
- Limit service account permissions
- Use least-privilege principle
- Regularly audit access logs

**Docker socket access**:
- Mount Docker socket read-only if possible
- Use Docker socket proxy for additional security
- Consider alternatives like Podman

---

## Monitoring & Logging

### 1. Health Checks

**Docker**:
```bash
# Check health
docker inspect --format='{{.State.Health.Status}}' vaultrix
```

**Kubernetes**:
```bash
# Check pod health
kubectl get pods -n vaultrix -o wide
```

### 2. Logging

**Centralized logging with Fluentd**:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/vaultrix*.log
      tag vaultrix.*
      format json
    </source>
    <match vaultrix.**>
      @type elasticsearch
      host elasticsearch.logging.svc
      port 9200
      logstash_format true
    </match>
```

### 3. Metrics

**Prometheus metrics** (future enhancement):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: vaultrix-metrics
  namespace: vaultrix
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
spec:
  ports:
    - port: 9090
      name: metrics
  selector:
    app: vaultrix
```

### 4. Alerting

**Example Prometheus alerts**:

```yaml
groups:
  - name: vaultrix
    rules:
      - alert: VaultrixHighErrorRate
        expr: rate(vaultrix_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Vaultrix"

      - alert: VaultrixDown
        expr: up{job="vaultrix"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Vaultrix is down"
```

---

## Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check logs
docker logs vaultrix

# Common causes:
# - Missing Docker socket mount
# - Insufficient permissions
# - Port conflicts
```

**Fix**:
```bash
# Ensure Docker socket is mounted
docker run -v /var/run/docker.sock:/var/run/docker.sock ...

# Check permissions
ls -l /var/run/docker.sock
```

#### 2. Sandbox Creation Fails

```bash
# Check Docker daemon
docker info

# Check available resources
docker system df
```

**Fix**:
```bash
# Clean up unused images
docker system prune -a

# Increase Docker resources (Docker Desktop)
# Settings -> Resources -> Advanced
```

#### 3. High Memory Usage

```bash
# Check container stats
docker stats vaultrix

# Check for memory leaks
docker exec vaultrix ps aux --sort=-%mem | head
```

**Fix**:
```bash
# Set memory limits
docker run --memory="2g" --memory-swap="2g" vaultrix:latest

# Or in docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 2G
```

#### 4. Permission Denied Errors

```bash
# Check user
docker exec vaultrix whoami

# Check file permissions
docker exec vaultrix ls -la /workspace
```

**Fix**:
```bash
# Run as correct user
docker run --user 1000:1000 vaultrix:latest

# Fix workspace permissions
chmod 755 workspace/
```

### Debug Mode

Enable debug logging:

```bash
# Docker
docker run -e VAULTRIX_LOG_LEVEL=DEBUG vaultrix:latest

# Kubernetes
kubectl set env deployment/vaultrix -n vaultrix VAULTRIX_LOG_LEVEL=DEBUG
```

### Getting Help

1. Check logs: `docker logs vaultrix` or `kubectl logs`
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. Open an issue: https://github.com/yourusername/vaultrix/issues
4. Join Discord: https://discord.gg/vaultrix

---

## Production Checklist

Before going to production:

- [ ] Security scan completed
- [ ] Resource limits configured
- [ ] Health checks enabled
- [ ] Monitoring setup
- [ ] Logging configured
- [ ] Backup strategy defined
- [ ] Disaster recovery plan
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation reviewed
- [ ] Team trained
- [ ] Rollback plan ready

---

## Next Steps

1. **Phase 2**: Deploy VaultHub registry
2. **Phase 3**: Add HITL web dashboard
3. **Phase 4**: Enable encryption features
4. **Monitor**: Track metrics and logs
5. **Scale**: Adjust resources as needed

---

**Vaultrix: Production Ready & Secure** 🔐
