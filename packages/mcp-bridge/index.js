/**
 * MCP Bridge Package
 * 
 * 提供 OpenClaw 与 Python AI Core 之间的通信桥梁
 */

const IntentAwareBridge = require('./intent-aware-bridge');
const { Client } = require('@modelcontextprotocol/sdk');

/**
 * 创建 MCP Bridge 实例
 * 
 * @param {Object} config - 配置对象
 * @param {string} config.pythonMcpUrl - Python MCP Server URL
 * @param {number} config.timeout - 超时时间（毫秒）
 * @returns {IntentAwareBridge}
 */
function createBridge(config = {}) {
    return new IntentAwareBridge(
        config.pythonMcpUrl || process.env.PYTHON_MCP_URL || 'http://localhost:8000',
        config.timeout || 5000
    );
}

module.exports = {
    IntentAwareBridge,
    createBridge,
    
    // OpenClaw 兼容导出
    default: IntentAwareBridge,
    
    // Skill 配置（供 OpenClaw 加载）
    skillConfig: {
        name: 'lumina_mcp_bridge',
        version: '1.0.0',
        description: 'Lumina AI MCP Bridge - 连接 Node.js 与 Python AI Core',
        
        // 激活条件
        shouldActivate: (intent) => {
            return true; // 所有请求都经过此 Bridge
        },
        
        // 执行函数
        execute: async (params, context) => {
            const bridge = createBridge();
            return bridge.execute(params, context);
        }
    }
};
