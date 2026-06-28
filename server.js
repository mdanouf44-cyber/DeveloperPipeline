const express = require('express');
const cron = require('node-cron');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const dotenv = require('dotenv');
const https = require('https');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const CONFIG_PATH = path.join(__dirname, 'scheduler_config.json');
const LOG_FILE_PATH = path.join(__dirname, 'pipeline_run.log');

// Global state
let pipelineState = {
    running: false,
    currentTask: null, // 'telegram' or 'linkedin'
    lastRunTime: null,
    lastRunResult: null // 'success' or 'failed'
};

let activeJobs = {
    telegram: null,
    linkedin: null
};

// Ensure default scheduler config exists
function loadSchedulerConfig() {
    const defaultConfig = {
        timezone: "Asia/Kolkata",
        telegram: { active: true, time: "18:00" },
        linkedin: { active: true, time: "19:30" }
    };
    if (!fs.existsSync(CONFIG_PATH)) {
        fs.writeFileSync(CONFIG_PATH, JSON.stringify(defaultConfig, null, 2));
        return defaultConfig;
    }
    try {
        const loaded = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
        if (!loaded.timezone) {
            loaded.timezone = "Asia/Kolkata";
            fs.writeFileSync(CONFIG_PATH, JSON.stringify(loaded, null, 2));
        }
        return loaded;
    } catch (e) {
        console.error("Error reading scheduler_config.json, returning default", e);
        return defaultConfig;
    }
}

// Append log file on startup to preserve logs across restarts
fs.appendFileSync(LOG_FILE_PATH, `--- Pipeline Logger Initialized ---\n`);

function logToFile(message) {
    const timeStr = new Date().toISOString();
    const formatted = `[${timeStr}] ${message}\n`;
    fs.appendFileSync(LOG_FILE_PATH, formatted);
    console.log(message);
}

// Telegram messaging helpers
function sendTelegramDirect(chatId, text) {
    if (!process.env.TELEGRAM_BOT_TOKEN || !chatId) return;
    const url = `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`;
    const payload = JSON.stringify({
        chat_id: chatId,
        text: text,
        parse_mode: 'HTML',
        disable_web_page_preview: true
    });

    const parsedUrl = new URL(url);
    const options = {
        hostname: parsedUrl.hostname,
        path: parsedUrl.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
        }
    };

    const req = https.request(options, (res) => {
        res.on('data', () => {});
    });
    req.on('error', (err) => {
        console.error("Telegram bot response error:", err.message);
    });
    req.write(payload);
    req.end();
}

