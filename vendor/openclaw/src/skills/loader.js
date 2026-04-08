// OpenClaw Skill Loader - 原始参考实现

const fs = require('fs').promises;
const path = require('path');
const yaml = require('js-yaml');

class SkillLoader {
    constructor(options = {}) {
        this.skillsDir = options.skillsDir || './skills';
        this.registry = new Map();
        this.watchers = new Map();
    }

    async loadAllSkills() {
        try {
            const entries = await fs.readdir(this.skillsDir, { withFileTypes: true });
            const skillDirs = entries
                .filter(entry => entry.isDirectory() && entry.name.startsWith('skill-'))
                .map(entry => entry.name);

            const skills = [];
            for (const dir of skillDirs) {
                const skillPath = path.join(this.skillsDir, dir);
                try {
                    const skill = await this.loadSkill(skillPath);
                    skills.push(skill);
                } catch (error) {
                    console.error(`Failed to load skill from ${dir}:`, error.message);
                }
            }

            return skills;
        } catch (error) {
            console.error('Failed to load skills:', error);
            return [];
        }
    }

    async loadSkill(skillPath) {
        const skillMdPath = path.join(skillPath, 'SKILL.md');
        
        // Check if SKILL.md exists
        try {
            await fs.access(skillMdPath);
        } catch {
            throw new Error(`SKILL.md not found in ${skillPath}`);
        }

        // Parse SKILL.md
        const content = await fs.readFile(skillMdPath, 'utf-8');
        const metadata = this.parseSkillMd(content);

        // Create skill instance
        const skill = new Skill({
            name: metadata.name,
            version: metadata.version,
            description: metadata.description,
            entryPoint: metadata.entry_point,
            path: skillPath,
            metadata: metadata
        });

        // Register skill
        this.registry.set(skill.name, skill);
        
        console.log(`Loaded skill: ${skill.name}@${skill.version}`);
        return skill;
    }

    parseSkillMd(content) {
        // Parse YAML frontmatter from SKILL.md
        // Format:
        // ---
        // name: text_generator
        // version: 1.0.0
        // description: Generate marketing copy
        // entry_point: main:TextGeneratorSkill
        // ---
        
        const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
        if (!frontmatterMatch) {
            throw new Error('Invalid SKILL.md format: no YAML frontmatter found');
        }

        try {
            const metadata = yaml.load(frontmatterMatch[1]);
            this.validateMetadata(metadata);
            return metadata;
        } catch (error) {
            throw new Error(`Failed to parse SKILL.md YAML: ${error.message}`);
        }
    }

    validateMetadata(metadata) {
        const required = ['name', 'version', 'description', 'entry_point'];
        for (const field of required) {
            if (!metadata[field]) {
                throw new Error(`Missing required field in SKILL.md: ${field}`);
            }
        }
    }

    getSkill(name) {
        return this.registry.get(name);
    }

    listSkills() {
        return Array.from(this.registry.values()).map(skill => ({
            name: skill.name,
            version: skill.version,
            description: skill.description,
            entryPoint: skill.entryPoint
        }));
    }

    async reloadSkill(name) {
        const skill = this.registry.get(name);
        if (skill) {
            await this.loadSkill(skill.path);
        }
    }

    unloadSkill(name) {
        return this.registry.delete(name);
    }
}

class Skill {
    constructor(data = {}) {
        this.name = data.name;
        this.version = data.version;
        this.description = data.description;
        this.entryPoint = data.entryPoint;
        this.path = data.path;
        this.metadata = data.metadata || {};
        this._executor = null;
        this.loadedAt = new Date();
    }

    async getExecutor() {
        if (!this._executor) {
            // Dynamic require of skill module
            const [moduleName, className] = this.entryPoint.split(':');
            const modulePath = path.join(this.path, `${moduleName}.js`);
            
            // Clear require cache for hot reload
            delete require.cache[require.resolve(modulePath)];
            
            const module = require(modulePath);
            this._executor = new module[className]();
        }
        return this._executor;
    }

    async execute(inputData, context = {}) {
        const executor = await this.getExecutor();
        return await executor.execute(inputData, context);
    }

    async healthCheck() {
        try {
            const executor = await this.getExecutor();
            if (executor.healthCheck) {
                return await executor.healthCheck();
            }
            return true;
        } catch {
            return false;
        }
    }

    toJSON() {
        return {
            name: this.name,
            version: this.version,
            description: this.description,
            entryPoint: this.entryPoint,
            path: this.path,
            metadata: this.metadata,
            loadedAt: this.loadedAt.toISOString()
        };
    }
}

// Example SKILL.md template
const SKILL_MD_TEMPLATE = `---
name: {{skill_name}}
version: 1.0.0
description: {{skill_description}}
entry_point: main:{{class_name}}
author: {{author}}
tags:
  - {{tag1}}
  - {{tag2}}
---

# {{skill_name}}

## Description

{{skill_description}}

## Input Schema

\`\`\`json
{
  "type": "object",
  "properties": {
    "input1": {
      "type": "string",
      "description": "Description of input1"
    }
  },
  "required": ["input1"]
}
\`\`\`

## Output Schema

\`\`\`json
{
  "type": "object",
  "properties": {
    "output1": {
      "type": "string",
      "description": "Description of output1"
    }
  }
}
\`\`\`

## Examples

### Example 1

Input:
\`\`\`json
{"input1": "value1"}
\`\`\`

Output:
\`\`\`json
{"output1": "result1"}
\`\`\`
`;

module.exports = { 
    SkillLoader, 
    Skill,
    SKILL_MD_TEMPLATE 
};
