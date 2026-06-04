# TestYourTier (TYT) Discord Bot

A production-grade Discord bot for operating a Minecraft PvP ranking community — inspired by MCTiers, Indian Tiers (ITL), EU Tiers, and other competitive tierlist servers.

## Run & Operate

- `python3 tyt-bot/bot.py` — run the TYT Discord bot (also starts Flask uptime server on port 8080)
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000, not used by TYT bot)
- Required env: `DISCORD_TOKEN` — Discord bot token (set in Replit Secrets)

## Stack

- Python 3.11
- discord.py 2.x
- aiosqlite (SQLite async ORM)
- Flask (uptime server for UptimeRobot/Render/Railway)
- Single-file deployment: `tyt-bot/bot.py`
- Database: `tyt_bot.db` (SQLite, persists through restarts)

## Where things live

- `tyt-bot/bot.py` — entire TYT bot (single-file)
- `tyt_bot.db` — SQLite database (auto-created on first run)
- `.local/skills/` — Replit agent skills

## Architecture decisions

- **Single-file bot**: All logic in `tyt-bot/bot.py` for easy deployment anywhere (Replit, Railway, Render, VPS)
- **Flask in a thread**: Uptime server runs in a daemon thread so it never blocks the discord.py asyncio event loop
- **Persistent Views**: All button views registered with `bot.add_view()` on startup so they survive bot restarts
- **Guild config in DB**: All channel/role IDs stored per-guild in `guild_config` table as JSON — no hardcoded IDs
- **SQLite first**: Modular DB layer; can migrate to PostgreSQL by swapping aiosqlite for asyncpg and connection string

## Product

**TestYourTier (TYT)** operates a full Minecraft PvP tier ranking system:
- 10 gamemodes: UHC, Pot, Sword, Axe, SMP, Vanilla, NethOP, Mace, Cart, DiaSMP
- Tier system: HT1–HT5, LT1–LT5, Unranked
- Player registration → waitlist → queue → test → rank assignment flow
- Ticket system: Support, Appeal, Tester App, Advertisements, Reports, Migrations
- Rubrics and Ruleset panels with per-gamemode details
- Admin `/setup` command suite for full server configuration
- Flask endpoint `GET /` → "TYT Bot Online" for uptime monitoring

## Setup Guide (in Discord)

1. Invite bot to server with Administrator permissions
2. `/setup channels` — assign request-test, results, rubrics, ruleset, migrations, support, report channels
3. `/setup roles` — assign staff, tester, admin roles
4. `/setup waitlists` — set waitlist channel + role per gamemode (run once per gamemode)
5. `/setup panels` — posts all embeds with buttons in configured channels
6. `/setup database` — verify DB is operational

## Slash Commands

| Command | Description | Access |
|---|---|---|
| `/profile` | View player profile & rankings | Everyone |
| `/results @user` | View tier rankings with MC skin | Everyone |
| `/leaderboard` | Top players per gamemode | Everyone |
| `/cooldown` | Check testing cooldown | Everyone |
| `/queuestatus` | See all open queues | Everyone |
| `/serverinfo` | Server statistics dashboard | Everyone |
| `/queue open/close` | Open or close a queue | Tester/Staff |
| `/nextplayer` | Advance queue to next player | Tester/Staff |
| `/resultsubmit` | Submit test result & assign tier | Tester/Staff |
| `/timeout_player` | Remove player from queue | Tester/Staff |
| `/removewaitlist @user` | Remove player from waitlist | Staff |
| `/setrank` | Manually set player tier | Staff |
| `/staff_stats` | View tester activity | Staff |
| `/migration_review` | Approve/deny migration requests | Staff |
| `/add @user` | Add user to ticket channel | Staff |
| `/remove @user` | Remove user from ticket channel | Staff |
| `/claim` | Claim ticket ownership | Staff |
| `/requestclose` | Request ticket closure | Staff |
| `/close` | Close & delete ticket immediately | Staff |
| `/panel` | Post ticket panel in channel | Staff |
| `/transcript` | Export ticket as .txt file | Staff |
| `/purge [n]` | Delete up to 100 messages | Staff |
| `/announce` | Post announcement embed | Staff |
| `/autosetup` | ⚡ One-click full server setup | Admin |
| `/setup *` | Manual server configuration | Admin |

## User preferences

- Single-file Python bot, no external dependencies beyond pip packages
- Discord bot token stored as Replit Secret `DISCORD_TOKEN`

## Gotchas

- Bot registers persistent views on `on_ready` — if you add new persistent views, add them there too
- After modifying `bot.py`, restart the "TYT Discord Bot" workflow
- SQLite DB file (`tyt_bot.db`) is gitignored — back it up before destructive operations
- Discord slash commands can take up to 1 hour to propagate globally after first sync

## Pointers

- See the `pnpm-workspace` skill for the Node.js monorepo structure (separate from the bot)