function htmlEscape(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Run a list of commands sequentially
function runPipeline(type) {
    if (pipelineState.running) {
        logToFile(`[Warning] Pipeline is already running. Cannot start ${type} task.`);
        return;
    }

    pipelineState.running = true;
    pipelineState.currentTask = type;
    fs.writeFileSync(LOG_FILE_PATH, `=== Starting ${type.toUpperCase()} Pipeline Execution ===\n`);
    sendTelegramDirect(process.env.TELEGRAM_CHAT_ID, `🚀 <b>Starting ${type.toUpperCase()} Pipeline Execution...</b>`);

    let steps = [];
    if (type === 'telegram') {
        steps = [
            { cmd: 'python', args: ['run_generation.py'], desc: 'Fetch Feeds & Generate Post Data' },
            { cmd: 'node', args: ['build_carousel_today.cjs'], desc: 'Compile Carousel Slides & PDF', useNodePath: true },
            { cmd: 'python', args: ['generate_infographic_today.py'], desc: 'Generate Infographic HTML' },
            { cmd: 'node', args: ['cap_infographic_today.cjs'], desc: 'Capture Infographic Image', useNodePath: true },
            { cmd: 'python', args: ['generate_daily_paper.py'], desc: 'Compile Newspaper HTML & PDF' },
            { cmd: 'python', args: ['send_to_telegram.py'], desc: 'Transmit to Telegram Channel' }
        ];
    } else if (type === 'linkedin') {
        steps = [
            { cmd: 'node', args: ['schedule_all_posts.cjs'], desc: 'Schedule Posts on LinkedIn via Puppeteer', useNodePath: true }
        ];
    }

    let currentStep = 0;

    function runNextStep() {
        if (currentStep >= steps.length) {
            pipelineState.running = false;
            pipelineState.currentTask = null;
            pipelineState.lastRunTime = new Date().toISOString();
            pipelineState.lastRunResult = 'success';
            logToFile(`=== ${type.toUpperCase()} Pipeline Completed Successfully! ===`);
            sendTelegramDirect(process.env.TELEGRAM_CHAT_ID, `✅ <b>${type.toUpperCase()} Pipeline Completed Successfully!</b>`);
            return;
        }

        const step = steps[currentStep];
        logToFile(`\n[Step ${currentStep + 1}/${steps.length}] Starting: ${step.desc}...`);
        sendTelegramDirect(process.env.TELEGRAM_CHAT_ID, `⏳ <b>[Step ${currentStep + 1}/${steps.length}]</b> ${step.desc}...`);
        
        const env = { ...process.env };
        if (step.useNodePath) {
            env.NODE_PATH = path.join(__dirname, 'carousel-routine', 'node_modules');
        }

        const proc = spawn(step.cmd, step.args, {
            cwd: __dirname,
            env: env,
            shell: true
        });

        proc.stdout.on('data', (data) => {
            const lines = data.toString().split('\n');
            lines.forEach(line => {
                if (line.trim()) logToFile(`[Stdout] ${line.trim()}`);
            });
        });

        proc.stderr.on('data', (data) => {
            const lines = data.toString().split('\n');
            lines.forEach(line => {
                if (line.trim()) logToFile(`[Stderr] ${line.trim()}`);
            });
        });

        proc.on('close', (code) => {
            logToFile(`[Step finished] ${step.desc} exited with code ${code}`);
            if (code === 0) {
                currentStep++;
                runNextStep();
            } else {
                pipelineState.running = false;
                pipelineState.currentTask = null;
                pipelineState.lastRunTime = new Date().toISOString();
                pipelineState.lastRunResult = 'failed';
                logToFile(`=== ${type.toUpperCase()} Pipeline Failed at Step: ${step.desc} (Exit Code: ${code}) ===`);
                sendTelegramDirect(process.env.TELEGRAM_CHAT_ID, `❌ <b>Pipeline Failed</b> at step: <i>${step.desc}</i> (Exit Code: ${code})`);
            }
        });

        proc.on('error', (err) => {
            pipelineState.running = false;
            pipelineState.currentTask = null;
            pipelineState.lastRunTime = new Date().toISOString();
            pipelineState.lastRunResult = 'failed';
            logToFile(`=== ${type.toUpperCase()} Pipeline Encountered Error: ${err.message} ===`);
            sendTelegramDirect(process.env.TELEGRAM_CHAT_ID, `❌ <b>Pipeline Error:</b> <code>${err.message}</code>`);
        });
    }

    runNextStep();
}

// Setup or reload the Cron Jobs
function initScheduler() {
    const config = loadSchedulerConfig();
    const tz = config.timezone || "Asia/Kolkata";
    
    // Stop existing jobs
    if (activeJobs.telegram) activeJobs.telegram.stop();
    if (activeJobs.linkedin) activeJobs.linkedin.stop();

    logToFile(`Initializing scheduler jobs with timezone: ${tz}...`);

    // Setup Telegram Daily Job
    if (config.telegram && config.telegram.active) {
        const [hour, minute] = config.telegram.time.split(':');
        const cronExpr = `${minute} ${hour} * * *`;
        logToFile(`Scheduled Telegram Pipeline: daily at ${config.telegram.time} ${tz} (Cron: "${cronExpr}")`);
        
        activeJobs.telegram = cron.schedule(cronExpr, () => {
            logToFile(`[Scheduler] Triggered scheduled Telegram Pipeline...`);
            runPipeline('telegram');
        }, {
            scheduled: true,
            timezone: tz
        });
    } else {
        logToFile("Telegram Pipeline schedule is disabled.");
    }

    // Setup LinkedIn Daily Job
    if (config.linkedin && config.linkedin.active) {
        const [hour, minute] = config.linkedin.time.split(':');
        const cronExpr = `${minute} ${hour} * * *`;
        logToFile(`Scheduled LinkedIn Posting: daily at ${config.linkedin.time} ${tz} (Cron: "${cronExpr}")`);
        
        activeJobs.linkedin = cron.schedule(cronExpr, () => {
            logToFile(`[Scheduler] Triggered scheduled LinkedIn Posting...`);
            runPipeline('linkedin');
        }, {
            scheduled: true,
            timezone: tz
        });
    } else {
        logToFile("LinkedIn Posting schedule is disabled.");
    }
}

// Initialize Scheduler on Start
initScheduler();

// Automatically configure Telegram Webhook if running on Render
const RENDER_URL = process.env.RENDER_EXTERNAL_URL;
if (RENDER_URL && process.env.TELEGRAM_BOT_TOKEN) {
    const webhookUrl = `${RENDER_URL}/api/telegram-webhook`;
    const setupUrl = `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/setWebhook?url=${encodeURIComponent(webhookUrl)}`;
    
    logToFile(`[Telegram Bot] Registering webhook at: ${webhookUrl}`);
    https.get(setupUrl, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
            logToFile(`[Telegram Bot] Webhook setup completed. Response: ${data}`);
        });
    }).on('error', (err) => {
        console.error("[Telegram Bot] Webhook setup failed:", err.message);
    });
} else {
    logToFile("[Telegram Bot] Webhook skip: RENDER_EXTERNAL_URL or TELEGRAM_BOT_TOKEN not set.");
}
app.get('/api/status', (req, res) => {
    const config = loadSchedulerConfig();
    res.json({
        serverTime: new Date().toISOString(),
        pipeline: pipelineState,
        scheduler: config,
        configLoaded: {
            telegramToken: !!process.env.TELEGRAM_BOT_TOKEN,
            telegramChatId: !!process.env.TELEGRAM_CHAT_ID,
            openrouterKey: !!process.env.OPENROUTER_API_KEY,
            geminiKey: !!process.env.GEMINI_API_KEY,
            nvidiaKey: !!process.env.NVIDIA_API_KEY,
            nvidiaModel: process.env.NVIDIA_MODEL || ""
        }
    });
});

