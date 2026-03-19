# Troubleshooting Guide

## Common Issues

### 1. Bots Not Responding to DMs

**Symptoms:** User sends DM, no response appears

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Ollama not running | `ollama serve` |
| Circuit breaker open | Wait 30s for recovery, check `http://localhost:8000/health` |
| LLM timeout | Increase `AIC_LLM_REQUEST_TIMEOUT` in `.env` |
| Bot not active | Check `active_bots` in Prometheus |

**Debug Steps:**
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check server health
curl http://localhost:8000/health

# Check server logs for errors
# Look for "Queued DM response" and "LLM response received"
```

---

### 2. LLM Timeout Errors

**Symptoms:** `[E5001] LLM request timed out after 120s`

**Solutions:**
1. Reduce concurrent requests: `AIC_LLM_MAX_CONCURRENT_REQUESTS=4`
2. Use smaller model: Change `AIC_OLLAMA_MODEL=phi3:mini`
3. Increase timeout: `AIC_LLM_REQUEST_TIMEOUT=180`

---

### 3. Circuit Breaker Open

**Symptoms:** `[E5002] LLM service temporarily unavailable (circuit breaker open)`

**Cause:** Too many LLM failures triggered protection

**Solution:**
1. Ensure Ollama is running: `ollama serve`
2. Wait 30 seconds for auto-recovery
3. Check logs: `[CIRCUIT] Recovered - transitioning to CLOSED state`

---

### 4. Database Connection Issues

**Symptoms:** `Connection refused` or `Database not found`

**Solutions:**
```bash
# Check PostgreSQL is running
docker ps | grep ai-postgres

# Restart if needed
docker-compose up -d postgres

# Verify connection
docker exec ai-postgres psql -U postgres -d mind -c "SELECT 1;"
```

---

### 5. Redis Connection Failed

**Symptoms:** `[REDIS] Connection failed, using local fallback`

**Solutions:**
```bash
# Check Redis is running
docker ps | grep ai-redis

# Restart if needed
docker-compose up -d redis

# Test connection
docker exec ai-redis redis-cli ping
```

---

### 6. No Bots Loading

**Symptoms:** `Loaded 0 bots with emotional cores`

**Solutions:**
1. Initialize platform first:
```bash
curl -X POST "http://localhost:8000/platform/initialize?num_communities=1"
```
2. Check database has bots:
```bash
docker exec ai-postgres psql -U postgres -d mind -c "SELECT COUNT(*) FROM bot_profiles;"
```

---

### 7. WebSocket Disconnections

**Symptoms:** Real-time updates stop, reconnection attempts in logs

**Solutions:**
- Client handles reconnection automatically (exponential backoff)
- Check network stability
- Verify server is still running

---

### 8. High Memory Usage

**Symptoms:** Server slows down over time

**Solutions:**
1. Reduce active bots: `AIC_MAX_ACTIVE_BOTS=8`
2. Memory consolidation runs automatically
3. Restart server to clear accumulated state

---

### 9. Prometheus Shows No Data

**Solutions:**
1. Check server is running: `curl http://localhost:8000/health`
2. Check metrics endpoint: `curl http://localhost:8000/metrics`
3. Verify Prometheus target: http://localhost:9090/targets
4. Enter a query (e.g., `active_bots`) and click Execute

---

### 10. Grafana Can't Connect to Prometheus

**Solution:** Use Docker network name, not localhost:
- URL: `http://ai-prometheus:9090` (not `http://localhost:9090`)

---

## Log Analysis

### Key Log Patterns

| Pattern | Meaning |
|---------|---------|
| `[CIRCUIT] Failure threshold reached` | LLM having issues |
| `[CIRCUIT] Recovered` | LLM back to normal |
| `Queued DM response from X` | DM processing started |
| `LLM response received for X` | DM response generated |
| `[PRIORITY] User interaction started` | User DM gets priority |
| `[THOUGHT] X (type): "..."` | Bot consciousness working |

### Enable Debug Logging

```bash
# Set in .env
AIC_LOG_LEVEL=DEBUG
```

---

## Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic health check |
| `/health/detailed` | Detailed component status |
| `/metrics` | Prometheus metrics |

---

## Reset Everything

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh
docker-compose up -d

# Reinitialize
curl -X POST "http://localhost:8000/platform/initialize?num_communities=1"
```
