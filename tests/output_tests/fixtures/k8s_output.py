"""Realistic kubectl output fixtures."""

# ---------------------------------------------------------------------------
# kubectl get pods — 13 pods, 1 CrashLoopBackOff, 1 Completed, rest Running
# ---------------------------------------------------------------------------

GET_PODS = """\
NAME                                      READY   STATUS             RESTARTS   AGE
api-server-7d4f8b9c6-xk2pn                1/1     Running            0          2d
api-server-7d4f8b9c6-zr8qt                1/1     Running            0          2d
worker-5b9c7d4f8-mn3vp                    1/1     Running            2          5d
worker-5b9c7d4f8-qw7xs                    1/1     Running            0          5d
worker-5b9c7d4f8-rv1ky                    1/1     Running            0          5d
scheduler-6c8d9e5f4-hp4lm                 1/1     Running            0          3d
cache-redis-0                             1/1     Running            0          7d
cache-redis-1                             1/1     Running            0          7d
db-postgres-0                             1/1     Running            0          10d
db-postgres-1                             1/1     Running            0          10d
ingress-nginx-controller-8f7b6c5d4-wj9nt  1/1     Running            0          14d
payment-svc-9e8f7a6b5-crash               0/1     CrashLoopBackOff   47         1h
batch-job-exporter-4k7m2                  0/1     Completed          0          6h
"""

# ---------------------------------------------------------------------------
# kubectl get pods — 3 pods all Running
# ---------------------------------------------------------------------------

GET_PODS_ALL_HEALTHY = """\
NAME                           READY   STATUS    RESTARTS   AGE
web-frontend-6d5c4b3a2-abc12   1/1     Running   0          1d
web-frontend-6d5c4b3a2-def34   1/1     Running   0          1d
web-frontend-6d5c4b3a2-ghi56   1/1     Running   0          1d
"""

# ---------------------------------------------------------------------------
# kubectl get services — 3 services
# ---------------------------------------------------------------------------

GET_SERVICES = """\
NAME            TYPE           CLUSTER-IP      EXTERNAL-IP      PORT(S)        AGE
api-server      ClusterIP      10.96.14.32     <none>           8080/TCP       2d
payment-svc     ClusterIP      10.96.87.15     <none>           3000/TCP       5d
ingress-nginx   LoadBalancer   10.96.200.5     203.0.113.42     80:32080/TCP   14d
"""

# ---------------------------------------------------------------------------
# kubectl describe pod — unhealthy pod with CrashLoopBackOff
# ---------------------------------------------------------------------------

