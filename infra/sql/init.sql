-- Lumina 数据库初始化脚本
-- 在 Docker 启动时自动执行

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于文本搜索

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 会话表（用于 Intent 上下文）
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_data JSONB DEFAULT '{}',
    last_intent VARCHAR(50),
    last_topic VARCHAR(200),
    intent_switch_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '7 days')
);

-- Intent 历史记录表
CREATE TABLE IF NOT EXISTS intent_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    intent_type VARCHAR(50) NOT NULL,
    intent_subtype VARCHAR(50),
    confidence FLOAT,
    entities JSONB DEFAULT '{}',
    requires_clarification BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 账号表（用于矩阵管理）
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,  -- xiaohongshu, douyin, etc.
    account_id VARCHAR(100) NOT NULL,
    account_name VARCHAR(100),
    account_type VARCHAR(50) DEFAULT 'single',  -- single, master, satellite
    credentials JSONB,  -- 加密存储的凭证
    cookies JSONB,
    status VARCHAR(20) DEFAULT 'active',
    last_login TIMESTAMP WITH TIME ZONE,
    health_score INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, platform, account_id)
);

-- 内容表
CREATE TABLE IF NOT EXISTS contents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    content_type VARCHAR(50) DEFAULT 'post',  -- post, video, script
    title VARCHAR(500),
    content TEXT,
    hashtags TEXT[],
    status VARCHAR(20) DEFAULT 'draft',  -- draft, scheduled, published, failed
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    platform_content_id VARCHAR(100),
    performance_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 矩阵关系表
CREATE TABLE IF NOT EXISTS matrix_relations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    master_account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    satellite_account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    traffic_share FLOAT DEFAULT 0.1,  -- 流量分配比例
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(master_account_id, satellite_account_id)
);

-- 知识库表
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(50) NOT NULL,  -- sop, template, case, best_practice
    category VARCHAR(100),
    title VARCHAR(200) NOT NULL,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    effectiveness_score FLOAT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RPA 任务记录表
CREATE TABLE IF NOT EXISTS rpa_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,  -- publish, collect, interact, login
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, success, failed
    params JSONB DEFAULT '{}',
    result JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_intent_history_user_id ON intent_history(user_id);
CREATE INDEX IF NOT EXISTS idx_intent_history_created_at ON intent_history(created_at);
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
CREATE INDEX IF NOT EXISTS idx_contents_user_id ON contents(user_id);
CREATE INDEX IF NOT EXISTS idx_contents_status ON contents(status);
CREATE INDEX IF NOT EXISTS idx_rpa_tasks_user_id ON rpa_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_rpa_tasks_status ON rpa_tasks(status);

-- 插入测试用户（开发环境）
INSERT INTO users (id, username, email, is_active, is_superuser)
VALUES 
    ('00000000-0000-0000-0000-000000000001', 'admin', 'admin@lumina.local', true, true),
    ('00000000-0000-0000-0000-000000000002', 'test', 'test@example.com', true, false)
ON CONFLICT (id) DO NOTHING;

-- 插入示例知识库内容
INSERT INTO knowledge_base (type, category, title, content, metadata)
VALUES 
    ('template', 'content', '爆款标题模板', '【数字】个【领域】技巧，让你【利益】', '{"tags": ["标题", "模板"]}'),
    ('best_practice', 'strategy', '黄金发布时间', '工作日晚8-10点为最佳发布时间', '{"tags": ["时间", "策略"]}'),
    ('sop', 'workflow', '内容创作SOP', '1.选题 -> 2.大纲 -> 3.初稿 -> 4.优化 -> 5.审核 -> 6.发布', '{"tags": ["SOP", "流程"]}')
ON CONFLICT DO NOTHING;

-- 创建更新触发器（自动更新 updated_at）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contents_updated_at BEFORE UPDATE ON contents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_base_updated_at BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
