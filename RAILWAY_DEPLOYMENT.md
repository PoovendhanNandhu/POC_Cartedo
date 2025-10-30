# 🚂 Railway Deployment Guide

Complete guide to deploy your FastAPI LangGraph application to Railway.

## 📋 Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **Railway CLI**: Install the CLI tool
3. **Git Repository**: Your code should be in a Git repository
4. **OpenAI API Key**: Get it from [platform.openai.com](https://platform.openai.com)

---

## 🚀 Quick Start (Automated)

Use the deployment script for a guided setup:

```bash
./deploy_railway.sh
```

Select option **8** for full automated deployment.

---

## 📦 Manual Deployment

### Step 1: Install Railway CLI

**macOS (Homebrew):**
```bash
brew install railway
```

**npm:**
```bash
npm install -g @railway/cli
```

**Shell script:**
```bash
bash <(curl -fsSL cli.new)
```

### Step 2: Login to Railway

```bash
railway login
```

This will open a browser window for authentication.

### Step 3: Initialize Project

**Option A: Create New Project**
```bash
railway init
```

**Option B: Link Existing Project**
```bash
railway link
```

### Step 4: Set Environment Variables

**From .env file (recommended):**
```bash
# Set each variable manually
railway variables --set OPENAI_API_KEY=sk-...
railway variables --set OPENAI_MODEL=gpt-4o-mini
railway variables --set OPENAI_TEMPERATURE=0
railway variables --set OPENAI_SEED=42
```

**Or use the script:**
```bash
./deploy_railway.sh
# Select option 4
```

**View current variables:**
```bash
railway variables
```

### Step 5: Deploy

```bash
railway up
```

This will:
1. Build your application
2. Install dependencies from `requirements.txt`
3. Start the server using the `Procfile`
4. Provide a public URL

### Step 6: Get Your URL

```bash
railway status
```

Or open the dashboard:
```bash
railway open
```

---

## 🌐 Deploy via GitHub (Recommended)

Railway can automatically deploy from your GitHub repository.

### Step 1: Push to GitHub

```bash
# Initialize git (if not already done)
git init

# Add files
git add .
git commit -m "Initial commit"

# Create repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Step 2: Connect to Railway

1. Go to [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository
5. Railway will automatically detect the `railway.toml` configuration

### Step 3: Add Environment Variables

In the Railway dashboard:
1. Go to your project
2. Click on **"Variables"** tab
3. Add:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `OPENAI_MODEL`: `gpt-4o-mini` (or your preferred model)
   - `OPENAI_TEMPERATURE`: `0`
   - `OPENAI_SEED`: `42`

### Step 4: Deploy

Railway will automatically deploy your application. Each push to `main` will trigger a new deployment.

---

## 📝 Configuration Files

### `railway.toml`
Main configuration file for Railway deployment:
```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install --upgrade pip && pip install -r requirements.txt"

[deploy]
startCommand = "uvicorn src.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### `Procfile`
Process definition for Railway:
```
web: uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

### `runtime.txt`
Python version specification:
```
python-3.13.5
```

---

## 🔐 Environment Variables

Required environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | `sk-proj-...` |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Temperature for generation | `0` |
| `OPENAI_SEED` | Seed for reproducibility | `42` |
| `PORT` | Port to run on (auto-set by Railway) | `8000` |

---

## 🛠️ Useful Commands

### View Logs
```bash
railway logs
```

### Check Status
```bash
railway status
```

### Open Dashboard
```bash
railway open
```

### Run Commands in Railway Environment
```bash
railway run python your_script.py
```

### Environment Management
```bash
# List all variables
railway variables

# Set a variable
railway variables --set KEY=VALUE

# Delete a variable
railway variables --unset KEY
```

### Rollback Deployment
```bash
railway rollback
```

---

## 🧪 Testing Your Deployment

Once deployed, test your API:

### Health Check
```bash
curl https://your-app.railway.app/api/v1/health
```

Expected response:
```json
{
  "status": "OK",
  "version": "1.0.0",
  "timestamp": "2025-10-30T16:00:00Z"
}
```

### API Documentation
Visit: `https://your-app.railway.app/docs`

### Test Transform Endpoint
```bash
curl -X POST https://your-app.railway.app/api/v1/transform/stream-openai \
  -H "Content-Type: application/json" \
  -d '{
    "input_json": {...},
    "selected_scenario": 1
  }' \
  --no-buffer
```

---

## 🔧 Troubleshooting

### Build Fails

**Check logs:**
```bash
railway logs
```

**Common issues:**
- Missing dependencies in `requirements.txt`
- Python version mismatch
- Environment variables not set

### Application Crashes

**Check if variables are set:**
```bash
railway variables
```

**Verify OpenAI API key:**
```bash
railway run python -c "import os; print(os.environ.get('OPENAI_API_KEY'))"
```

### Port Issues

Railway automatically sets the `PORT` environment variable. Make sure your app uses it:
```python
import os
port = int(os.environ.get("PORT", 8000))
```

### Import Errors

Ensure all dependencies are in `requirements.txt`:
```bash
pip freeze > requirements.txt
```

---

## 💰 Pricing

Railway offers:
- **Hobby Plan**: $5/month with $5 usage included
- **Free Trial**: Available for new users

Monitor your usage in the Railway dashboard.

---

## 🔒 Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`
2. **Use Railway secrets** for sensitive data
3. **Rotate API keys** regularly
4. **Enable CORS** properly in production
5. **Use HTTPS** only (automatic with Railway)

---

## 📊 Monitoring

### Built-in Monitoring
Railway provides:
- CPU usage
- Memory usage
- Request metrics
- Error logs

Access via dashboard: `railway open`

### Custom Logging
Your application logs are available:
```bash
railway logs --follow
```

---

## 🔄 Continuous Deployment

### Automatic Deployments
When connected to GitHub, Railway auto-deploys on:
- Push to `main` branch
- Pull request merges

### Manual Deployments
```bash
railway up
```

### Deployment Webhooks
Configure in Railway dashboard for external CI/CD integration.

---

## 📱 Deployment Script Options

The `deploy_railway.sh` script provides:

1. **Initialize new project** - Create a new Railway project
2. **Link existing project** - Connect to existing project
3. **Deploy** - Push current code to Railway
4. **Set environment variables** - Configure env vars from .env
5. **View logs** - Check deployment logs
6. **Open dashboard** - Open Railway web interface
7. **Check status** - View deployment status
8. **Full deployment** - Complete automated setup
9. **Exit** - Close the script

---

## 🌟 Next Steps

After successful deployment:

1. **Set up custom domain** (optional)
   ```bash
   railway domain
   ```

2. **Configure monitoring and alerts** in Railway dashboard

3. **Set up staging environment** for testing

4. **Enable automatic deployments** from GitHub

5. **Review and optimize** Railway usage

---

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Railway CLI Reference](https://docs.railway.app/develop/cli)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Railway Community Discord](https://discord.gg/railway)

---

## ❓ Support

### Railway Support
- Documentation: https://docs.railway.app
- Discord: https://discord.gg/railway
- Status: https://status.railway.app

### Application Issues
Check the health endpoint: `/api/v1/health`

View logs:
```bash
railway logs --follow
```

---

**Happy Deploying! 🚀**
