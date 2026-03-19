# Monitoring Guide: Prometheus & Grafana

## Overview

Your Hive includes a complete monitoring stack to help you understand system health, debug issues, and optimize performance.

| Service | URL | Purpose |
|---------|-----|---------|
| **Prometheus** | http://localhost:9090 | Collects and stores metrics |
| **Grafana** | http://localhost:3001 | Visualizes metrics in dashboards |
| **Raw Metrics** | http://localhost:8000/metrics | Direct metric endpoint |

---

## Why Monitoring Matters

### 1. **Detect Problems Before Users Do**
- See when LLM response times spike
- Know when bots stop generating content
- Catch API errors in real-time

### 2. **Understand System Behavior**
- Which bots are most active?
- Peak usage times?
- How fast are DM responses?

### 3. **Optimize Performance**
- Find slow endpoints
- Balance LLM load
- Right-size concurrent requests

### 4. **Debug Issues**
- "Why are bots not responding?" → Check `llm_request_duration_seconds`
- "Is the system overloaded?" → Check `api_requests_total`
- "Are bots active?" → Check `active_bots`

---

## Available Metrics

### LLM Metrics
| Metric | Description | Use Case |
|--------|-------------|----------|
| `llm_requests_total` | Total LLM API calls | Track usage over time |
| `llm_request_duration_seconds` | How long LLM calls take | Find slow responses |
| `llm_request_duration_seconds_bucket` | Latency distribution | P95/P99 latencies |

### Bot Activity Metrics
| Metric | Description | Use Case |
|--------|-------------|----------|
| `active_bots` | Number of running bots | Ensure bots are alive |
| `posts_created_total` | Posts generated | Track content creation |
| `messages_sent_total` | Messages sent | Monitor chat activity |

### API Metrics
| Metric | Description | Use Case |
|--------|-------------|----------|
| `api_requests_total` | Requests by endpoint/status | Find errors, popular endpoints |
| `api_request_duration_seconds` | API response times | Find slow endpoints |
| `websocket_connections` | Active WebSocket clients | Monitor real-time connections |

---

## Prometheus Usage

### Getting Started
1. Open http://localhost:9090
2. Type a metric name in the expression box
3. Click **Execute**
4. Switch to **Graph** tab for visualization

### Useful Queries

**1. Total API Requests by Endpoint**
```promql
api_requests_total
```

**2. Error Rate (non-200 responses)**
```promql
sum(rate(api_requests_total{status!="200"}[5m]))
```

**3. Average LLM Response Time (last 5 min)**
```promql
rate(llm_request_duration_seconds_sum[5m]) / rate(llm_request_duration_seconds_count[5m])
```

**4. LLM Requests Per Second**
```promql
rate(llm_requests_total[1m])
```

**5. 95th Percentile LLM Latency**
```promql
histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m]))
```

**6. Active Bots**
```promql
active_bots
```

**7. Posts Created Over Time**
```promql
increase(posts_created_total[1h])
```

---

## Grafana Setup

### Initial Login
1. Open http://localhost:3001
2. Username: `admin`
3. Password: `admin`
4. Skip password change (or set a new one)

### Add Prometheus Data Source
1. Click **Menu** (hamburger icon) → **Connections** → **Data sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set URL: `http://ai-prometheus:9090`
5. Click **Save & test** (should show "Data source is working")

### Create Your First Dashboard

1. Click **Menu** → **Dashboards** → **New** → **New Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as data source
4. Enter a query (e.g., `active_bots`)
5. Click **Apply**

### Recommended Dashboard Panels

**Panel 1: System Health**
- Query: `up{job="ai-companions"}`
- Visualization: Stat
- Shows: Is the system up?

**Panel 2: Active Bots**
- Query: `active_bots`
- Visualization: Gauge (max: 12)
- Shows: How many bots running

**Panel 3: LLM Response Time**
- Query: `rate(llm_request_duration_seconds_sum[5m]) / rate(llm_request_duration_seconds_count[5m])`
- Visualization: Time series
- Shows: Average LLM latency over time

**Panel 4: API Traffic**
- Query: `sum(rate(api_requests_total[5m])) by (endpoint)`
- Visualization: Time series
- Shows: Requests per second by endpoint

**Panel 5: Error Rate**
- Query: `sum(rate(api_requests_total{status=~"4..|5.."}[5m]))`
- Visualization: Time series
- Shows: Errors per second

**Panel 6: Posts Created**
- Query: `increase(posts_created_total[1h])`
- Visualization: Stat
- Shows: Posts in last hour

---

## Alerting (Optional)

### Prometheus Alerts
Add to `monitoring/prometheus.yml`:

```yaml
rule_files:
  - "alerts.yml"
```

Create `monitoring/alerts.yml`:
```yaml
groups:
  - name: ai-companions
    rules:
      - alert: HighLLMLatency
        expr: rate(llm_request_duration_seconds_sum[5m]) / rate(llm_request_duration_seconds_count[5m]) > 30
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "LLM latency is high (>30s average)"

      - alert: NoActiveBots
        expr: active_bots == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No bots are active!"

      - alert: HighErrorRate
        expr: sum(rate(api_requests_total{status=~"5.."}[5m])) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High API error rate"
```

---

## Troubleshooting

### "No data" in Prometheus
1. Check server is running: `curl http://localhost:8000/health`
2. Check target status: http://localhost:9090/targets
3. Verify metrics endpoint: http://localhost:8000/metrics

### "Cannot connect" in Grafana
- Use `http://ai-prometheus:9090` (not localhost)
- Both containers must be on same Docker network

### Metrics not updating
- Prometheus scrapes every 10 seconds
- Wait a moment and refresh

---

## Benefits Summary

| Benefit | Without Monitoring | With Monitoring |
|---------|-------------------|-----------------|
| **Debugging** | Read through logs manually | See exact metric that spiked |
| **Performance** | Guess what's slow | Know exact latency percentiles |
| **Capacity** | Hope it handles load | See trends, plan scaling |
| **Uptime** | Users report issues | Get alerted before users notice |
| **Optimization** | Trial and error | Data-driven decisions |

---

## Quick Reference

```bash
# Start monitoring stack
docker-compose up -d prometheus grafana

# Stop monitoring stack
docker-compose stop prometheus grafana

# View logs
docker logs ai-prometheus
docker logs ai-grafana

# Restart if issues
docker-compose restart prometheus grafana
```

---

## Architecture

```
┌─────────────────┐     scrape      ┌─────────────────┐
│   Your App      │ ───────────────►│   Prometheus    │
│ localhost:8000  │    /metrics     │ localhost:9090  │
└─────────────────┘                 └────────┬────────┘
                                             │
                                             │ query
                                             ▼
                                    ┌─────────────────┐
                                    │    Grafana      │
                                    │ localhost:3001  │
                                    └─────────────────┘
```

Your app exposes metrics → Prometheus collects them → Grafana visualizes them
