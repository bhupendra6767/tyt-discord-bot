# TestYourTier (TYT) — Discord Bot

A production-grade Minecraft PvP ranking bot for competitive tierlist communities.

---

## 🚀 Complete Deployment Guide: Replit → GitHub → Render → UptimeRobot

---

## PHASE 1 — PROJECT STRUCTURE

```
tyt-bot/
  bot.py              ← The entire bot (single file)
requirements.txt      ← Python dependencies
Procfile              ← Tells Render how to start the bot
render.yaml           ← Render auto-deploy config
.gitignore            ← Prevents secrets/DB from being pushed
README.md             ← This file
```

**Required environment variable (NEVER hardcode):**
- `DISCORD_TOKEN` — your Discord bot token

---

## PHASE 2 — GITHUB REPOSITORY

### Step 2.1 — Create Account
1. Go to **https://github.com** → Sign up
2. Username: `bhupendra6767` | Email: `minecraftcraze2@gmail.com`

### Step 2.2 — Create Repository
1. Click **"+"** → **"New repository"**
2. Name: `tyt-discord-bot` | Visibility: **Public**
3. Do NOT add README or .gitignore (already exist)
4. Click **"Create repository"**

---

## PHASE 3 — PUSH CODE TO GITHUB

### Step 3.1 — Open Replit Shell tab (`>`)

### Step 3.2 — Configure Git
```bash
git config --global user.name "bhupendra6767"
git config --global user.email "minecraftcraze2@gmail.com"
```

### Step 3.3 — Push (run all at once)
```bash
git add . && git commit -m "TYT bot update" && git push
```

**If asked for password:** use a Personal Access Token from https://github.com/settings/tokens
(check the **repo** scope, no expiration)

---

## PHASE 4 — RENDER DEPLOYMENT

### Step 4.1 — Create Account
1. Go to **https://render.com** → "Get Started for Free"
2. Sign in with GitHub → Authorize

### Step 4.2 — Create Web Service
1. Click **"New +"** → **"Web Service"**
2. Connect `bhupendra6767/tyt-discord-bot`

### Step 4.3 — Configure
| Field | Value |
|---|---|
| Name | `tyt-discord-bot` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python3 tyt-bot/bot.py` |
| Instance Type | `Free` |

### Step 4.4 — Add DISCORD_TOKEN
1. Environment Variables section → Add Environment Variable
2. Key: `DISCORD_TOKEN` | Value: *(your token)*

### Step 4.5 — Deploy
Click "Create Web Service" → watch logs for:
```
TYT Bot Online — Logged in as YourBot#XXXX
```

---

## PHASE 5 — UPTIMEROBOT (keep-alive)

Render free tier sleeps after 15 min inactivity. UptimeRobot pings every 5 min.

1. Go to **https://uptimerobot.com** → Register free
2. Add New Monitor:
   - Type: `HTTP(s)`
   - URL: `https://tyt-discord-bot.onrender.com`
   - Interval: `Every 5 minutes`
3. Status should show 🟢 Up

---

## BOT SETUP IN DISCORD

After the bot is online:

**Option A — One-click (recommended):**
```
/autosetup
```
Auto-detects all your channels and roles by name, configures everything, and posts all panels in one shot.

**Option B — Manual:**
1. `/setup channels` — assign all channels
2. `/setup roles` — assign staff/tester/admin roles
3. `/setup waitlists` — configure each gamemode waitlist (×8)
4. `/setup tickets_category` — set the ticket category
5. `/setup panels` — posts all panels with buttons

---

## SLASH COMMANDS REFERENCE

### Everyone
| Command | Description |
|---|---|
| `/profile` | View your profile & tier rankings |
| `/results @user` | View any player's rankings with MC skin |
| `/leaderboard` | Top players per gamemode |
| `/cooldown` | Check your test cooldown |
| `/queuestatus` | See all open queues |
| `/serverinfo` | Server statistics dashboard |

