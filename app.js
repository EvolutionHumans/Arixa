/**
 * Arixa 许可证管理系统 - 主应用逻辑
 * License Management System - Main Application
 */

document.addEventListener('DOMContentLoaded', function() {
    // ========== DOM 元素 ==========
    const tabs = document.querySelectorAll('.tab');
    const panels = document.querySelectorAll('.panel');
    const generateBtn = document.getElementById('generate-btn');
    const verifyBtn = document.getElementById('verify-btn');
    const clearBtn = document.getElementById('clear-btn');
    const searchInput = document.getElementById('search');
    const filterStatus = document.getElementById('filter-status');
    const modal = document.getElementById('modal');
    const modalBody = document.getElementById('modal-body');
    const modalClose = document.querySelector('.modal .close');
    const toast = document.getElementById('toast');
    const durationInput = document.getElementById('duration');
    const durationUnitSelect = document.getElementById('duration-unit');

    // 存储最近生成的许可证
    let lastGeneratedLicenses = [];

    // ========== 有效期单位切换 ==========
    durationUnitSelect.addEventListener('change', function() {
        if (this.value === 'permanent') {
            durationInput.disabled = true;
            durationInput.value = '';
            durationInput.placeholder = '永久有效';
        } else {
            durationInput.disabled = false;
            durationInput.placeholder = '';
            if (!durationInput.value) {
                durationInput.value = '30';
            }
        }
    });

    // ========== 标签切换 ==========
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            tab.classList.add('active');
            const panelId = tab.getAttribute('data-tab');
            document.getElementById(panelId).classList.add('active');

            // 切换到管理面板时刷新列表
            if (panelId === 'manage') {
                refreshLicenseList();
            }
        });
    });

    // ========== 生成许可证 ==========
    generateBtn.addEventListener('click', async () => {
        const format = document.getElementById('format').value;
        const duration = parseInt(document.getElementById('duration').value) || 0;
        const durationUnit = document.getElementById('duration-unit').value;
        const userType = document.getElementById('usertype').value;
        const product = document.getElementById('product').value.trim() || 'Arixa';
        const batchCount = parseInt(document.getElementById('batch-count').value);

        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span>⏳</span> 生成中...';

        try {
            const options = { format, duration, durationUnit, userType, product };
            const licenses = await licenseGenerator.generateBatch(batchCount, options);
            
            lastGeneratedLicenses = licenses;
            displayGeneratedLicenses(licenses);
            showToast(`成功生成 ${licenses.length} 个许可证`);
        } catch (error) {
            console.error('生成失败:', error);
            showToast('生成失败，请重试');
        }

        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span>🎫</span> 生成许可证';
    });

    // ========== 显示生成的许可证 ==========
    function displayGeneratedLicenses(licenses) {
        const container = document.getElementById('generated-licenses');
        const result = document.getElementById('result');
        
        let html = '';
        licenses.forEach(license => {
            const expiresText = license.isPermanent ? '永久有效' : formatDate(license.expiresAt);
            const durationText = license.isPermanent ? '永久' : `${license.duration} ${getUnitLabel(license.durationUnit)}`;
            
            html += `
                <div class="license-item">
                    <div class="license-key">
                        <span>${license.key}</span>
                        <button class="copy-btn" onclick="copyToClipboard('${license.key}')">复制</button>
                    </div>
                    <div class="license-meta">
                        <span>📅 过期: ${expiresText}</span>
                        <span>⏱️ 有效期: ${durationText}</span>
                        <span>👤 ${license.metadata?.userType || '用户'}</span>
                        <span>📦 ${license.metadata?.product || 'Arixa'}</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
        result.classList.remove('hidden');
    }

    // ========== 生成结果导出按钮 ==========
    document.getElementById('export-excel-btn').addEventListener('click', () => {
        if (lastGeneratedLicenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportCSV(lastGeneratedLicenses),
            `Arixa_Licenses_${formatDateFile(new Date())}.csv`,
            'text/csv;charset=utf-8'
        );
        showToast('已导出为 Excel 格式');
    });

    document.getElementById('export-word-btn').addEventListener('click', () => {
        if (lastGeneratedLicenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportWord(lastGeneratedLicenses),
            `Arixa_Licenses_${formatDateFile(new Date())}.doc`,
            'application/msword'
        );
        showToast('已导出为 Word 格式');
    });

    document.getElementById('export-txt-btn').addEventListener('click', () => {
        if (lastGeneratedLicenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportTXT(lastGeneratedLicenses),
            `Arixa_Licenses_${formatDateFile(new Date())}.txt`,
            'text/plain;charset=utf-8'
        );
        showToast('已导出为 TXT 格式');
    });

    document.getElementById('export-json-btn').addEventListener('click', () => {
        if (lastGeneratedLicenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportJSON(lastGeneratedLicenses),
            `Arixa_Licenses_${formatDateFile(new Date())}.json`,
            'application/json'
        );
        showToast('已导出为 JSON 格式');
    });

    // ========== 管理列表导出按钮 ==========
    document.getElementById('manage-export-excel').addEventListener('click', () => {
        const licenses = getFilteredLicenses();
        if (licenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportCSV(licenses),
            `Arixa_All_Licenses_${formatDateFile(new Date())}.csv`,
            'text/csv;charset=utf-8'
        );
        showToast('已导出为 Excel 格式');
    });

    document.getElementById('manage-export-word').addEventListener('click', () => {
        const licenses = getFilteredLicenses();
        if (licenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportWord(licenses),
            `Arixa_All_Licenses_${formatDateFile(new Date())}.doc`,
            'application/msword'
        );
        showToast('已导出为 Word 格式');
    });

    document.getElementById('manage-export-txt').addEventListener('click', () => {
        const licenses = getFilteredLicenses();
        if (licenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportTXT(licenses),
            `Arixa_All_Licenses_${formatDateFile(new Date())}.txt`,
            'text/plain;charset=utf-8'
        );
        showToast('已导出为 TXT 格式');
    });

    document.getElementById('manage-export-json').addEventListener('click', () => {
        const licenses = getFilteredLicenses();
        if (licenses.length === 0) {
            showToast('没有可导出的许可证');
            return;
        }
        downloadFile(
            licenseGenerator.exportJSON(licenses),
            `Arixa_All_Licenses_${formatDateFile(new Date())}.json`,
            'application/json'
        );
        showToast('已导出为 JSON 格式');
    });

    // ========== 获取筛选后的许可证 ==========
    function getFilteredLicenses() {
        const query = searchInput.value.trim();
        const status = filterStatus.value;
        return licenseGenerator.search(query, status);
    }

    // ========== 下载文件 ==========
    function downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }

    // ========== 验证许可证 ==========
    verifyBtn.addEventListener('click', () => {
        const key = document.getElementById('verify-key').value.trim();
        
        if (!key) {
            showToast('请输入许可证密钥');
            return;
        }

        const result = licenseGenerator.verify(key);
        displayVerifyResult(result);
    });

    // ========== 显示验证结果 ==========
    function displayVerifyResult(result) {
        const container = document.getElementById('verify-result');
        container.classList.remove('hidden', 'valid', 'invalid', 'permanent');
        
        if (result.valid) {
            if (result.isPermanent) {
                container.classList.add('permanent');
                container.innerHTML = `
                    <div class="icon">♾️</div>
                    <h4>许可证永久有效</h4>
                    <div class="details">
                        <p><strong>创建时间:</strong> <span>${formatDate(result.license.createdAt)}</span></p>
                        <p><strong>用户类型:</strong> <span>${result.license.metadata?.userType || '用户'}</span></p>
                        <p><strong>产品名称:</strong> <span>${result.license.metadata?.product || 'Arixa'}</span></p>
                    </div>
                `;
            } else {
                container.classList.add('valid');
                container.innerHTML = `
                    <div class="icon">✅</div>
                    <h4>许可证有效</h4>
                    <p>剩余 <strong>${result.daysRemaining}</strong> 天</p>
                    <div class="details">
                        <p><strong>创建时间:</strong> <span>${formatDate(result.license.createdAt)}</span></p>
                        <p><strong>过期时间:</strong> <span>${formatDate(result.license.expiresAt)}</span></p>
                        <p><strong>用户类型:</strong> <span>${result.license.metadata?.userType || '用户'}</span></p>
                        <p><strong>产品名称:</strong> <span>${result.license.metadata?.product || 'Arixa'}</span></p>
                    </div>
                `;
            }
        } else {
            container.classList.add('invalid');
            container.innerHTML = `
                <div class="icon">❌</div>
                <h4>${result.reason}</h4>
                ${result.license ? `
                    <div class="details">
                        <p><strong>过期时间:</strong> <span>${formatDate(result.license.expiresAt)}</span></p>
                        <p><strong>用户类型:</strong> <span>${result.license.metadata?.userType || '用户'}</span></p>
                        <p><strong>产品名称:</strong> <span>${result.license.metadata?.product || 'Arixa'}</span></p>
                    </div>
                ` : '<p>该许可证密钥未在系统中注册</p>'}
            `;
        }
    }

    // ========== 刷新许可证列表 ==========
    function refreshLicenseList() {
        const query = searchInput.value.trim();
        const status = filterStatus.value;
        
        const licenses = licenseGenerator.search(query, status);
        const stats = licenseGenerator.getStats();
        
        // 更新统计
        document.getElementById('total-count').textContent = stats.total;
        document.getElementById('valid-count').textContent = stats.valid;
        document.getElementById('expired-count').textContent = stats.expired;
        document.getElementById('permanent-count').textContent = stats.permanent;
        
        // 更新列表
        const container = document.getElementById('license-list');
        
        if (licenses.length === 0) {
            container.innerHTML = '<p class="empty-message">暂无许可证</p>';
            return;
        }

        const now = new Date();
        let html = '';
        
        // 按创建时间倒序排列
        licenses.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
        
        licenses.forEach(license => {
            let statusClass = 'valid';
            let statusText = '✓ 有效';
            
            if (license.isPermanent) {
                statusClass = 'permanent';
                statusText = '♾️ 永久';
            } else if (new Date(license.expiresAt) <= now) {
                statusClass = 'expired';
                statusText = '✗ 已过期';
            }

            const expiresText = license.isPermanent ? '永久有效' : formatDate(license.expiresAt);

            html += `
                <div class="license-item">
                    <div class="license-info">
                        <div class="license-key">
                            <span>${license.key}</span>
                            <span class="status-badge ${statusClass}">
                                ${statusText}
                            </span>
                        </div>
                        <div class="license-meta">
                            <span>📅 ${expiresText}</span>
                            <span>👤 ${license.metadata?.userType || '用户'}</span>
                            <span>📦 ${license.metadata?.product || 'Arixa'}</span>
                        </div>
                    </div>
                    <div class="license-actions">
                        <button class="btn small secondary" onclick="showLicenseDetail('${license.key}')">详情</button>
                        <button class="btn small secondary" onclick="copyToClipboard('${license.key}')">复制</button>
                        <button class="btn small danger" onclick="revokeLicense('${license.key}')">删除</button>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    // ========== 搜索和筛选 ==========
    searchInput.addEventListener('input', refreshLicenseList);
    filterStatus.addEventListener('change', refreshLicenseList);

    // ========== 清空 ==========
    clearBtn.addEventListener('click', () => {
        if (confirm('确定要清空所有许可证吗？此操作不可恢复！')) {
            licenseGenerator.clearAll();
            refreshLicenseList();
            showToast('已清空所有许可证');
        }
    });

    // ========== 模态框 ==========
    modalClose.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });

    // ========== 全局函数 ==========
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('已复制到剪贴板');
        }).catch(() => {
            // 降级方案
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showToast('已复制到剪贴板');
        });
    };

    window.showLicenseDetail = function(key) {
        const license = licenseGenerator.get(key);
        if (!license) return;

        const now = new Date();
        let statusText = '有效';
        let daysRemaining = '-';
        
        if (license.isPermanent) {
            statusText = '永久有效';
            daysRemaining = '∞';
        } else {
            const expiresAt = new Date(license.expiresAt);
            if (expiresAt <= now) {
                statusText = '已过期';
                daysRemaining = '0';
            } else {
                daysRemaining = Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24)) + ' 天';
            }
        }

        const expiresText = license.isPermanent ? '永久有效' : formatDateTime(license.expiresAt);
        const durationText = license.isPermanent ? '永久' : `${license.duration} ${getUnitLabel(license.durationUnit)}`;

        modalBody.innerHTML = `
            <div class="detail-row">
                <span class="detail-label">许可证密钥</span>
                <span class="detail-value">${license.key}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">状态</span>
                <span class="detail-value">
                    <span class="status-badge ${license.isPermanent ? 'permanent' : (new Date(license.expiresAt) > now ? 'valid' : 'expired')}">
                        ${statusText}
                    </span>
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">剩余时间</span>
                <span class="detail-value">${daysRemaining}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">创建时间</span>
                <span class="detail-value">${formatDateTime(license.createdAt)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">过期时间</span>
                <span class="detail-value">${expiresText}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">有效期</span>
                <span class="detail-value">${durationText}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">用户类型</span>
                <span class="detail-value">${license.metadata?.userType || '用户'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">产品名称</span>
                <span class="detail-value">${license.metadata?.product || 'Arixa'}</span>
            </div>
        `;

        modal.classList.remove('hidden');
    };

    window.revokeLicense = function(key) {
        if (confirm('确定要删除这个许可证吗？')) {
            licenseGenerator.revoke(key);
            refreshLicenseList();
            showToast('许可证已删除');
        }
    };

    // ========== 工具函数 ==========
    function formatDate(dateStr) {
        if (!dateStr) return '永久有效';
        const date = new Date(dateStr);
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '永久有效';
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function formatDateFile(date) {
        return date.toISOString().slice(0, 10).replace(/-/g, '');
    }

    function getUnitLabel(unit) {
        const labels = {
            days: '天',
            months: '月',
            years: '年',
            permanent: '永久'
        };
        return labels[unit] || unit;
    }

    function showToast(message) {
        toast.textContent = message;
        toast.classList.remove('hidden');
        
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }

    // ========== 初始化 ==========
    refreshLicenseList();
});
