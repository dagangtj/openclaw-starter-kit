#!/bin/bash
# System Health Check Script (Generic Version)
# Quick health check for OpenClaw host system

echo "=== System Health Check $(date) ==="
echo ""

# OS Info
echo "📋 System:"
uname -a 2>/dev/null | head -1
echo ""

# Uptime & Load
echo "⏱️ Uptime & Load:"
uptime 2>/dev/null
echo ""

# Memory
echo "💾 Memory:"
free -h 2>/dev/null || vm_stat 2>/dev/null | head -5
echo ""

# Disk
echo "💿 Disk:"
df -h / 2>/dev/null | tail -1
echo ""

# OpenClaw
echo "🦞 OpenClaw:"
openclaw --version 2>/dev/null || echo "Not installed"
openclaw gateway status 2>/dev/null | grep -E "Runtime|Service|Probe" | head -3
echo ""

# Node
echo "📦 Node.js:"
node --version 2>/dev/null
echo ""

echo "=== Health Check Complete ==="