### Tester / Staff
| Command | Description |
|---|---|
| `/queue open` | Open a queue for a gamemode |
| `/queue close` | Close a queue |
| `/nextplayer` | Call the next player in queue |
| `/resultsubmit` | Submit test result & assign tier (with MC skin) |
| `/timeout_player` | Remove player from queue (24h cooldown) |
| `/removewaitlist @user` | Remove player from a gamemode waitlist |

### Staff
| Command | Description |
|---|---|
| `/setrank @user` | Manually set a player's tier |
| `/staff_stats` | View tester activity stats |
| `/migration_review` | Approve or deny migration requests |
| `/add @user` | Add user to current ticket channel |
| `/remove @user` | Remove user from current ticket channel |
| `/claim` | Claim this ticket as your responsibility |
| `/requestclose` | Request ticket closure (confirms with staff) |
| `/close` | Immediately close & delete ticket |
| `/panel` | Post a support ticket panel in this channel |
| `/transcript` | Export ticket history as .txt file |
| `/purge [amount]` | Delete up to 100 messages in a channel |
| `/announce` | Send a rich embed announcement to any channel |

### Admin
| Command | Description |
|---|---|
| `/autosetup` | ⚡ One-click: auto-detect channels/roles, configure everything, post all panels |
| `/setup channels` | Manually assign all channels |
| `/setup roles` | Manually assign staff/tester/admin roles |
| `/setup waitlists` | Configure waitlist channel + role per gamemode |
| `/setup tickets_category` | Set the category for ticket channels |
| `/setup panels` | Post all panels to configured channels |
| `/setup database` | Check DB status and stats |

---

## GAMEMODES & TIERS

**Gamemodes:** UHC • Sword • Axe • NethPot • DiaPot • SMP • Mace • CPvP

**Tiers:** HT1–HT5 • MT1–MT5 • LT1–LT5 • Unranked

**Role name auto-detection (WAITLIST_ROLE_MAP):**
| Gamemode | Waitlist Role | Queue Role |
|---|---|---|
| UHC | `Waitlist [UHC]` | `UHC Queue` |
| Sword | `Waitlist [Sword]` | `Sword Queue` |
| Axe | `Waitlist [Axe & Shield]` | `Axe Queue` |
| NethPot | `Waitlist [Neth Pot]` | `NetheritePot Queue` |
| DiaPot | `Waitlist [Dia Pot]` | `DiamondPot Queue` |
| SMP | `Waitlist [SMP Kit]` | `SMP Queue` |
| Mace | `Waitlist [Mace]` | `Mace Queue` |
| CPvP | `Waitlist [CPvP]` | `Crystal Queue` |

---

## STAFF ROLE RECOGNITION

The bot recognises these roles by name — no `/setup roles` required for most features:

**Staff:** Ownership, Founder, Manager, Staff Manager, Media Manager, Admin, Sr.Mod, Moderator, Helper, Trial Staff, TYT Staff, TYT Admin

**Ticket Perm:** [/] Ticket Perm, TYT Admin, Ownership, Founder, Manager, Admin

**Tester:** TYT High Tester, TYT Tester, Mace Tester, Crystal Tester, UHC Tester, Diapot Tester, Nethpot Tester, SMP Tester, Sword Tester, Axe Tester, Tier Testers

---

## UPDATING THE BOT

Every time you change `bot.py` in Replit, push to GitHub to auto-deploy on Render:

```bash
git add . && git commit -m "Update bot" && git push
```

Render detects the push and redeploys in 2–3 minutes automatically.

---

## TECH STACK

- **Python 3.11** — Runtime
- **discord.py 2.x** — Discord API
- **aiosqlite** — Async SQLite ORM
- **Flask** — Keep-alive web server (pings `GET /` → "TYT Bot Online")
- **SQLite** — Persistent database (`tyt_bot.db`, gitignored)
