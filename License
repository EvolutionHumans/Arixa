/**
 * 许可证生成器核心模块
 * License Generator Core Module
 */

class LicenseGenerator {
    constructor(secretKey = 'default-secret-key') {
        this.secretKey = secretKey;
        this.storageKey = 'license_manager_data';
        this.licenses = this.loadFromStorage();
    }

    /**
     * 从 localStorage 加载数据
     */
    loadFromStorage() {
        try {
            const data = localStorage.getItem(this.storageKey);
            return data ? JSON.parse(data) : {};
        } catch (e) {
            console.error('加载数据失败:', e);
            return {};
        }
    }

    /**
     * 保存数据到 localStorage
     */
    saveToStorage() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.licenses));
        } catch (e) {
            console.error('保存数据失败:', e);
        }
    }

    /**
     * 生成 UUID
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        }).toUpperCase();
    }

    /**
     * 生成哈希
     */
    async generateHash(data) {
        const encoder = new TextEncoder();
        const dataBuffer = encoder.encode(data);
        const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    /**
     * 根据格式生成密钥
     */
    async generateKey(format, timestamp, metadata) {
        const uniqueId = this.generateUUID();
        const timeStr = timestamp.toISOString();
        const metaStr = metadata ? JSON.stringify(metadata) : '';
        
        const data = `${uniqueId}${timeStr}${metaStr}${this.secretKey}`;
        const hash = await this.generateHash(data);

        switch (format) {
            case 'uuid':
                return this.generateUUID();
            
            case 'serial':
                const chars = hash.slice(0, 16).toUpperCase();
                return `${chars.slice(0,4)}-${chars.slice(4,8)}-${chars.slice(8,12)}-${chars.slice(12,16)}`;
            
            case 'compact':
                return hash.slice(0, 20).toUpperCase();
            
            case 'encoded':
                const payload = {
                    id: uniqueId.slice(0, 8),
                    ts: Math.floor(timestamp.getTime() / 1000),
                    sig: hash.slice(0, 8)
                };
                return btoa(JSON.stringify(payload)).replace(/=/g, '');
            
            default:
                return hash.slice(0, 16).toUpperCase();
        }
    }

    /**
     * 计算过期时间
     */
    calculateExpiry(duration, unit) {
        const now = new Date();
        switch (unit) {
            case 'days':
                return new Date(now.getTime() + duration * 24 * 60 * 60 * 1000);
            case 'months':
                return new Date(now.setMonth(now.getMonth() + duration));
            case 'years':
                return new Date(now.setFullYear(now.getFullYear() + duration));
            default:
                return new Date(now.getTime() + duration * 24 * 60 * 60 * 1000);
        }
    }

    /**
     * 生成许可证
     */
    async generate(options = {}) {
        const {
            format = 'serial',
            duration = 30,
            durationUnit = 'days',
            username = '',
            product = ''
        } = options;

        const createdAt = new Date();
        const expiresAt = this.calculateExpiry(duration, durationUnit);

        const metadata = {};
        if (username) metadata.user = username;
        if (product) metadata.product = product;

        const key = await this.generateKey(format, createdAt, metadata);

        const license = {
            key,
            createdAt: createdAt.toISOString(),
            expiresAt: expiresAt.toISOString(),
            duration,
            durationUnit,
            metadata: Object.keys(metadata).length > 0 ? metadata : null
        };

        this.licenses[key] = license;
        this.saveToStorage();

        return license;
    }

    /**
     * 批量生成
     */
    async generateBatch(count, options = {}) {
        const licenses = [];
        for (let i = 0; i < count; i++) {
            const license = await this.generate(options);
            licenses.push(license);
        }
        return licenses;
    }

    /**
     * 验证许可证
     */
    verify(key) {
        const license = this.licenses[key];
        if (!license) {
            return { valid: false, reason: '许可证不存在' };
        }

        const now = new Date();
        const expiresAt = new Date(license.expiresAt);

        if (now > expiresAt) {
            return { 
                valid: false, 
                reason: '许可证已过期',
                license 
            };
        }

        return { 
            valid: true, 
            reason: '许可证有效',
            license,
            daysRemaining: Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24))
        };
    }

    /**
     * 获取许可证
     */
    get(key) {
        return this.licenses[key] || null;
    }

    /**
     * 获取所有许可证
     */
    getAll() {
        return Object.values(this.licenses);
    }

    /**
     * 删除许可证
     */
    revoke(key) {
        if (this.licenses[key]) {
            delete this.licenses[key];
            this.saveToStorage();
            return true;
        }
        return false;
    }

    /**
     * 清空所有许可证
     */
    clearAll() {
        this.licenses = {};
        this.saveToStorage();
    }

    /**
     * 获取统计信息
     */
    getStats() {
        const all = this.getAll();
        const now = new Date();
        
        let valid = 0;
        let expired = 0;

        all.forEach(license => {
            if (new Date(license.expiresAt) > now) {
                valid++;
            } else {
                expired++;
            }
        });

        return {
            total: all.length,
            valid,
            expired
        };
    }

    /**
     * 导出为 JSON
     */
    exportJSON() {
        return JSON.stringify(this.licenses, null, 2);
    }

    /**
     * 导入 JSON
     */
    importJSON(jsonString) {
        try {
            const data = JSON.parse(jsonString);
            this.licenses = { ...this.licenses, ...data };
            this.saveToStorage();
            return true;
        } catch (e) {
            console.error('导入失败:', e);
            return false;
        }
    }

    /**
     * 搜索许可证
     */
    search(query, status = 'all') {
        const now = new Date();
        return this.getAll().filter(license => {
            // 状态过滤
            const isValid = new Date(license.expiresAt) > now;
            if (status === 'valid' && !isValid) return false;
            if (status === 'expired' && isValid) return false;

            // 关键词搜索
            if (query) {
                const q = query.toLowerCase();
                const keyMatch = license.key.toLowerCase().includes(q);
                const userMatch = license.metadata?.user?.toLowerCase().includes(q);
                const productMatch = license.metadata?.product?.toLowerCase().includes(q);
                return keyMatch || userMatch || productMatch;
            }

            return true;
        });
    }
}

// 导出实例
const licenseGenerator = new LicenseGenerator('my-secret-key-2024');
