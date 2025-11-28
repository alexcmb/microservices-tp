# Microservices TP - Observability

A microservices architecture with comprehensive observability implementation including structured logging, Prometheus metrics, and Elastic Stack integration.

## Services

| Service | Port | Description |
|---------|------|-------------|
| Users Service | 8000 | User management API |
| Products Service | 8001 | Product catalog API |
| Orders Service | 8002 | Order processing API |

## Features

### Observability (TP n°3)
- ✅ Structured JSON logging with Loguru
- ✅ Correlation IDs (X-Trace-ID) for distributed tracing
- ✅ Prometheus metrics endpoints (/metrics)
- ✅ Simulated failure scenarios (slow/error endpoints)
- ✅ Unit tests with pytest (49 tests total)
- ✅ Elastic Stack deployment (ElasticSearch + Kibana)
- ✅ Filebeat DaemonSet with autodiscover
- ✅ Metricbeat for system/container metrics
- ✅ RBAC configuration for Kubernetes

## Quick Start

### Local Development (Docker Compose)
```bash
# Start microservices
docker-compose up -d

# Start Elastic Stack
cd observability
docker-compose -f docker-compose-elastic.yml up -d
```

### Kubernetes Deployment
```bash
# Deploy Elastic Stack
kubectl apply -f microk8s/elastic-stack.yaml

# Deploy Beats
kubectl apply -f microk8s/filebeat-daemonset.yaml
kubectl apply -f microk8s/metricbeat-daemonset.yaml

# Deploy services
kubectl apply -f microk8s/
```

## API Endpoints

### Standard Endpoints
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

### Users Service (8000)
- `GET /users` - List all users
- `GET /users/{id}` - Get user by ID
- `POST /users/create` - Create new user
- `GET /users/slow/{seconds}` - Slow endpoint simulation
- `GET /users/error` - Error endpoint simulation

### Products Service (8001)
- `GET /products` - List all products
- `GET /products/{id}` - Get product by ID
- `POST /products/create` - Create new product
- `GET /products/slow/{seconds}` - Slow endpoint simulation
- `GET /products/error` - Error endpoint simulation

### Orders Service (8002)
- `GET /orders` - List all orders
- `GET /orders/{id}` - Get order by ID
- `POST /orders/create` - Create new order
- `GET /orders/slow/{seconds}` - Slow endpoint simulation
- `GET /orders/error` - Error endpoint simulation
- `GET /orders/cascade-error` - Cascade error simulation

## Running Tests

```bash
# All services
cd users-service && pytest test_main.py -v
cd products-service && pytest test_main.py -v
cd orders-service && pytest test_main.py -v
```

## Documentation

See [observability/README.md](observability/README.md) for detailed documentation on:
- Instrumentation details
- Elastic Stack deployment
- Kibana dashboard setup
- RBAC and security configuration
- Troubleshooting guide

