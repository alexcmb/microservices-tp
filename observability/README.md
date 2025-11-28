# Microservices Observability - TP n°3

This project implements a comprehensive observability stack for microservices architecture, including:
- Structured JSON logging with correlation IDs (trace-id)
- Prometheus metrics endpoints
- Elastic Stack (ElasticSearch, Kibana, Filebeat, Metricbeat)
- Simulated failure scenarios for testing observability

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Users Service  │────▶│ Products Service │────▶│ Orders Service  │
│    :8000        │     │      :8001       │     │     :8002       │
│   /metrics      │     │    /metrics      │     │   /metrics      │
│   /health       │     │    /health       │     │   /health       │
└────────┬────────┘     └────────┬─────────┘     └────────┬────────┘
         │                       │                        │
         │                       │                        │
         └───────────────────────┼────────────────────────┘
                                 │
                           X-Trace-ID
                                 │
         ┌───────────────────────┼────────────────────────┐
         │                       ▼                        │
         │            ┌─────────────────┐                 │
         │            │    Filebeat     │                 │
         │            │   (DaemonSet)   │                 │
         │            └────────┬────────┘                 │
         │                     │                          │
         │            ┌────────▼────────┐                 │
         │            │  ElasticSearch  │                 │
         │            │     :9200       │                 │
         │            └────────┬────────┘                 │
         │                     │                          │
         │            ┌────────▼────────┐                 │
         │            │     Kibana      │                 │
         │            │     :5601       │                 │
         │            └─────────────────┘                 │
         │                                                │
         │            ┌─────────────────┐                 │
         │            │   Metricbeat    │                 │
         │            │   (DaemonSet)   │                 │
         │            └─────────────────┘                 │
         │                                                │
         └────────────────────────────────────────────────┘
```

## Phase 1: Instrumentation

### Structured JSON Logging

All microservices use Loguru for structured JSON logging with:
- **Levels**: INFO, WARNING, ERROR
- **Correlation IDs**: X-Trace-ID header propagation across services
- **Automatic rotation**: Daily log rotation

Example log entry:
```json
{
  "text": "Request: GET /users/1",
  "record": {
    "level": {"name": "INFO"},
    "extra": {
      "trace_id": "abc123-def456-ghi789",
      "service": "users-service",
      "method": "GET",
      "url": "http://localhost:8000/users/1"
    }
  }
}
```

### Prometheus Metrics Endpoints

Each service exposes `/metrics` endpoint with:
- `http_requests_total`: Counter for total HTTP requests (labels: service, method, endpoint, status)
- `http_request_duration_seconds`: Histogram for request latency
- `http_errors_total`: Counter for HTTP errors (labels: service, endpoint, error_type)
- `external_service_calls_total`: Counter for external service calls (orders-service only)
- `external_service_call_duration_seconds`: Histogram for external call latency

### Failure Scenarios

#### Slow Service Simulation
```bash
# Introduce 3 seconds delay
curl http://localhost:8000/users/slow/3.0
curl http://localhost:8001/products/slow/3.0
curl http://localhost:8002/orders/slow/3.0
```

#### Controlled Error Endpoint
```bash
# Generate HTTP 500 error
curl http://localhost:8000/users/error
curl http://localhost:8001/products/error
curl http://localhost:8002/orders/error
```

#### Cascade Error Testing
```bash
# Test error propagation through services
curl http://localhost:8002/orders/cascade-error
```

### Unit Tests

Each service has pytest unit tests covering:
- Business logic validation
- Error handling
- Endpoint functionality
- Correlation ID propagation

Run tests:
```bash
cd users-service && pytest test_main.py -v
cd products-service && pytest test_main.py -v
cd orders-service && pytest test_main.py -v
```

## Phase 2: Observability Stack Deployment

### Docker Compose (Local Development)

```bash
# Start microservices
docker-compose up -d

# Start Elastic Stack
cd observability
docker-compose -f docker-compose-elastic.yml up -d

# Access:
# - Kibana: http://localhost:5601
# - ElasticSearch: http://localhost:9200
```

### Kubernetes/K3s Deployment

```bash
# Deploy Elastic Stack
kubectl create namespace elastic
kubectl apply -f microk8s/elastic-stack.yaml

