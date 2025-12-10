# 🚀 Deployment Tools

This folder contains all the deployment and monitoring tools for the Anarcho Capital Trading System.

## 📁 Files Overview

### `deploy_production.py`
**Production Deployment Script**
- Comprehensive pre-deployment validation
- Environment variable checks
- Dependency installation
- Configuration validation
- System health tests
- Wallet connection verification
- API connectivity checks

**Usage:**
```bash
python deploy/deploy_production.py
```

### `system_health_dashboard.py`
**Real-time System Health Dashboard**
- Live system monitoring
- Agent status tracking
- Wallet balance monitoring
- Position summary display
- Trading metrics visualization
- Alert system
- Health report export

**Usage:**
```bash
python deploy/system_health_dashboard.py
```

**Export health report:**
```bash
python deploy/system_health_dashboard.py --export
```

### `app.py`
**Web Application Server**
- Flask-based webhook server
- Handles incoming webhooks
- Logging and monitoring
- Production-ready web server

**Usage:**
```bash
python deploy/app.py
```

### `build.py`
**Executable Build Script**
- Creates standalone executables
- Cross-platform support
- Automatic icon generation
- Distribution packaging

**Usage:**
```bash
python deploy/build.py
```

## 🔧 Quick Start

1. **Production Deployment:**
   ```bash
   python deploy/deploy_production.py
   ```

2. **Monitor System:**
   ```bash
   python deploy/system_health_dashboard.py
   ```

3. **Build Executable:**
   ```bash
   python deploy/build.py
   ```

4. **Start Web Server:**
   ```bash
   python deploy/app.py
   ```

## 📋 Deployment Checklist

- [ ] Environment variables configured (.env file)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Wallet funded with minimum balance
- [ ] API keys configured and tested
- [ ] Run deployment validation script
- [ ] Monitor system health dashboard
- [ ] Test with small position sizes first

## 🛡️ Safety Features

All deployment tools include:
- Input validation
- Error handling
- Safety checks
- Rollback capabilities
- Monitoring and alerting
- Comprehensive logging

## 📊 Monitoring

The system provides multiple monitoring options:
- Real-time health dashboard
- Health report exports
- System metrics tracking
- Error rate monitoring
- Performance analytics

## 🆘 Support

For issues or questions:
1. Check the main README.md
2. Review INSTALL.md for setup instructions
3. Consult PRODUCTION_READINESS_SUMMARY.md for comprehensive deployment guide
4. Monitor system health dashboard for real-time status

---

*Built with love by Anarcho Capital 🌙* 