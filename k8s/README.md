# Kubernetes deployment (bonus / production path)

`docker compose up` is the acceptance-gate source of truth. These manifests show
how the same stack runs on Kubernetes for production: stateless **api** scaled to
2 replicas behind a Service with an **HPA** (2–8 on 70% CPU), **postgres** and
**redis** with readiness probes, and the **dashboard** on a NodePort. Detection
stays a host/batch job (GPU), feeding events in via the API — so it is not a
cluster workload here.

## Run on a local cluster (kind / minikube)

```bash
# 1. build the app image
docker build -t store-intelligence:local .

# 2. make it available to the cluster
kind load docker-image store-intelligence:local        # kind
# minikube image load store-intelligence:local         # minikube

# 3. deploy
kubectl apply -k k8s/

# 4. watch it come up
kubectl -n storeiq get pods -w

# 5. reach the API / dashboard
kubectl -n storeiq port-forward svc/api 8000:8000
#   dashboard: http://<node-ip>:30850  (NodePort)  or port-forward svc/dashboard 8050:8050
```

## Production notes
- **Secrets**: `DATABASE_URL` / DB password are in a `Secret` here for demo; in a
  real cluster they come from a secrets manager (e.g. External Secrets / Vault).
- **Postgres**: shown as a Deployment for brevity; production would use a
  StatefulSet + PVC or a managed database.
- **Ingress**: add an Ingress in front of the `api` and `dashboard` Services for
  TLS + host routing.
- **Health**: the `/health` endpoint backs both readiness and liveness probes.
