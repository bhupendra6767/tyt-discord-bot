# TestYourTier (TYT) — Discord Bot

A production-grade Minecraft PvP ranking bot. Full deployment guide below.

---

## 🚀 Complete Deployment Guide: Replit → GitHub → Render → UptimeRobot

---

## PHASE 1 — PROJECT STRUCTURE VERIFICATION

Your project must contain these files before deploying:

```
tyt-bot/
  bot.py              ← The entire bot (single file)
requirements.txt      ← Python dependencies
Procfile              ← Tells Render how to start the bot
render.yaml           ← Render auto-deploy config
.gitignore            ← Prevents secrets/DB from being pushed
README.md             ← This file
```

**Required environment variable (NEVER hardcode this):**
- `DISCORD_TOKEN` — your Discord bot token

---

## PHASE 2 — PREPARE GITHUB REPOSITORY

### Step 2.1 — Create a GitHub Account (if you don't have one)
1. Go to **https://github.com**
2. Click **Sign up**
3. Use email: `minecraftcraze2@gmail.com`
4. Username: `bhupendra6767`
5. Complete signup and verify your email

### Step 2.2 — Create a New Repository
1. Log into **https://github.com**
2. Click the **"+"** icon in the top-right corner
3. Click **"New repository"**
4. Fill in:
   - **Repository name:** `tyt-discord-bot`
   - **Description:** `TestYourTier Minecraft PvP ranking Discord bot`
   - **Visibility:** Select **Public** *(required for free Render)*
   - **Do NOT** check "Add a README file" (we already have one)
   - **Do NOT** add .gitignore (we already have one)
5. Click the green **"Create repository"** button
6. You will see a page with a URL like: `https://github.com/bhupendra6767/tyt-discord-bot`
   **Copy this URL — you will need it in the next step**

---

## PHASE 3 — PUSH CODE FROM REPLIT TO GITHUB

### Step 3.1 — Open the Replit Shell
In Replit, click the **"Shell"** tab at the bottom of the screen (looks like `>`).

### Step 3.2 — Configure Git Identity
Copy and paste these commands one at a time, pressing Enter after each:

```bash
git config --global user.name "bhupendra6767"
git config --global user.email "minecraftcraze2@gmail.com"
```

### Step 3.3 — Initialize and Push
Run these commands one at a time:

```bash
git init
git add .
git commit -m "Initial TYT bot deployment"
git branch -M main
git remote add origin https://github.com/bhupendra6767/tyt-discord-bot.git
git push -u origin main
```

**When asked for username:** type `bhupendra6767` and press Enter

**When asked for password:** You need a Personal Access Token (NOT your GitHub password):
1. Go to **https://github.com/settings/tokens**
2. Click **"Generate new token (classic)"**
3. Note: `Replit push`
4. Expiration: **No expiration**
5. Check the box: ✅ **repo** (first checkbox)
6. Click **"Generate token"** at the bottom
7. **COPY THE TOKEN IMMEDIATELY** (you cannot see it again)
8. Paste it as your password in the shell

### Step 3.4 — Verify Upload
1. Go to `https://github.com/bhupendra6767/tyt-discord-bot`
2. You should see all your files listed
3. Confirm these files are present:
   - ✅ `tyt-bot/bot.py`
   - ✅ `requirements.txt`
   - ✅ `Procfile`
   - ✅ `render.yaml`
   - ✅ `.gitignore`
   - ✅ `README.md`