app.post('/api/trigger', (req, res) => {
    const { type } = req.body;
    if (type !== 'telegram' && type !== 'linkedin') {
        return res.status(400).json({ error: "Invalid pipeline type. Must be 'telegram' or 'linkedin'." });
    }
    if (pipelineState.running) {
        return res.status(400).json({ error: "Pipeline is already running another task." });
    }
    
    // Run asynchronously
    setTimeout(() => runPipeline(type), 100);
    res.json({ success: true, message: `Asynchronously triggered ${type} pipeline execution.` });
});

app.get('/api/logs', (req, res) => {
    if (fs.existsSync(LOG_FILE_PATH)) {
        const logs = fs.readFileSync(LOG_FILE_PATH, 'utf8');
        res.json({ logs });
    } else {
        res.json({ logs: "No logs found." });
    }
});

// Interactive Telegram Webhook Endpoint
app.post('/api/telegram-webhook', (req, res) => {
    // Respond 200 OK immediately to acknowledge receipt to Telegram
    res.sendStatus(200);

    const update = req.body;
    if (!update || !update.message) return;

    const message = update.message;
    const chatId = message.chat.id.toString();
    const text = message.text ? message.text.trim() : '';

    // Authorization check
    const authorizedChatId = process.env.TELEGRAM_CHAT_ID;
    if (!authorizedChatId || chatId !== authorizedChatId.toString()) {
        logToFile(`[Telegram Bot] Unauthorized access attempt from Chat ID: ${chatId}`);
        sendTelegramDirect(chatId, "⚠️ <b>Unauthorized.</b> You do not have access to manage this pipeline.");
        return;
    }

    if (text === '/start' || text === '/help') {
        const helpText = `🤖 <b>Mohammad Anouf Saani Pipeline Bot</b>\n\nUse these commands to manage your pipeline:\n\n👉 /run - Trigger the Daily Telegram Pipeline (Generate & Deliver)\n👉 /status - Check the current pipeline run status\n👉 /logs - Get the last 15 lines of console logs\n👉 /help - Show this menu`;
        sendTelegramDirect(chatId, helpText);
    } else if (text === '/run') {
        if (pipelineState.running) {
            sendTelegramDirect(chatId, "⚠️ <b>Pipeline is already running</b> another task.");
        } else {
            sendTelegramDirect(chatId, "🚀 <b>Pipeline Triggered!</b> Generating content, slides, PDF, and infographics. I will deliver the results directly to this channel when finished.");
            setTimeout(() => runPipeline('telegram'), 100);
        }
    } else if (text === '/status') {
        const lastRun = pipelineState.lastRunTime ? new Date(pipelineState.lastRunTime).toLocaleString("en-US", { timeZone: "Asia/Kolkata" }) : 'N/A';
        const statusText = `ℹ️ <b>Pipeline Status:</b>\n• <b>Current State:</b> <code>${pipelineState.running ? 'RUNNING (' + pipelineState.currentTask.toUpperCase() + ')' : 'IDLE'}</code>\n• <b>Last Run Time:</b> <code>${lastRun}</code>\n• <b>Last Run Result:</b> <code>${pipelineState.lastRunResult ? pipelineState.lastRunResult.toUpperCase() : 'NONE'}</code>`;
        sendTelegramDirect(chatId, statusText);
    } else if (text === '/logs') {
        if (fs.existsSync(LOG_FILE_PATH)) {
            const logs = fs.readFileSync(LOG_FILE_PATH, 'utf8');
            const lines = logs.trim().split('\n');
            const lastLines = lines.slice(-15).join('\n');
            sendTelegramDirect(chatId, `📋 <b>Recent Console Logs:</b>\n<pre>${htmlEscape(lastLines)}</pre>`);
        } else {
            sendTelegramDirect(chatId, "📋 No logs found.");
        }
    } else {
        sendTelegramDirect(chatId, "❓ <b>Unknown command.</b> Type /help to see all available commands.");
    }
});

