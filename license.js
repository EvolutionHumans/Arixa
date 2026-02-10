/**
 * Arixa 许可证生成器核心模块
 * License Generator Core Module
 */

class LicenseGenerator {
    constructor(secretKey = 'arixa-secret-key-2024') {
        this.secretKey = secretKey;
        this.storageKey = 'arixa_license_manager_data';
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
        // 永久有效返回 null
        if (unit === 'permanent') {
            return null;
        }
        
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
            userType = '用户',
            product = 'Arixa'
        } = options;

        const createdAt = new Date();
        const expiresAt = this.calculateExpiry(duration, durationUnit);
        const isPermanent = durationUnit === 'permanent';

        const metadata = {
            userType: userType,
            product: product
        };

        const key = await this.generateKey(format, createdAt, metadata);

        const license = {
            key,
            createdAt: createdAt.toISOString(),
            expiresAt: isPermanent ? null : expiresAt.toISOString(),
            duration: isPermanent ? 0 : duration,
            durationUnit,
            isPermanent,
            metadata
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

        // 永久有效的许可证
        if (license.isPermanent) {
            return { 
                valid: true, 
                reason: '许可证永久有效',
                license,
                isPermanent: true
            };
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
        let permanent = 0;

        all.forEach(license => {
            if (license.isPermanent) {
                permanent++;
                valid++;
            } else if (new Date(license.expiresAt) > now) {
                valid++;
            } else {
                expired++;
            }
        });

        return {
            total: all.length,
            valid,
            expired,
            permanent
        };
    }

    /**
     * 导出为 JSON
     */
    exportJSON(licenses = null) {
        const data = licenses || this.getAll();
        return JSON.stringify(data, null, 2);
    }

    /**
     * 导出为 CSV (用于 Excel)
     */
    exportCSV(licenses = null) {
        const data = licenses || this.getAll();
        const headers = ['许可证密钥', '用户类型', '产品名称', '创建时间', '过期时间', '有效期', '状态'];
        const now = new Date();
        
        const rows = data.map(lic => {
            let status = '有效';
            let expiresStr = '永久有效';
            let durationStr = '永久';
            
            if (!lic.isPermanent) {
                expiresStr = this.formatDate(lic.expiresAt);
                durationStr = `${lic.duration} ${this.getUnitLabel(lic.durationUnit)}`;
                if (new Date(lic.expiresAt) < now) {
                    status = '已过期';
                }
            }
            
            return [
                lic.key,
                lic.metadata?.userType || '用户',
                lic.metadata?.product || 'Arixa',
                this.formatDate(lic.createdAt),
                expiresStr,
                durationStr,
                status
            ];
        });

        // 添加 BOM 以支持中文
        const BOM = '\uFEFF';
        const csvContent = BOM + [headers, ...rows].map(row => row.join(',')).join('\n');
        return csvContent;
    }

    /**
     * 导出为 Word (HTML 格式，可被 Word 打开)
     */
    exportWord(licenses = null) {
        const data = licenses || this.getAll();
        const now = new Date();
        
        let html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Arixa 许可证列表</title>
    <style>
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; padding: 20px; }
        h1 { color: #6366f1; text-align: center; }
        .info { text-align: center; color: #666; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background: #6366f1; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .valid { color: #10b981; font-weight: bold; }
        .expired { color: #ef4444; font-weight: bold; }
        .permanent { color: #3b82f6; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🔐 Arixa 许可证列表</h1>
    <p class="info">导出时间: ${this.formatDateTime(new Date())} | 共 ${data.length} 个许可证</p>
    <table>
        <tr>
            <th>序号</th>
            <th>许可证密钥</th>
            <th>用户类型</th>
            <th>产品名称</th>
            <th>创建时间</th>
            <th>过期时间</th>
            <th>状态</th>
        </tr>`;

        data.forEach((lic, index) => {
            let status = '<span class="valid">有效</span>';
            let expiresStr = '<span class="permanent">永久有效</span>';
            
            if (!lic.isPermanent) {
                expiresStr = this.formatDate(lic.expiresAt);
                if (new Date(lic.expiresAt) < now) {
                    status = '<span class="expired">已过期</span>';
                }
            } else {
                status = '<span class="permanent">永久有效</span>';
            }

            html += `
        <tr>
            <td>${index + 1}</td>
            <td><code>${lic.key}</code></td>
            <td>${lic.metadata?.userType || '用户'}</td>
            <td>${lic.metadata?.product || 'Arixa'}</td>
            <td>${this.formatDate(lic.createdAt)}</td>
            <td>${expiresStr}</td>
            <td>${status}</td>
        </tr>`;
        });

        html += `
    </table>
</body>
</html>`;
        return html;
    }

    /**
     * 导出为纯文本
     */
    exportTXT(licenses = null) {
        const data = licenses || this.getAll();
        const now = new Date();
        
        let txt = `========================================\n`;
        txt += `    Arixa 许可证列表\n`;
        txt += `    导出时间: ${this.formatDateTime(new Date())}\n`;
        txt += `    共 ${data.length} 个许可证\n`;
        txt += `========================================\n\n`;

        data.forEach((lic, index) => {
            let status = '有效';
            let expiresStr = '永久有效';
            
            if (!lic.isPermanent) {
                expiresStr = this.formatDate(lic.expiresAt);
                if (new Date(lic.expiresAt) < now) {
                    status = '已过期';
                }
            } else {
                status = '永久有效';
            }

            txt += `[${index + 1}] ${lic.key}\n`;
            txt += `    用户类型: ${lic.metadata?.userType || '用户'}\n`;
            txt += `    产品名称: ${lic.metadata?.product || 'Arixa'}\n`;
            txt += `    创建时间: ${this.formatDate(lic.createdAt)}\n`;
            txt += `    过期时间: ${expiresStr}\n`;
            txt += `    状态: ${status}\n`;
            txt += `----------------------------------------\n`;
        });

        return txt;
    }

    /**
     * 搜索许可证
     */
    search(query, status = 'all') {
        const now = new Date();
        return this.getAll().filter(license => {
            // 状态过滤
            if (status === 'valid') {
                if (license.isPermanent) return true;
                if (new Date(license.expiresAt) <= now) return false;
            } else if (status === 'expired') {
                if (license.isPermanent) return false;
                if (new Date(license.expiresAt) > now) return false;
            } else if (status === 'permanent') {
                if (!license.isPermanent) return false;
            }

            // 关键词搜索
            if (query) {
                const q = query.toLowerCase();
                const keyMatch = license.key.toLowerCase().includes(q);
                const userMatch = license.metadata?.userType?.toLowerCase().includes(q);
                const productMatch = license.metadata?.product?.toLowerCase().includes(q);
                return keyMatch || userMatch || productMatch;
            }

            return true;
        });
    }

    /**
     * 工具函数
     */
    formatDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }

    formatDateTime(date) {
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    getUnitLabel(unit) {
        const labels = {
            days: '天',
            months: '月',
            years: '年',
            permanent: '永久'
        };
        return labels[unit] || unit;
    }
}

// 导出实例
const licenseGenerator = new LicenseGenerator('arixa-secret-key-2024');