4. Confirm `tyt_bot.db` is **NOT** there (it's gitignored — good, keeps data private)

---

## PHASE 4 — RENDER DEPLOYMENT

Render is a free cloud hosting platform. It will run your bot 24/7.

### Step 4.1 — Create a Render Account
1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Click **"Continue with GitHub"**
4. Authorize Render to access your GitHub account
5. You are now logged in with your GitHub account ✅

### Step 4.2 — Create a New Web Service
1. On the Render dashboard, click **"New +"** (top right)
2. Click **"Web Service"**
3. Under "Connect a repository", find `bhupendra6767/tyt-discord-bot`
4. Click **"Connect"** next to it

### Step 4.3 — Configure the Service
Fill in these exact settings:

| Field | Value |
|-------|-------|
| **Name** | `tyt-discord-bot` |
| **Region** | Choose closest to you (Singapore for AS/AU, Frankfurt for EU, Oregon for NA) |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python3 tyt-bot/bot.py` |
| **Instance Type** | `Free` |

### Step 4.4 — Add Environment Variable (THE MOST IMPORTANT STEP)
⚠️ **Your bot token must NEVER be in your code. Add it here:**

1. Scroll down to the **"Environment Variables"** section
2. Click **"Add Environment Variable"**
3. Fill in:
   - **Key:** `DISCORD_TOKEN`
   - **Value:** *(paste your actual Discord bot token here)*
4. Click **"Save"**

**How to get your Discord bot token:**
1. Go to **https://discord.com/developers/applications**
2. Click on your bot application
3. Click **"Bot"** in the left sidebar
4. Under the Token section, click **"Reset Token"**
5. Copy the token and paste it into Render

### Step 4.5 — Deploy
1. Scroll to the bottom and click **"Create Web Service"**
2. Render will now build your bot — this takes 2–5 minutes
3. Watch the build logs — you should see:
   ```
   Successfully installed discord.py aiosqlite flask ...
   TYT Bot Online — Logged in as YourBot#XXXX
   ```
4. Once deployed, Render gives you a public URL like:
   `https://tyt-discord-bot.onrender.com`
   **Copy this URL — you need it for UptimeRobot**

### Step 4.6 — Troubleshoot Build Errors
If the build fails, check these common issues:

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: discord` | Make sure `requirements.txt` is in the root folder |
| `DISCORD_TOKEN not set` | Re-check Step 4.4 — add the env variable |
| `port already in use` | The `PORT` env var is auto-set by Render — already handled |
| `No such file: tyt-bot/bot.py` | Make sure `tyt-bot/` folder was pushed to GitHub |

---

## PHASE 5 — KEEP-ALIVE SYSTEM VERIFICATION

The bot already has a Flask web server built in. Here's how it works:

```
GET https://tyt-discord-bot.onrender.com/
→ Response: "TYT Bot Online"
```

This endpoint is what UptimeRobot will ping every 5 minutes to keep Render from sleeping.

**To verify it works:**
1. Open your browser
2. Go to: `https://tyt-discord-bot.onrender.com`
3. You should see the text: **TYT Bot Online**
4. If you see this, the keep-alive system is working ✅

---

## PHASE 6 — UPTIMEROBOT SETUP

Render's free tier sleeps after 15 minutes of inactivity. UptimeRobot pings your bot every 5 minutes to keep it awake.

### Step 6.1 — Create UptimeRobot Account
1. Go to **https://uptimerobot.com**
2. Click **"Register for FREE"**
3. Fill in your details and verify your email

### Step 6.2 — Create a New Monitor
1. After logging in, click **"+ Add New Monitor"**
2. Configure it:

| Field | Value |
|-------|-------|
| **Monitor Type** | `HTTP(s)` |
| **Friendly Name** | `TYT Discord Bot` |
| **URL** | `https://tyt-discord-bot.onrender.com` |
| **Monitoring Interval** | `Every 5 minutes` |

3. Click **"Create Monitor"**

### Step 6.3 — Verify It's Working
1. After a few minutes, the monitor status should show 🟢 **Up**
2. If it shows 🔴 **Down**, check that your Render service is running
3. You will receive email alerts if the bot goes down

---

## PHASE 7 — FINAL VALIDATION CHECKLIST

After completing all steps, verify everything:

| Check | How to verify |
|-------|--------------|
| ✅ Discord bot online | Check your Discord server — bot should show as online |
| ✅ Slash commands work | Type `/profile` in your Discord server |
| ✅ GitHub repo correct | Visit `https://github.com/bhupendra6767/tyt-discord-bot` |
| ✅ Render deployed | Render dashboard shows "Live" in green |
| ✅ Public URL works | Open `https://tyt-discord-bot.onrender.com` — see "TYT Bot Online" |
| ✅ UptimeRobot monitoring | UptimeRobot dashboard shows 🟢 Up |
| ✅ No exposed secrets | Search GitHub for `DISCORD_TOKEN` — should NOT appear in any file |
| ✅ Auto-restart working | Render auto-restarts on crash by default |
| ✅ 24/7 uptime | UptimeRobot pings every 5 min → Render never sleeps |

---

## UPDATING THE BOT AFTER CHANGES

Every time you change `bot.py` in Replit, push to GitHub to auto-deploy:

```bash
git add .
git commit -m "Update bot"
git push
```

Render will automatically detect the push and redeploy within 2–3 minutes.

---

## BOT SETUP IN DISCORD (after deployment)

Once the bot is online, run these commands in your Discord server:

1. `/setup channels` — assign all channels
2. `/setup roles` — assign staff/tester/admin roles
3. `/setup waitlists` — configure each gamemode (run 10 times, once per gamemode)
4. `/setup tickets_category` — set the ticket channels category
5. `/setup panels` — posts all embeds with buttons

---

## SLASH COMMANDS REFERENCE

| Command | Description | Who can use |
|---------|-------------|-------------|
| `/profile` | View profile | Everyone |
| `/results` | View tier rankings (with skin) | Everyone |
| `/leaderboard` | Top players per gamemode | Everyone |
| `/cooldown` | Check test cooldown | Everyone |
| `/queuestatus` | See all open queues | Everyone |
| `/queue open/close` | Manage a queue | Tester/Staff |
| `/nextplayer` | Call next player | Tester/Staff |
| `/resultsubmit` | Submit test result (with skin) | Tester/Staff |
| `/timeout_player` | Remove player from queue | Tester/Staff |
| `/setrank` | Manually set tier | Staff |
| `/staff_stats` | View tester activity | Staff |
| `/migration_review` | Approve/deny migrations | Staff |
| `/setup *` | Full server configuration | Admin |

---

## ENVIRONMENT VARIABLES

| Variable | Where to set | Description |
|----------|-------------|-------------|
| `DISCORD_TOKEN` | Render → Environment Variables | Your bot token — NEVER put in code |
| `PORT` | Auto-set by Render | Flask server port |

---

## TECH STACK

- **Python 3.11** — Runtime
- **discord.py 2.x** — Discord API
- **aiosqlite** — Async SQLite database
- **Flask** — Keep-alive web server
- **SQLite** — Persistent database (`tyt_bot.db`)