# Deploy Filebeat DaemonSet
kubectl apply -f microk8s/filebeat-daemonset.yaml

# Deploy Metricbeat DaemonSet
kubectl apply -f microk8s/metricbeat-daemonset.yaml

# Deploy microservices
kubectl apply -f microk8s/users-deployment.yaml
kubectl apply -f microk8s/products-deployment.yaml
kubectl apply -f microk8s/orders-deployment.yaml

# Access Kibana (port-forward)
kubectl port-forward svc/kibana 5601:5601 -n elastic
```

## RBAC and Security Configuration

### Kubernetes RBAC

Filebeat and Metricbeat require specific RBAC permissions:

**Filebeat ClusterRole:**
- Read access to: namespaces, pods, nodes, replicasets
- Required for pod autodiscovery

**Metricbeat ClusterRole:**
- Read access to: nodes, namespaces, events, pods, services, deployments, replicasets, daemonsets, statefulsets, cronjobs, jobs
- Read access to: nodes/stats for metrics collection

### Secrets Management

```bash
# Create secrets for ElasticSearch credentials
kubectl create secret generic elasticsearch-credentials \
  --from-literal=username=elastic \
  --from-literal=password=your-secure-password \
  -n elastic
```

### Security Best Practices

1. **Never expose ElasticSearch/Kibana publicly** without authentication
2. **Use Kubernetes Network Policies** to restrict access
3. **Enable TLS** for all Elastic Stack components in production
4. **Use sealed-secrets** or external secrets managers for sensitive data
5. **Implement RBAC** for Kibana dashboards
6. **Rotate credentials** regularly

## Kibana Dashboards

### Creating Log Visualization

1. Go to Kibana → Stack Management → Index Patterns
2. Create pattern: `filebeat-*`
3. Set time field: `@timestamp`
4. Go to Discover to view logs

### Useful Kibana Queries

```
# Filter by service
service: "users-service"

# Filter by log level
level: "ERROR"

# Filter by trace ID
trace_id: "your-trace-id"

# Filter errors in time range
level: "ERROR" AND @timestamp:[now-1h TO now]
```

### Metrics Dashboard

1. Go to Kibana → Stack Management → Index Patterns
2. Create pattern: `metricbeat-*`
3. Go to Dashboard → Create Dashboard
4. Add visualizations for CPU, memory, request counts

## File Structure

```
microservices-tp/
├── docker-compose.yml              # Main microservices compose
├── users-service/
│   ├── main.py                     # Instrumented FastAPI app
│   ├── test_main.py                # Unit tests
│   └── requirements.txt            # Dependencies
├── products-service/
│   ├── main.py                     # Instrumented FastAPI app
│   ├── test_main.py                # Unit tests
│   └── requirements.txt            # Dependencies
├── orders-service/
│   ├── main.py                     # Instrumented FastAPI app
│   ├── test_main.py                # Unit tests
│   └── requirements.txt            # Dependencies
├── observability/
│   ├── docker-compose-elastic.yml  # Elastic Stack for Docker
│   ├── filebeat/
│   │   └── filebeat.yml            # Filebeat configuration
│   └── metricbeat/
│       └── metricbeat.yml          # Metricbeat configuration
└── microk8s/
    ├── elastic-stack.yaml          # ElasticSearch + Kibana K8s
    ├── filebeat-daemonset.yaml     # Filebeat DaemonSet
    ├── metricbeat-daemonset.yaml   # Metricbeat DaemonSet
    ├── users-deployment.yaml
    ├── products-deployment.yaml
    └── orders-deployment.yaml
```

## Troubleshooting

### Logs not appearing in Kibana
1. Check Filebeat logs: `docker logs filebeat` or `kubectl logs -n kube-system -l k8s-app=filebeat`
2. Verify ElasticSearch is healthy: `curl http://localhost:9200/_cluster/health`
3. Check index exists: `curl http://localhost:9200/_cat/indices`

### Metrics not appearing
1. Check Metricbeat logs: `docker logs metricbeat` or `kubectl logs -n kube-system -l k8s-app=metricbeat`
2. Verify /metrics endpoint: `curl http://localhost:8000/metrics`

### Correlation ID not propagating
1. Ensure X-Trace-ID header is passed between services
2. Check middleware configuration in each service