DESCRIBE_POD = """\
Name:             payment-svc-9e8f7a6b5-crash
Namespace:        production
Priority:         0
Node:             node-3.example.com/10.0.0.13
Start Time:       Sun, 13 Apr 2026 10:22:00 +0000
Labels:           app=payment-svc
                  pod-template-hash=9e8f7a6b5
Annotations:      kubectl.kubernetes.io/last-applied-configuration:
                    {"apiVersion":"apps/v1","kind":"Deployment","metadata":{"annotations":{},"name":"payment-svc","namespace":"production"},"spec":{"replicas":1,"selector":{"matchLabels":{"app":"payment-svc"}},"template":{"metadata":{"labels":{"app":"payment-svc"}},"spec":{"containers":[{"image":"payment-svc:v1.2.3","name":"payment-svc","ports":[{"containerPort":3000}]}]}}}}
                  kubernetes.io/config.seen: "2026-04-13T10:22:00.000000000Z"
Status:           Running
IP:               10.244.3.47
IPs:
  IP:           10.244.3.47
Controlled By:  ReplicaSet/payment-svc-9e8f7a6b5
Containers:
  payment-svc:
    Container ID:   containerd://a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2
    Image:          payment-svc:v1.2.3
    Image ID:       docker.io/library/payment-svc@sha256:deadbeef
    Port:           3000/TCP
    Host Port:      0/TCP
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Sun, 13 Apr 2026 11:45:00 +0000
      Finished:     Sun, 13 Apr 2026 11:45:03 +0000
    Ready:          False
    Restart Count:  47
    Limits:
      cpu:     500m
      memory:  512Mi
    Requests:
      cpu:     250m
      memory:  256Mi
    Environment:
      DATABASE_URL:  <set to the key 'database-url' in secret 'payment-secrets'>  Optional: false
      LOG_LEVEL:     info
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-xk2pn (ro)
Conditions:
  Type              Status
  Initialized       True
  Ready             False
  ContainersReady   False
  PodScheduled      True
Volumes:
  kube-api-access-xk2pn:
    Type:                    Projected (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  3607
    ConfigMapName:           kube-root-ca.crt
    ConfigMapOptional:       <nil>
    DownwardAPI:             true
QoS Class:                   Burstable
Node-Selectors:              <none>
Tolerations:                 node.kubernetes.io/not-ready:NoExecute op=Exists for 300s
Events:
  Type     Reason     Age                   From               Message
  ----     ------     ----                  ----               -------
  Normal   Scheduled  61m                   default-scheduler  Successfully assigned production/payment-svc-9e8f7a6b5-crash to node-3.example.com
  Normal   Pulled     61m                   kubelet            Container image "payment-svc:v1.2.3" already present on machine
  Normal   Created    61m (x48 over 61m)    kubelet            Created container payment-svc
  Normal   Started    61m (x48 over 61m)    kubelet            Started container payment-svc
  Warning  BackOff    2m (x238 over 60m)    kubelet            Back-off restarting failed container payment-svc in pod payment-svc-9e8f7a6b5-crash_production(abc123)
"""

# ---------------------------------------------------------------------------
# kubectl logs — 70+ lines with 2 ERROR lines in the middle
# ---------------------------------------------------------------------------