app.get('/api/config', (req, res) => {
    // Read current environment keys
    res.json({
        TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN || "",
        TELEGRAM_CHAT_ID: process.env.TELEGRAM_CHAT_ID || "",
        OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY ? "EXISTS" : "",
        GEMINI_API_KEY: process.env.GEMINI_API_KEY ? "EXISTS" : "",
        NVIDIA_API_KEY: process.env.NVIDIA_API_KEY ? "EXISTS" : "",
        NVIDIA_MODEL: process.env.NVIDIA_MODEL || "meta/llama-3.3-70b-instruct",
        APIFY_API_KEY: process.env.APIFY_API_KEY ? "EXISTS" : ""
    });
});

app.post('/api/config', (req, res) => {
    const { TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENROUTER_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY, NVIDIA_MODEL, APIFY_API_KEY } = req.body;
    
    // Read, parse and write .env
    const envPath = path.join(__dirname, '.env');
    let envLines = [];
    if (fs.existsSync(envPath)) {
        envLines = fs.readFileSync(envPath, 'utf8').split('\n');
    }

    const updates = {
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        OPENROUTER_API_KEY,
        GEMINI_API_KEY,
        NVIDIA_API_KEY,
        NVIDIA_MODEL,
        APIFY_API_KEY
    };

    let updatedKeys = new Set();
    let newLines = [];

    for (let line of envLines) {
        let matched = false;
        for (let key in updates) {
            if (line.trim().startsWith(`${key}=`)) {
                // If it exists but is set to "EXISTS", do not overwrite it (protect passwords)
                if (updates[key] === "EXISTS" && (key === "OPENROUTER_API_KEY" || key === "GEMINI_API_KEY" || key === "NVIDIA_API_KEY" || key === "APIFY_API_KEY")) {
                    newLines.push(line);
                } else if (updates[key] !== undefined) {
                    newLines.push(`${key}=${updates[key]}`);
                } else {
                    newLines.push(line);
                }
                updatedKeys.add(key);
                matched = true;
                break;
            }
        }
        if (!matched) {
            newLines.push(line);
        }
    }

    // Append new keys
    for (let key in updates) {
        if (!updatedKeys.has(key) && updates[key] !== undefined && updates[key] !== "EXISTS") {
            newLines.push(`${key}=${updates[key]}`);
        }
    }

    fs.writeFileSync(envPath, newLines.join('\n'));
    
    // Reload dotenv
    dotenv.config({ path: envPath, override: true });
    
    logToFile("[Config] Environment variables updated via settings console.");
    res.json({ success: true, message: "Environment configuration saved successfully." });
});

app.post('/api/scheduler', (req, res) => {
    const { telegram, linkedin, timezone } = req.body;
    
    let config = loadSchedulerConfig();
    
    if (timezone) {
        config.timezone = timezone;
    }
    
    if (telegram) {
        config.telegram.active = telegram.active !== undefined ? telegram.active : config.telegram.active;
        config.telegram.time = telegram.time !== undefined ? telegram.time : config.telegram.time;
    }
    
    if (linkedin) {
        config.linkedin.active = linkedin.active !== undefined ? linkedin.active : config.linkedin.active;
        config.linkedin.time = linkedin.time !== undefined ? linkedin.time : config.linkedin.time;
    }

    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
    
    // Reload scheduler cron jobs
    initScheduler();
    
    res.json({ success: true, message: "Scheduler configurations updated and reloaded successfully." });
});

// Health check
app.get('/ping', (req, res) => {
    res.send('pong');
});

app.listen(PORT, () => {
    logToFile(`Dashboard Server started on port ${PORT}. Open http://localhost:${PORT}`);
});
