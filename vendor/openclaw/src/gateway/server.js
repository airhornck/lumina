// OpenClaw Gateway Server - 原始参考实现
// 基于 https://github.com/openclaw/openclaw

const WebSocket = require('ws');
const http = require('http');
const EventEmitter = require('events');

class GatewayServer extends EventEmitter {
    constructor(options = {}) {
        super();
        this.port = options.port || 18789;
        this.sessions = new Map();
        this.router = new MessageRouter();
        this.wss = null;
    }

    async start() {
        const server = http.createServer();
        this.wss = new WebSocket.Server({ server });

        this.wss.on('connection', (ws, req) => {
            const clientId = this.generateClientId();
            this.handleConnection(ws, clientId);
        });

        server.listen(this.port, () => {
            console.log(`OpenClaw Gateway listening on port ${this.port}`);
        });

        return this;
    }

    handleConnection(ws, clientId) {
        console.log(`New connection: ${clientId}`);
        
        // Create session
        const session = new Session(clientId, this, ws);
        this.sessions.set(clientId, session);

        ws.on('message', async (data) => {
            try {
                const message = JSON.parse(data);
                const response = await this.router.route(message, session);
                ws.send(JSON.stringify(response));
            } catch (error) {
                ws.send(JSON.stringify({
                    error: true,
                    message: error.message
                }));
            }
        });

        ws.on('close', () => {
            this.handleDisconnect(clientId);
        });
    }

    handleDisconnect(clientId) {
        const session = this.sessions.get(clientId);
        if (session) {
            session.cleanup();
            this.sessions.delete(clientId);
        }
        console.log(`Disconnected: ${clientId}`);
    }

    generateClientId() {
        return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

class Session {
    constructor(sessionId, gateway, ws) {
        this.sessionId = sessionId;
        this.gateway = gateway;
        this.ws = ws;
        this.context = {};
        this.lockedSop = null;
        this.history = [];
        this.createdAt = new Date();
    }

    async send(message) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    async cleanup() {
        // Persist history
        await this.persistHistory();
    }

    async persistHistory() {
        // Implementation for persistence
        console.log(`Persisting history for session ${this.sessionId}`);
    }

    addToHistory(role, content) {
        this.history.push({
            role,
            content,
            timestamp: new Date().toISOString()
        });
    }
}

class MessageRouter {
    constructor() {
        this.handlers = new Map();
        this.setupDefaultHandlers();
    }

    setupDefaultHandlers() {
        this.handlers.set('ping', async (msg, session) => ({
            type: 'pong',
            timestamp: Date.now()
        }));

        this.handlers.set('skill.call', async (msg, session) => {
            // Route to skill hub
            return {
                type: 'skill.response',
                result: await this.callSkill(msg.skillName, msg.params)
            };
        });
    }

    async route(message, session) {
        const handler = this.handlers.get(message.type);
        if (handler) {
            return await handler(message, session);
        }
        return {
            error: true,
            message: `Unknown message type: ${message.type}`
        };
    }

    async callSkill(skillName, params) {
        // Implementation to call skill
        return { skillName, params, status: 'called' };
    }
}

module.exports = { GatewayServer, Session, MessageRouter };
