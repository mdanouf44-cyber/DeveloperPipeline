// Dashboard Frontend Controller

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const tgActive = document.getElementById('chk-tg-active');
    const tgTime = document.getElementById('time-tg');
    const saveTgBtn = document.getElementById('btn-save-tg');

    const liActive = document.getElementById('chk-li-active');
    const liTime = document.getElementById('time-li');
    const saveLiBtn = document.getElementById('btn-save-li');

    const triggerTgBtn = document.getElementById('btn-trigger-telegram');
    const triggerLiBtn = document.getElementById('btn-trigger-linkedin');
    const stateBadge = document.getElementById('pipeline-state-badge');
    const lastRunLbl = document.getElementById('lbl-last-run');
    const lastResultLbl = document.getElementById('lbl-last-result');

    const configForm = document.getElementById('config-form');
    const cfgTgToken = document.getElementById('cfg-tg-token');
    const cfgTgChatId = document.getElementById('cfg-tg-chat-id');
    const cfgOrKey = document.getElementById('cfg-or-key');
    const cfgApifyKey = document.getElementById('cfg-apify-key');

    const consoleOutput = document.getElementById('terminal-output');
    const clearLogsBtn = document.getElementById('btn-clear-logs');
    const refreshLogsBtn = document.getElementById('btn-refresh-logs');
    const autoscrollChk = document.getElementById('chk-autoscroll');
    const toast = document.getElementById('toast');

    // Global variables
    let isPipelineRunning = false;
    let cachedLogsLength = 0;

    // Toast Notification helper
    function showToast(message, type = 'success') {
        toast.innerText = message;
        toast.className = `toast ${type}`;
        
        // Remove hidden class
        setTimeout(() => {
            toast.classList.remove('hidden');
        }, 50);

        // Hide after 3 seconds
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }

    // Helper to format date strings nicely
    function formatDate(isoStr) {
        if (!isoStr) return '-';
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString();
    }

    // Fetch dashboard status
    async function updateStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();

            // Update pipeline running state
            isPipelineRunning = data.pipeline.running;
            
            if (isPipelineRunning) {
                stateBadge.innerText = `Running (${data.pipeline.currentTask})`;
                stateBadge.className = 'state-badge running';
                triggerTgBtn.disabled = true;
                triggerLiBtn.disabled = true;
            } else {
                stateBadge.innerText = 'Idle';
                stateBadge.className = 'state-badge idle';
                triggerTgBtn.disabled = false;
                triggerLiBtn.disabled = false;
            }

            // Update last execution values
            lastRunLbl.innerText = formatDate(data.pipeline.lastRunTime);
            if (data.pipeline.lastRunResult) {
                lastResultLbl.innerText = data.pipeline.lastRunResult.toUpperCase();
                lastResultLbl.style.color = data.pipeline.lastRunResult === 'success' ? '#10B981' : '#E63946';
            } else {
                lastResultLbl.innerText = '-';
                lastResultLbl.style.color = 'inherit';
            }

            // Update scheduler inputs only if not actively interacting
            const selectTz = document.getElementById('select-timezone');
            if (selectTz && document.activeElement !== selectTz && data.scheduler.timezone) {
                selectTz.value = data.scheduler.timezone;
            }
            if (document.activeElement !== tgTime) {
                tgActive.checked = data.scheduler.telegram.active;
                tgTime.value = data.scheduler.telegram.time;
            }
            if (document.activeElement !== liTime) {
                liActive.checked = data.scheduler.linkedin.active;
                liTime.value = data.scheduler.linkedin.time;
            }
        } catch (e) {
            console.error("Error fetching status", e);
        }
    }

    // Fetch logs
    async function fetchLogs() {
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();
            
            // Only update DOM if log content changed
            if (data.logs.length !== cachedLogsLength) {
                consoleOutput.innerText = data.logs;
                cachedLogsLength = data.logs.length;
                
                // Auto scroll if checked
                if (autoscrollChk.checked) {
                    const body = consoleOutput.parentNode;
                    body.scrollTop = body.scrollHeight;
                }
            }
        } catch (e) {
            console.error("Error fetching logs", e);
        }
    }

    // Load initial config parameters
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            
            if (data.TELEGRAM_BOT_TOKEN) {
                cfgTgToken.value = "EXISTS";
            }
            cfgTgChatId.value = data.TELEGRAM_CHAT_ID || "";
            if (data.OPENROUTER_API_KEY) {
                cfgOrKey.placeholder = "Key exists. Type here to overwrite.";
            }
            if (data.APIFY_API_KEY) {
                cfgApifyKey.placeholder = "Key exists. Type here to overwrite.";
            }
        } catch (e) {
            console.error("Error loading config", e);
        }
    }

    // Trigger pipeline run
    async function triggerPipeline(type) {
        try {
            const res = await fetch('/api/trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Started ${type} execution! Check logs below.`);
                updateStatus();
                // Immediately check logs
                setTimeout(fetchLogs, 500);
            } else {
                showToast(data.error || 'Failed to start execution.', 'error');
            }
        } catch (e) {
            showToast('Network error triggering execution.', 'error');
        }
    }

    // Save scheduler settings
    async function saveScheduler(type, active, time) {
        const selectTz = document.getElementById('select-timezone');
        const tz = selectTz ? selectTz.value : "Asia/Kolkata";
        try {
            const res = await fetch('/api/scheduler', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timezone: tz,
                    [type]: { active, time }
                })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} schedule saved successfully!`);
                updateStatus();
            } else {
                showToast(data.error || 'Failed to save schedule.', 'error');
            }
        } catch (e) {
            showToast('Network error saving schedule.', 'error');
        }
    }

    // Config form submit
    configForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            TELEGRAM_BOT_TOKEN: cfgTgToken.value === "EXISTS" ? "EXISTS" : cfgTgToken.value,
            TELEGRAM_CHAT_ID: cfgTgChatId.value,
            OPENROUTER_API_KEY: cfgOrKey.value ? cfgOrKey.value : undefined,
            APIFY_API_KEY: cfgApifyKey.value ? cfgApifyKey.value : undefined
        };

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast("Configurations saved successfully!");
                loadConfig();
            } else {
                showToast(data.error || "Failed to save configuration.", "error");
            }
        } catch (e) {
            showToast("Network error saving configuration.", "error");
        }
    });

    // Event listeners for trigger buttons
    triggerTgBtn.addEventListener('click', () => triggerPipeline('telegram'));
    triggerLiBtn.addEventListener('click', () => triggerPipeline('linkedin'));

    // Event listeners for scheduler save buttons
    saveTgBtn.addEventListener('click', () => {
        saveScheduler('telegram', tgActive.checked, tgTime.value);
    });
    saveLiBtn.addEventListener('click', () => {
        saveScheduler('linkedin', liActive.checked, liTime.value);
    });

    // Event listeners for toggle switches directly
    tgActive.addEventListener('change', () => {
        saveScheduler('telegram', tgActive.checked, tgTime.value);
    });
    liActive.addEventListener('change', () => {
        saveScheduler('linkedin', liActive.checked, liTime.value);
    });

    const selectTz = document.getElementById('select-timezone');
    if (selectTz) {
        selectTz.addEventListener('change', () => {
            saveScheduler('telegram', tgActive.checked, tgTime.value);
        });
    }

    // Log terminal actions
    clearLogsBtn.addEventListener('click', () => {
        consoleOutput.innerText = "Console cleared by user.";
        cachedLogsLength = 0;
    });

    refreshLogsBtn.addEventListener('click', fetchLogs);

    // Initial setup
    updateStatus();
    fetchLogs();
    loadConfig();

    // Auto update status & logs every 2 seconds
    setInterval(() => {
        updateStatus();
        fetchLogs();
    }, 2000);
});
