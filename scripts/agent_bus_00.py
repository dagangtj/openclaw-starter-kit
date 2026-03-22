#!/usr/bin/env python3
"""
OpenClaw 三机通信总线 v1.0
基于MQTT的Agent间实时通信

Topic结构:
  agent/chat          - 通用对话频道（所有机都订阅）
  agent/01/inbox      - 发给01号机的消息
  agent/02/inbox      - 发给02号机的消息
  agent/00/inbox      - 发给00号机的消息
  agent/broadcast     - 广播（所有机都收）
  agent/memory        - 共享记忆同步
  agent/status        - 心跳/状态
"""
import json
import time
import threading
import sqlite3
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# 配置
BROKER_HOST = "100.104.241.24"
MQTT_USER = "openclaw"
MQTT_PASS = "r1CyzsROs3t7UjKNZYVCiw=="  # MQTT认证密码
BROKER_PORT = 1883  # 01号机 Tailscale IP
AGENT_ID = "00"  # 本机ID
DB_PATH = os.path.expanduser("~/.openclaw/workspace/memory/agent_bus.db")

# 颜色输出
def color(text, code): return f"\033[{code}m{text}\033[0m"
GREEN = lambda t: color(t, 32)
YELLOW = lambda t: color(t, 33)
BLUE = lambda t: color(t, 34)
RED = lambda t: color(t, 31)


class AgentMemoryDB:
    """轻量级共享记忆存储（SQLite替代向量DB）"""
    
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                from_agent TEXT,
                topic TEXT,
                content TEXT,
                tags TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shared_memory (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_by TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()
    
    def store_message(self, from_agent, topic, content, tags=None):
        self.conn.execute(
            "INSERT INTO messages (timestamp, from_agent, topic, content, tags) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(), from_agent, topic, content, json.dumps(tags or []))
        )
        self.conn.commit()
    
    def get_recent(self, limit=10, topic=None):
        if topic:
            rows = self.conn.execute(
                "SELECT timestamp, from_agent, topic, content FROM messages WHERE topic=? ORDER BY id DESC LIMIT ?",
                (topic, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT timestamp, from_agent, topic, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return list(reversed(rows))
    
    def set_memory(self, key, value, agent_id):
        self.conn.execute(
            "INSERT OR REPLACE INTO shared_memory (key, value, updated_by, updated_at) VALUES (?,?,?,?)",
            (key, json.dumps(value), agent_id, datetime.now().isoformat())
        )
        self.conn.commit()
    
    def get_memory(self, key):
        row = self.conn.execute(
            "SELECT value, updated_by, updated_at FROM shared_memory WHERE key=?", (key,)
        ).fetchone()
        if row:
            return json.loads(row[0]), row[1], row[2]
        return None, None, None


class AgentBus:
    """Agent通信总线"""
    
    def __init__(self, agent_id, broker_host, broker_port):
        self.agent_id = agent_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.db = AgentMemoryDB(DB_PATH)
        self.handlers = {}
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                   client_id=f"openclaw-{agent_id}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(GREEN(f"[{self.agent_id}] ✅ 已连接到MQTT Broker {self.broker_host}"))
            # 订阅所有相关频道
            subscriptions = [
                f"agent/{self.agent_id}/inbox",  # 专属收件箱
                "agent/broadcast",                # 广播
                "agent/chat",                     # 通用对话
                "agent/memory",                   # 共享记忆
                "agent/status",                   # 状态心跳
            ]
            for topic in subscriptions:
                client.subscribe(topic)
                print(BLUE(f"  订阅: {topic}"))
            
            # 上线公告
            self.publish("agent/status", {
                "type": "online",
                "agent": self.agent_id,
                "time": datetime.now().isoformat()
            })
        else:
            print(RED(f"[{self.agent_id}] ❌ 连接失败: {reason_code}"))
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            from_agent = payload.get("from", "unknown")
            
            # 存入记忆数据库
            self.db.store_message(from_agent, topic, json.dumps(payload))
            
            # 过滤自己发的消息
            if from_agent == self.agent_id:
                return
            
            print(YELLOW(f"[{topic}] {from_agent} → {self.agent_id}: ") + 
                  json.dumps(payload.get("content", payload), ensure_ascii=False)[:200])
            
            # 调用处理器
            handler = self.handlers.get(topic) or self.handlers.get("*")
            if handler:
                handler(topic, from_agent, payload)
                
        except Exception as e:
            print(RED(f"消息处理错误: {e}"))
    
    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(YELLOW(f"[{self.agent_id}] 断开连接，5秒后重连..."))
        time.sleep(5)
        try:
            client.reconnect()
        except:
            pass
    
    def on(self, topic, handler):
        """注册消息处理器"""
        self.handlers[topic] = handler
    
    def publish(self, topic, content):
        """发布消息"""
        payload = {
            "from": self.agent_id,
            "time": datetime.now().isoformat(),
            "content": content
        }
        self.client.publish(topic, json.dumps(payload, ensure_ascii=False))
    
    def broadcast(self, message):
        """广播消息给所有Agent"""
        self.publish("agent/broadcast", message)
    
    def send_to(self, agent_id, message):
        """发送给指定Agent"""
        self.publish(f"agent/{agent_id}/inbox", message)
    
    def sync_memory(self, key, value):
        """同步共享记忆"""
        self.db.set_memory(key, value, self.agent_id)
        self.publish("agent/memory", {"action": "set", "key": key, "value": value})
    
    def start(self, blocking=True):
        """启动总线"""
        self.client.connect(self.broker_host, self.broker_port, 60)
        if blocking:
            self.client.loop_forever()
        else:
            self.client.loop_start()
    
    def stop(self):
        self.publish("agent/status", {"type": "offline", "agent": self.agent_id})
        self.client.loop_stop()
        self.client.disconnect()


def heartbeat_loop(bus):
    """心跳线程"""
    while True:
        time.sleep(60)
        bus.publish("agent/status", {
            "type": "heartbeat",
            "agent": bus.agent_id,
            "time": datetime.now().isoformat()
        })


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 测试模式
        bus = AgentBus(AGENT_ID, BROKER_HOST, BROKER_PORT)
        bus.start(blocking=False)
        time.sleep(2)
        
        # 发送测试消息
        bus.broadcast({"msg": "01号机上线！三机通信总线测试"})
        bus.sync_memory("last_test", {"time": datetime.now().isoformat(), "by": "01"})
        
        time.sleep(2)
        
        # 显示最近消息
        print("\n=== 最近消息 ===")
        for row in bus.db.get_recent(5):
            print(f"[{row[0][:19]}] {row[1]} → {row[2]}: {row[3][:100]}")
        
        bus.stop()
        print("\n✅ 测试完成")
    else:
        # 守护进程模式
        bus = AgentBus(AGENT_ID, BROKER_HOST, BROKER_PORT)
        
        # 处理广播消息
        def handle_broadcast(topic, from_agent, payload):
            print(f"收到广播: {payload}")
        
        bus.on("agent/broadcast", handle_broadcast)
        
        # 心跳线程
        t = threading.Thread(target=heartbeat_loop, args=(bus,), daemon=True)
        t.start()
        
        print(f"🚀 01号机通信总线启动 (Broker: {BROKER_HOST}:{BROKER_PORT})")
        bus.start(blocking=True)