LOGS_WITH_ERRORS = """\
2026-04-13T10:00:00.001Z INFO  Starting payment-svc v1.2.3
2026-04-13T10:00:00.123Z INFO  Loading configuration from environment
2026-04-13T10:00:00.245Z INFO  Connecting to database at postgres:5432
2026-04-13T10:00:00.512Z INFO  Database connection established
2026-04-13T10:00:00.634Z INFO  Initializing payment gateway client
2026-04-13T10:00:00.756Z INFO  Payment gateway ready
2026-04-13T10:00:00.878Z INFO  Starting HTTP server on :3000
2026-04-13T10:00:01.000Z INFO  Server ready to accept connections
2026-04-13T10:00:01.200Z INFO  Health check endpoint registered at /health
2026-04-13T10:00:01.300Z INFO  Metrics endpoint registered at /metrics
2026-04-13T10:00:05.001Z INFO  Received POST /payments request id=req-001
2026-04-13T10:00:05.050Z INFO  Validating payment payload
2026-04-13T10:00:05.100Z INFO  Payment validated successfully
2026-04-13T10:00:05.200Z INFO  Processing payment amount=99.99 currency=USD
2026-04-13T10:00:05.350Z INFO  Payment processed successfully tx_id=txn-abc123
2026-04-13T10:00:10.000Z INFO  Received POST /payments request id=req-002
2026-04-13T10:00:10.050Z INFO  Validating payment payload
2026-04-13T10:00:10.100Z INFO  Payment validated successfully
2026-04-13T10:00:10.200Z INFO  Processing payment amount=49.99 currency=USD
2026-04-13T10:00:10.350Z INFO  Payment processed successfully tx_id=txn-def456
2026-04-13T10:00:15.000Z INFO  Received POST /payments request id=req-003
2026-04-13T10:00:15.050Z INFO  Validating payment payload
2026-04-13T10:00:15.100Z INFO  Payment validated successfully
2026-04-13T10:00:15.200Z INFO  Processing payment amount=199.00 currency=USD
2026-04-13T10:00:15.350Z INFO  Payment processed successfully tx_id=txn-ghi789
2026-04-13T10:00:20.000Z INFO  Received POST /payments request id=req-004
2026-04-13T10:00:20.050Z INFO  Validating payment payload
2026-04-13T10:00:20.100Z INFO  Payment validated successfully
2026-04-13T10:00:20.200Z INFO  Processing payment amount=25.00 currency=USD
2026-04-13T10:00:20.350Z INFO  Payment processed successfully tx_id=txn-jkl012
2026-04-13T10:00:25.000Z INFO  Received POST /payments request id=req-005
2026-04-13T10:00:25.050Z INFO  Validating payment payload
2026-04-13T10:00:25.100Z INFO  Payment validated successfully
2026-04-13T10:00:25.200Z INFO  Processing payment amount=75.50 currency=USD
2026-04-13T10:00:25.350Z INFO  Payment processed successfully tx_id=txn-mno345
2026-04-13T10:00:30.001Z INFO  Received POST /payments request id=req-006
2026-04-13T10:00:30.050Z INFO  Validating payment payload
2026-04-13T10:00:30.100Z INFO  Payment validated successfully
2026-04-13T10:00:30.200Z ERROR Failed to connect to payment gateway: connection refused after 3 retries
2026-04-13T10:00:30.201Z INFO  Queuing payment for retry tx_id=txn-pqr678
2026-04-13T10:00:30.202Z INFO  Payment queued successfully
2026-04-13T10:00:35.000Z INFO  Received POST /payments request id=req-007
2026-04-13T10:00:35.050Z INFO  Validating payment payload
2026-04-13T10:00:35.100Z INFO  Payment validated successfully
2026-04-13T10:00:35.200Z INFO  Processing payment amount=300.00 currency=USD
2026-04-13T10:00:35.350Z INFO  Payment processed successfully tx_id=txn-stu901
2026-04-13T10:00:40.000Z INFO  Received POST /payments request id=req-008
2026-04-13T10:00:40.050Z INFO  Validating payment payload
2026-04-13T10:00:40.100Z INFO  Payment validated successfully
2026-04-13T10:00:40.200Z INFO  Processing payment amount=12.99 currency=USD
2026-04-13T10:00:40.350Z INFO  Payment processed successfully tx_id=txn-vwx234
2026-04-13T10:00:45.000Z INFO  Received GET /health request
2026-04-13T10:00:45.010Z INFO  Health check passed
2026-04-13T10:00:50.000Z INFO  Received POST /payments request id=req-009
2026-04-13T10:00:50.050Z INFO  Validating payment payload
2026-04-13T10:00:50.100Z ERROR Payment validation failed: card number checksum mismatch req_id=req-009
2026-04-13T10:00:50.101Z INFO  Returning 400 to client
2026-04-13T10:00:50.102Z INFO  Request completed req_id=req-009 status=400
2026-04-13T10:00:55.000Z INFO  Received POST /payments request id=req-010
2026-04-13T10:00:55.050Z INFO  Validating payment payload
2026-04-13T10:00:55.100Z INFO  Payment validated successfully
2026-04-13T10:00:55.200Z INFO  Processing payment amount=500.00 currency=USD
2026-04-13T10:00:55.350Z INFO  Payment processed successfully tx_id=txn-yza567
2026-04-13T10:01:00.000Z INFO  Received GET /metrics request
2026-04-13T10:01:00.020Z INFO  Metrics served successfully
2026-04-13T10:01:05.000Z INFO  Running scheduled retry job
2026-04-13T10:01:05.100Z INFO  Retry job found 1 pending payment
2026-04-13T10:01:05.200Z INFO  Retrying payment tx_id=txn-pqr678
2026-04-13T10:01:05.350Z INFO  Retry successful tx_id=txn-pqr678
2026-04-13T10:01:10.000Z INFO  Received SIGTERM signal
2026-04-13T10:01:10.010Z INFO  Graceful shutdown initiated
2026-04-13T10:01:10.100Z INFO  Stopping HTTP server
2026-04-13T10:01:10.200Z INFO  Waiting for in-flight requests to complete
2026-04-13T10:01:10.500Z INFO  All requests completed
2026-04-13T10:01:10.600Z INFO  Closing database connection
2026-04-13T10:01:10.700Z INFO  Shutdown complete
"""
