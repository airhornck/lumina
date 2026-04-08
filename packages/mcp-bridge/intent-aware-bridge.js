/**
 * Intent-Aware MCP Bridge
 * 
 * 增强型 MCP Bridge，整合工业级 Intent 层
 * 负责 OpenClaw 与 Python 层的通信
 */

const { Client } = require('@modelcontextprotocol/sdk');
const { HttpTransport } = require('@modelcontextprotocol/sdk/http');
const axios = require('axios');

class IntentAwareBridge {
    constructor(pythonMcpUrl, timeoutMs = 5000) {
        this.pythonUrl = pythonMcpUrl;
        this.timeout = timeoutMs;
        this.intentEndpoint = `${pythonMcpUrl}/intent/recognize`;
        this.skillEndpoint = `${pythonMcpUrl}/skill/execute`;
    }

    /**
     * 执行用户请求
     * 
     * 完整流程：
     * 1. 调用 Intent Engine 识别意图
     * 2. 处理澄清状态
     * 3. 调用业务 Skill
     * 4. 返回格式化结果
     */
    async execute(params, context) {
        const session = context.session;
        const sessionContext = {
            previous_intent: session.get('last_intent'),
            previous_topic: session.get('last_topic'),
            user_history_count: session.get('history_count', 0),
            intent_switch_count: session.get('intent_switch_count', 0),
            user_id: session.user_id,
            session_id: session.id,
        };

        // 1. 调用 Intent Engine（带重试）
        let intentResult;
        try {
            intentResult = await this.callIntentEngine({
                text: params.text,
                user_id: session.user_id,
                session_context: sessionContext
            });
        } catch (err) {
            console.error('Intent recognition failed:', err);
            // Fallback: 保守假设为营销意图
            intentResult = {
                intent_type: 'marketing',
                subtype: 'general',
                confidence: 0.5,
                requires_clarification: false
            };
        }

        // 2. 处理澄清状态
        if (intentResult.requires_clarification) {
            return this.handleClarification(intentResult, session, params);
        }

        // 3. 更新会话上下文
        session.set('last_intent', intentResult.intent_type);
        session.set('last_topic', intentResult.topic || params.text);
        session.set('intent_switch_count', 0);
        session.increment('history_count');

        // 4. 调用业务 Skill
        const businessResult = await this.callSkill({
            user_input: params.text,
            confirmed_intent: intentResult.intent_type,
            intent_subtype: intentResult.subtype,
            entities: intentResult.entities,
            user_id: session.user_id,
            session_id: session.id
        });

        return {
            type: 'skill_result',
            content: businessResult.reply || businessResult.result,
            data: businessResult,
            intent: intentResult
        };
    }

    /**
     * 调用 Intent Engine
     */
    async callIntentEngine(params) {
        const response = await axios.post(
            this.intentEndpoint,
            params,
            {
                timeout: this.timeout,
                headers: {
                    'Content-Type': 'application/json'
                }
            }
        );
        return response.data;
    }

    /**
     * 调用业务 Skill
     */
    async callSkill(params) {
        const response = await axios.post(
            this.skillEndpoint,
            params,
            {
                timeout: this.timeout * 2, // Skill 调用可能需要更长时间
                headers: {
                    'Content-Type': 'application/json'
                }
            }
        );
        return response.data;
    }

    /**
     * 处理澄清状态
     */
    handleClarification(intentResult, session, params) {
        // 设置会话状态为澄清中
        session.setState('CLARIFYING', {
            questions: intentResult.clarification_questions,
            possible_intents: intentResult.clarification_options,
            original_text: params.text,
            timestamp: Date.now()
        });

        // 流式响应处理
        if (params.streamMode) {
            return this.createClarificationStream(intentResult);
        }

        return {
            type: 'clarification',
            message: intentResult.clarification_questions[0],
            suggestions: intentResult.clarification_options,
            context: 'needs_clarification'
        };
    }

    /**
     * 处理澄清响应
     */
    async handleClarificationResponse(userResponse, context) {
        const session = context.session;
        const clarifyingState = session.getState('CLARIFYING');

        if (!clarifyingState) {
            return {
                type: 'error',
                message: 'No clarification in progress'
            };
        }

        // 调用 Intent Engine 处理澄清响应
        const clarificationResult = await this.callIntentEngine({
            text: userResponse,
            user_id: session.user_id,
            session_context: {
                previous_intent: session.get('last_intent'),
                previous_topic: session.get('last_topic'),
                is_clarification_response: true,
                possible_intents: clarifyingState.possible_intents
            }
        });

        // 如果仍然是模糊意图，继续澄清
        if (clarificationResult.requires_clarification) {
            return this.handleClarification(clarificationResult, session, {
                text: userResponse
            });
        }

        // 清除澄清状态
        session.clearState('CLARIFYING');

        // 使用确认的意图执行
        return this.execute({
            text: clarifyingState.original_text,
            confirmed_intent: clarificationResult.intent_type,
            confirmed_subtype: clarificationResult.subtype
        }, context);
    }

    /**
     * 创建澄清流
     */
    createClarificationStream(intentResult) {
        const { Readable } = require('stream');
        const stream = new Readable({
            read() {
                this.push(JSON.stringify({
                    type: 'clarification',
                    message: intentResult.clarification_questions[0],
                    suggestions: intentResult.clarification_options
                }));
                this.push(null);
            }
        });
        return { type: 'clarification_stream', stream };
    }

    /**
     * 带重试的调用
     */
    async callWithRetry(request, retries = 2) {
        for (let i = 0; i <= retries; i++) {
            try {
                return await this.callSkill(request);
            } catch (err) {
                if (i === retries) throw err;
                
                // 指数退避
                const delay = 100 * Math.pow(2, i);
                await new Promise(r => setTimeout(r, delay));
            }
        }
    }
}

/**
 * OpenClaw Skill 配置导出
 */
module.exports = {
    name: 'ai_marketing_intent_aware',
    description: 'AI 营销助手 - Intent-Aware Bridge',
    
    create: (config) => {
        const bridge = new IntentAwareBridge(
            config.pythonMcpUrl || 'http://localhost:8000',
            config.timeout || 5000
        );
        return bridge;
    },
    
    execute: async (params, context) => {
        // 检查是否在澄清状态
        const session = context.session;
        const currentState = session.getState?.('CLARIFYING');
        
        if (currentState) {
            // 处理澄清响应
            return bridge.handleClarificationResponse(params.text, context);
        }
        
        // 正常执行
        const bridge = new IntentAwareBridge(
            process.env.PYTHON_MCP_URL || 'http://localhost:8000'
        );
        return bridge.execute(params, context);
    },
    
    shouldActivate: (intent) => {
        // 激活条件：所有营销和闲聊意图
        return ['marketing', 'casual', 'ambiguous'].includes(intent.category);
    }
};
