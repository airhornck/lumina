// OpenClaw Session Management - 原始参考实现

const EventEmitter = require('events');
const fs = require('fs').promises;
const path = require('path');

class SessionManager extends EventEmitter {
    constructor(options = {}) {
        super();
        this.sessions = new Map();
        this.persistencePath = options.persistencePath || './sessions';
        this.sessionTimeout = options.sessionTimeout || 30 * 60 * 1000; // 30 minutes
        this.cleanupInterval = setInterval(() => this.cleanupExpired(), 60000);
    }

    async createSession(sessionId, metadata = {}) {
        const session = new Session({
            sessionId,
            createdAt: new Date(),
            metadata,
            context: {},
            lockedSop: null,
            messageHistory: []
        });

        this.sessions.set(sessionId, session);
        this.emit('sessionCreated', session);
        
        return session;
    }

    getSession(sessionId) {
        const session = this.sessions.get(sessionId);
        if (session) {
            session.lastActivity = new Date();
        }
        return session;
    }

    async lockSop(sessionId, sopId) {
        const session = this.sessions.get(sessionId);
        if (session) {
            session.lockedSop = sopId;
            session.lockedAt = new Date();
            await this.persistSession(session);
            return true;
        }
        return false;
    }

    async clearLock(sessionId) {
        const session = this.sessions.get(sessionId);
        if (session) {
            session.lockedSop = null;
            session.lockedAt = null;
            await this.persistSession(session);
            return true;
        }
        return false;
    }

    async addMessage(sessionId, role, content, metadata = {}) {
        const session = this.sessions.get(sessionId);
        if (session) {
            const message = {
                id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                role,
                content,
                metadata,
                timestamp: new Date().toISOString()
            };
            session.messageHistory.push(message);
            session.lastActivity = new Date();
            
            // Persist if needed
            if (session.messageHistory.length % 10 === 0) {
                await this.persistSession(session);
            }
            
            return message;
        }
        return null;
    }

    async persistSession(session) {
        try {
            const filePath = path.join(this.persistencePath, `${session.sessionId}.json`);
            await fs.mkdir(this.persistencePath, { recursive: true });
            await fs.writeFile(filePath, JSON.stringify(session.toJSON(), null, 2));
        } catch (error) {
            console.error('Failed to persist session:', error);
        }
    }

    async loadSession(sessionId) {
        try {
            const filePath = path.join(this.persistencePath, `${sessionId}.json`);
            const data = await fs.readFile(filePath, 'utf-8');
            const sessionData = JSON.parse(data);
            const session = Session.fromJSON(sessionData);
            this.sessions.set(sessionId, session);
            return session;
        } catch (error) {
            return null;
        }
    }

    cleanupExpired() {
        const now = Date.now();
        for (const [sessionId, session] of this.sessions) {
            if (now - session.lastActivity.getTime() > this.sessionTimeout) {
                this.destroySession(sessionId);
            }
        }
    }

    async destroySession(sessionId) {
        const session = this.sessions.get(sessionId);
        if (session) {
            await this.persistSession(session);
            this.sessions.delete(sessionId);
            this.emit('sessionDestroyed', session);
        }
    }

    destroy() {
        clearInterval(this.cleanupInterval);
    }
}

class Session {
    constructor(data = {}) {
        this.sessionId = data.sessionId;
        this.createdAt = data.createdAt ? new Date(data.createdAt) : new Date();
        this.lastActivity = data.lastActivity ? new Date(data.lastActivity) : new Date();
        this.metadata = data.metadata || {};
        this.context = data.context || {};
        this.lockedSop = data.lockedSop || null;
        this.lockedAt = data.lockedAt ? new Date(data.lockedAt) : null;
        this.messageHistory = data.messageHistory || [];
    }

    toJSON() {
        return {
            sessionId: this.sessionId,
            createdAt: this.createdAt.toISOString(),
            lastActivity: this.lastActivity.toISOString(),
            metadata: this.metadata,
            context: this.context,
            lockedSop: this.lockedSop,
            lockedAt: this.lockedAt ? this.lockedAt.toISOString() : null,
            messageHistory: this.messageHistory
        };
    }

    static fromJSON(data) {
        return new Session(data);
    }

    getContext(key, defaultValue = null) {
        return this.context[key] !== undefined ? this.context[key] : defaultValue;
    }

    setContext(key, value) {
        this.context[key] = value;
        this.lastActivity = new Date();
    }

    clearContext() {
        this.context = {};
        this.lastActivity = new Date();
    }
}

module.exports = { SessionManager, Session };
