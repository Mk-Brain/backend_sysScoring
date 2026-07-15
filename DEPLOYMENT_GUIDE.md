# Render Deployment Checklist

## Before Deploying

### 1. Environment Variables
Set these in Render Dashboard (Settings → Environment):
```
DATABASE_HOST=your-mysql-host.onrender.com
DATABASE_ROOT=your-db-user
DATABASE_PASSWORD=your-secure-password
DATABASE_NAME=your-db-name
SECRET_KEY=your-very-long-random-secret-key
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com
```

### 2. Database Preparation
- Ensure MySQL database is running and accessible from Render
- Alembic migrations run automatically on startup

### 3. Local Testing
```bash
# Build image locally
docker build -t pointage-system:latest .

# Run with environment variables
docker run -e DATABASE_HOST=localhost \
  -e DATABASE_ROOT=admin \
  -e DATABASE_PASSWORD=your-password \
  -e DATABASE_NAME=syteme_pointage \
  -e SECRET_KEY="your-secret" \
  -e ALLOWED_ORIGINS="http://localhost:3000" \
  -p 10000:10000 \
  pointage-system:latest
```

### 4. Git Setup
- Remove .env from history: `git rm --cached .env`
- Verify .gitignore includes .env
- Push to GitHub

### 5. Render Deployment
1. Connect GitHub repository to Render
2. Select this project
3. Ensure "Docker" is selected as Runtime
4. Add all environment variables in Dashboard
5. Deploy

## Monitoring

### Health Check
Access `https://your-render-app.onrender.com/health` to verify the app is running.

### Logs
Monitor logs in Render Dashboard for any migration or startup errors.

### Database Connection Issues
If migrations fail:
- Verify DATABASE_HOST is correct
- Check DATABASE_PASSWORD is exact
- Ensure database user has permission to create tables
- Check network access/firewall rules

## Security Notes

- Never commit .env files
- Use strong SECRET_KEY (minimum 32 characters)
- Use HTTPS for frontend domain in ALLOWED_ORIGINS
- Rotate API keys periodically
- Monitor Render logs for errors
