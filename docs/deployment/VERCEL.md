# Vercel Deployment Guide - Queen Portal

This guide covers deploying the Queen observation portal to Vercel.

## Prerequisites

- Vercel account (free tier works)
- Backend API deployed and accessible (see [production.md](./production.md))
- Git repository connected to Vercel

## Quick Deploy

### Option 1: Vercel Dashboard

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your Git repository
3. Set the **Root Directory** to `queen`
4. Configure environment variables (see below)
5. Click **Deploy**

### Option 2: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Navigate to queen directory
cd queen

# Deploy (first time - will prompt for configuration)
vercel

# Deploy to production
vercel --prod
```

## Environment Variables

Configure these in Vercel Dashboard > Project Settings > Environment Variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL | `https://api.yourserver.com` |
| `NEXT_PUBLIC_WS_URL` | No | WebSocket URL (if different) | `wss://api.yourserver.com` |

### Setting Environment Variables

**Via Dashboard:**
1. Go to Project Settings > Environment Variables
2. Add each variable with appropriate scope (Production, Preview, Development)

**Via CLI:**
```bash
vercel env add NEXT_PUBLIC_API_URL
# Enter the value when prompted
```

## Project Configuration

The `vercel.json` in the `queen/` directory includes:

- **Framework**: Next.js (auto-detected)
- **Build Command**: `npm run build`
- **Output Directory**: `.next`
- **Security Headers**: XSS protection, frame denial, content type sniffing prevention
- **API Rewrites**: Routes `/api/*` requests to your backend

## Build Settings

Vercel auto-detects Next.js settings, but ensure these are configured:

| Setting | Value |
|---------|-------|
| Framework Preset | Next.js |
| Root Directory | `queen` |
| Build Command | `npm run build` |
| Output Directory | `.next` |
| Install Command | `npm install` |
| Node.js Version | 18.x or 20.x |

## API Proxy Configuration

The portal proxies API requests to your backend. The rewrite rule in `vercel.json`:

```json
{
  "source": "/api/:path*",
  "destination": "${NEXT_PUBLIC_API_URL}/:path*"
}
```

This means:
- Frontend calls `/api/civilization`
- Vercel rewrites to `https://your-api.com/civilization`
- No CORS issues, backend URL hidden from client

### Backend CORS

Your backend should allow requests from your Vercel domain:

```python
# In mind/api/main.py or similar
AIC_CORS_ORIGINS=https://your-project.vercel.app,https://your-custom-domain.com
```

## Custom Domain

1. Go to Project Settings > Domains
2. Add your domain (e.g., `observe.yourdomain.com`)
3. Configure DNS as instructed:
   - **CNAME**: Point to `cname.vercel-dns.com`
   - Or **A record**: Point to Vercel's IP addresses
4. SSL certificate is auto-provisioned

## Deployment Workflow

### Automatic Deployments

Vercel deploys automatically on:
- **Production**: Pushes to `main` branch
- **Preview**: Pull requests and other branches

### Manual Deployments

```bash
# Preview deployment
vercel

# Production deployment
vercel --prod

# Redeploy specific commit
vercel --prod --force
```

## Performance Optimization

### Edge Caching

Static pages are automatically cached at the edge. For dynamic pages, add caching headers in your API routes or use ISR.

### Image Optimization

Next.js Image Optimization is enabled by default. Configure remote patterns if loading external images:

```typescript
// next.config.ts
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'your-media-cdn.com',
      },
    ],
  },
};
```

## Monitoring

### Vercel Analytics

Enable in Project Settings > Analytics for:
- Web Vitals (LCP, FID, CLS)
- Page views
- Geographic distribution

### Logs

View function logs in:
- Vercel Dashboard > Deployments > [deployment] > Functions
- Or via CLI: `vercel logs`

## Troubleshooting

### Build Failures

1. Check Node.js version compatibility (use 18.x or 20.x)
2. Ensure all dependencies in `package.json`
3. Check build logs for specific errors

### API Connection Issues

1. Verify `NEXT_PUBLIC_API_URL` is set correctly
2. Check backend CORS allows Vercel domain
3. Ensure backend is accessible from Vercel's network

### Environment Variables Not Working

- `NEXT_PUBLIC_*` variables are exposed to the browser
- Non-prefixed variables are server-side only
- Redeploy after adding/changing variables

### Preview Deployments

Preview deployments get unique URLs. Ensure your backend CORS handles:
- `https://your-project.vercel.app` (production)
- `https://your-project-*-your-team.vercel.app` (previews)

## Security Considerations

1. **Never commit secrets** - Use Vercel environment variables
2. **API URL exposure** - `NEXT_PUBLIC_*` vars are visible in client bundle
3. **Backend protection** - Implement rate limiting on your API
4. **Domain verification** - Use Vercel's built-in SSL

## Cost Optimization

Free tier includes:
- Unlimited deployments
- 100GB bandwidth/month
- Serverless function executions

For higher traffic, consider:
- Vercel Pro for higher limits
- CDN for static assets
- Edge functions for API routes

## Related Documentation

- [Production Deployment](./production.md) - Backend deployment
- [Docker Deployment](./docker.md) - Containerized deployment
- [Scaling Guide](./scaling.md) - Scaling considerations
