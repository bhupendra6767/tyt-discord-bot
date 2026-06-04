import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import logging
import json
import re
import os
from datetime import datetime, timezone, timedelta
from threading import Thread
from flask import Flask

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TYT")

# ─────────────────────────────────────────────
# FLASK UPTIME SERVER
# ─────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "TYT Bot Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
DB_PATH = "tyt_bot.db"

TIERS = ["HT1", "HT2", "HT3", "HT4", "HT5", "MT1", "MT2", "MT3", "MT4", "MT5", "LT1", "LT2", "LT3", "LT4", "LT5", "Unranked"]

GAMEMODES = ["UHC", "Sword", "Axe", "NethPot", "DiaPot", "SMP", "Mace", "CPvP"]

GAMEMODE_EMOJIS = {
    "UHC": "🌟",
    "Sword": "⚔️",
    "Axe": "🪓",
    "NethPot": "💀",
    "DiaPot": "💎",
    "SMP": "🌿",
    "Mace": "🔨",
    "CPvP": "🔮",
}

# Exact Discord role names from server — used for name-based lookup
WAITLIST_ROLE_MAP = {
    "UHC":     "Waitlist [UHC]",
    "Sword":   "Waitlist [Sword]",
    "Axe":     "Waitlist [Axe & Shield]",
    "NethPot": "Waitlist [Neth Pot]",
    "DiaPot":  "Waitlist [Dia Pot]",
    "SMP":     "Waitlist [SMP Kit]",
    "Mace":    "Waitlist [Mace]",
    "CPvP":    "Waitlist [CPvP]",
}

QUEUE_ROLE_MAP = {
    "UHC":     "UHC Queue",
    "Sword":   "Sword Queue",
    "Axe":     "Axe Queue",
    "NethPot": "NetheritePot Queue",
    "DiaPot":  "DiamondPot Queue",
    "SMP":     "SMP Queue",
    "Mace":    "Mace Queue",
    "CPvP":    "Crystal Queue",
}

# All staff role names — checked by name so no /setup roles needed
STAFF_ROLE_NAMES = {
    "Ownership", "Founder", "Manager", "Staff Manager", "Media Manager",
    "Admin", "Sr.Mod", "Moderator", "Helper", "Trial Staff",
    "TYT Staff", "TYT Admin",
}

TICKET_PERM_ROLE_NAMES = {"[/] Ticket Perm", "TYT Admin", "Ownership", "Founder", "Manager", "Admin"}

TESTER_ROLE_NAMES = {
    "TYT High Tester", "TYT Tester", "Mace Tester", "Crystal Tester",
    "UHC Tester", "Diapot Tester", "Nethpot Tester", "SMP Tester",
    "Sword Tester", "Axe Tester", "Tier Testers",
}

REGIONS = ["NA", "EU", "AS/AU", "SA"]

COLORS = {
    "gold": 0xFFD700,
    "orange": 0xFF8C00,
    "blue": 0x5865F2,
    "red": 0xED4245,
    "green": 0x57F287,
    "dark": 0x2B2D31,
    "purple": 0x9B59B6,
    "teal": 0x1ABC9C,
    "white": 0xFFFFFF,
    "yellow": 0xFEE75C,
}

COOLDOWN_DAYS = 5

def skin_url(mc_username: str) -> str:
    return f"https://mc-heads.net/avatar/{mc_username}/100"

def skin_body_url(mc_username: str) -> str:
    return f"https://mc-heads.net/body/{mc_username}/100"

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                minecraft_username TEXT NOT NULL,
                region TEXT NOT NULL,
                account_type TEXT NOT NULL,
                registration_date TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                current_tier TEXT DEFAULT 'Unranked',
                peak_tier TEXT DEFAULT 'Unranked',
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                tests_taken INTEGER DEFAULT 0,
                UNIQUE(user_id, gamemode)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                cooldown_end TEXT NOT NULL,
                PRIMARY KEY (user_id, gamemode)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                region TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                position INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gamemode TEXT NOT NULL,
                region TEXT NOT NULL,
                tester_id INTEGER NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT DEFAULT 'open',
                current_player_id INTEGER,
                queue_message_id INTEGER,
                queue_channel_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                tester_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                rank_before TEXT NOT NULL,
                rank_after TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notes TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticket_type TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL,
                closed_at TEXT,
                transcript TEXT,
                claimed_by INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                gamemode TEXT,
                timestamp TEXT NOT NULL,
                details TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS migration_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                from_server TEXT NOT NULL,
                claimed_tier TEXT NOT NULL,
                evidence TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gamemode TEXT NOT NULL,
                current_tier TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                issue TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                gamemode TEXT,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                config TEXT NOT NULL DEFAULT '{}'
            )
        """)
        await db.commit()
        # ── Schema migrations for existing databases ─────────────
        try:
            await db.execute("ALTER TABLE tickets ADD COLUMN claimed_by INTEGER")
            await db.commit()
        except Exception:
            pass  # Column already exists — safe to ignore
    logger.info("Database initialized.")


async def log_event(event_type: str, user_id: int = None, gamemode: str = None, details: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_log (event_type, user_id, gamemode, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (event_type, user_id, gamemode, details, utcnow())
        )
        await db.commit()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# ─────────────────────────────────────────────
# GUILD CONFIG HELPERS
# ─────────────────────────────────────────────
async def get_guild_config(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT config FROM guild_config WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row else {}


async def set_guild_config(guild_id: int, config: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_config (guild_id, config) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET config = excluded.config",
            (guild_id, json.dumps(config))
        )
        await db.commit()

# ─────────────────────────────────────────────
# PERMISSION HELPERS
# ─────────────────────────────────────────────
def has_staff_role(member: discord.Member, staff_role_id: int = None) -> bool:
    if member.guild_permissions.administrator:
        return True
    member_role_names = {r.name for r in member.roles}
    if STAFF_ROLE_NAMES & member_role_names:
        return True
    if staff_role_id:
        return any(r.id == staff_role_id for r in member.roles)
    return False


def has_ticket_perm(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return bool(TICKET_PERM_ROLE_NAMES & {r.name for r in member.roles})


def has_tester_role(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    member_role_names = {r.name for r in member.roles}
    return bool((TESTER_ROLE_NAMES | STAFF_ROLE_NAMES) & member_role_names)


async def is_tester_or_staff(member: discord.Member, guild_id: int) -> bool:
    if member.guild_permissions.administrator:
        return True
    return has_tester_role(member)


def get_role_by_name(guild: discord.Guild, name: str) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=name)

# ─────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ─────────────────────────────────────────────
# VIEWS – REGISTRATION
# ─────────────────────────────────────────────
class RegionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="NA", description="Test on NA servers", emoji="🌎"),
            discord.SelectOption(label="EU", description="Test on EU servers", emoji="🌍"),
            discord.SelectOption(label="AS/AU", description="Test on AS/AU servers", emoji="🌏"),
            discord.SelectOption(label="SA", description="Test on SA servers", emoji="🌎"),
        ]
        super().__init__(placeholder="Select your region", options=options, custom_id="reg_region_select")

    async def callback(self, interaction: discord.Interaction):
        region = self.values[0]
        view = AccountTypeView(region=region)
        embed = discord.Embed(
            title="📋 Register/Update Profile — Step 2/3",
            description="**Select Your Account Type**\n\nChoose whether you have a Premium or Cracked Minecraft account.",
            color=COLORS["blue"]
        )
        embed.add_field(name="Selected Region", value=region, inline=False)
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.edit_message(embed=embed, view=view)


class RegionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(RegionSelect())


class AccountTypeSelect(discord.ui.Select):
    def __init__(self, region: str):
        self.region = region
        options = [
            discord.SelectOption(label="Premium", description="Paid Minecraft account (Java Edition)", emoji="💎"),
            discord.SelectOption(label="Cracked", description="Free/Cracked Minecraft account", emoji="🔓"),
        ]
        super().__init__(placeholder="Select your account type", options=options, custom_id="reg_account_select")

    async def callback(self, interaction: discord.Interaction):
        modal = UsernameModal(region=self.region, account_type=self.values[0])
        await interaction.response.send_modal(modal)


class AccountTypeView(discord.ui.View):
    def __init__(self, region: str):
        super().__init__(timeout=180)
        self.add_item(AccountTypeSelect(region=region))


class UsernameModal(discord.ui.Modal, title="Register/Update Profile — Step 3/3"):
    username = discord.ui.TextInput(
        label="Minecraft Username",
        placeholder="Enter your Minecraft username",
        min_length=3,
        max_length=16,
        required=True
    )

    def __init__(self, region: str, account_type: str):
        super().__init__()
        self.region = region
        self.account_type = account_type

    async def on_submit(self, interaction: discord.Interaction):
        mc_username = self.username.value.strip()
        if not re.match(r'^[a-zA-Z0-9_]{3,16}$', mc_username):
            await interaction.response.send_message(
                "❌ Invalid Minecraft username. Must be 3–16 characters (letters, numbers, underscores only).",
                ephemeral=True
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO users (user_id, minecraft_username, region, account_type, registration_date) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "minecraft_username=excluded.minecraft_username, region=excluded.region, account_type=excluded.account_type",
                (interaction.user.id, mc_username, self.region, self.account_type, utcnow())
            )
            await db.commit()

        await log_event("USER_REGISTERED", interaction.user.id, details=f"MC:{mc_username} Region:{self.region} Type:{self.account_type}")

        embed = discord.Embed(
            title="✅ Profile Registered Successfully!",
            description="You can now join waitlists!",
            color=COLORS["green"]
        )
        embed.set_thumbnail(url=skin_url(mc_username))
        embed.add_field(name="🌐 Region", value=self.region, inline=False)
        embed.add_field(name="💎 Account Type", value=self.account_type, inline=False)
        embed.add_field(name="👤 Username", value=mc_username, inline=False)
        embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# VIEWS – WAITLIST PANEL  (persistent — static custom_ids)
# ─────────────────────────────────────────────
class WaitlistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Register/Update", style=discord.ButtonStyle.danger, emoji="📋", custom_id="wl_register", row=0)
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Register/Update Profile — Step 1/3",
            description="**Select Your Region**\n\nChoose the server region you wish to test on.",
            color=COLORS["blue"]
        )
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.send_message(embed=embed, view=RegionView(), ephemeral=True)

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="wl_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "UHC")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="wl_sword", row=0)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="wl_axe", row=0)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Axe")

    @discord.ui.button(label="Neth Pot", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="wl_nethpot", row=1)
    async def nethpot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "NethPot")

    @discord.ui.button(label="Dia Pot", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="wl_diapot", row=1)
    async def diapot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "DiaPot")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="wl_smp", row=1)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "SMP")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="wl_mace", row=2)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Mace")

    @discord.ui.button(label="CPvP", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="wl_cpvp", row=2)
    async def cpvp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "CPvP")


async def handle_waitlist_join(interaction: discord.Interaction, gamemode: str):
    """Assign waitlist + queue roles by exact name lookup and confirm to user."""
    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
            user = await cur.fetchone()

    if not user:
        await interaction.followup.send(
            "❌ You must register your profile first! Click the **Register/Update** button above.",
            ephemeral=True
        )
        return

    mc_username, region, account_type = user[1], user[2], user[3]
    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    guild = interaction.guild
    member = interaction.user
    roles_added = []
    warnings = []

    # ── Waitlist role ──────────────────────────────────────────
    wl_role_name = WAITLIST_ROLE_MAP.get(gamemode)
    if wl_role_name:
        wl_role = get_role_by_name(guild, wl_role_name)
        if wl_role is None:
            warnings.append(f"⚠️ Waitlist role `{wl_role_name}` not found in server.")
        elif wl_role in member.roles:
            await interaction.followup.send(
                f"⚠️ You already have the **{wl_role_name}** role — you're already on the {gamemode} waitlist!",
                ephemeral=True
            )
            return
        else:
            try:
                await member.add_roles(wl_role, reason=f"Joined {gamemode} waitlist via panel")
                roles_added.append(wl_role_name)
            except discord.Forbidden:
                warnings.append(f"⚠️ Missing permissions to assign `{wl_role_name}`.")
            except discord.HTTPException as e:
                warnings.append(f"⚠️ Could not assign waitlist role: {e}")

    # ── Queue role (ping role for when queue opens) ────────────
    q_role_name = QUEUE_ROLE_MAP.get(gamemode)
    if q_role_name:
        q_role = get_role_by_name(guild, q_role_name)
        if q_role and q_role not in member.roles:
            try:
                await member.add_roles(q_role, reason=f"Queue ping role for {gamemode}")
                roles_added.append(q_role_name)
            except (discord.Forbidden, discord.HTTPException):
                pass  # Queue ping role is optional — don't block the flow

    # ── Also respect /setup-configured role ID as fallback ─────
    cfg = await get_guild_config(guild.id)
    cfg_role_id = cfg.get(f"waitlist_role_{gamemode.lower()}")
    if cfg_role_id and not wl_role_name:
        cfg_role = guild.get_role(cfg_role_id)
        if cfg_role and cfg_role not in member.roles:
            try:
                await member.add_roles(cfg_role, reason=f"Joined {gamemode} waitlist (cfg)")
                roles_added.append(cfg_role.name)
            except (discord.Forbidden, discord.HTTPException):
                pass

    await log_event("WAITLIST_JOIN", member.id, gamemode, details=f"Region:{region} Roles:{roles_added}")

    embed = discord.Embed(
        title="✅ Waitlist Joined!",
        description=f"You have been added to the **{emoji} {gamemode}** waitlist.",
        color=COLORS["green"]
    )
    embed.set_thumbnail(url=skin_url(mc_username))
    if roles_added:
        embed.add_field(name="🏷️ Roles Assigned", value="\n".join(f"• `{r}`" for r in roles_added), inline=False)
    embed.add_field(name="📋 Next Step", value="Go to the waitlist channel and wait for a tester to open the queue.", inline=False)
    embed.add_field(name="👤 Username", value=mc_username, inline=True)
    embed.add_field(name=f"{emoji} Gamemode", value=gamemode, inline=True)
    embed.add_field(name="🌐 Region", value=region, inline=True)
    embed.add_field(name="💎 Account Type", value=account_type, inline=True)
    if warnings:
        embed.add_field(name="⚠️ Notes", value="\n".join(warnings), inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# VIEWS – QUEUE  (persistent — per-gamemode static custom_ids)
# Each gamemode gets its own view so custom_ids are fully static.
# The callbacks query the DB for the active session — no constructor state needed.
# ─────────────────────────────────────────────
def _make_queue_view(gm: str) -> discord.ui.View:
    gm_key = gm.lower()

    class _QueueView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

    join_btn = discord.ui.Button(
        label="Join Queue",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id=f"qjoin_{gm_key}"
    )
    leave_btn = discord.ui.Button(
        label="Leave Queue",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id=f"qleave_{gm_key}"
    )

    async def join_callback(interaction: discord.Interaction):
        await _handle_queue_join(interaction, gm)

    async def leave_callback(interaction: discord.Interaction):
        await _handle_queue_leave(interaction, gm)

    join_btn.callback = join_callback
    leave_btn.callback = leave_callback

    view = _QueueView()
    view.add_item(join_btn)
    view.add_item(leave_btn)
    return view


# Registry of all per-gamemode queue views — populated in on_ready
_queue_views: dict[str, discord.ui.View] = {}


async def _get_open_session(gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
        ) as cur:
            return await cur.fetchone()


async def _handle_queue_join(interaction: discord.Interaction, gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
            user = await cur.fetchone()
        if not user:
            await interaction.response.send_message("❌ You must register your profile first!", ephemeral=True)
            return

        async with db.execute(
            "SELECT * FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
        ) as cur:
            session = await cur.fetchone()
        if not session:
            await interaction.response.send_message("❌ This queue is no longer active.", ephemeral=True)
            return

        async with db.execute(
            "SELECT id FROM queue_members WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
        ) as cur:
            if await cur.fetchone():
                await interaction.response.send_message("⚠️ You are already in this queue!", ephemeral=True)
                return

        async with db.execute(
            "SELECT cooldown_end FROM cooldowns WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
        ) as cur:
            cd = await cur.fetchone()
        if cd:
            try:
                cd_end = datetime.strptime(cd[0], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < cd_end:
                    remaining = cd_end - datetime.now(timezone.utc)
                    h = int(remaining.total_seconds() // 3600)
                    m = int((remaining.total_seconds() % 3600) // 60)
                    await interaction.response.send_message(
                        f"⏳ You are on **{gamemode}** cooldown for **{h}h {m}m**.\nEnds: `{cd[0]}`",
                        ephemeral=True
                    )
                    return
            except Exception:
                pass

        async with db.execute(
            "SELECT COUNT(*) FROM queue_members WHERE gamemode = ?", (gamemode,)
        ) as cur:
            row = await cur.fetchone()
        position = (row[0] if row else 0) + 1

        await db.execute(
            "INSERT INTO queue_members (user_id, gamemode, region, joined_at, position) VALUES (?, ?, ?, ?, ?)",
            (interaction.user.id, gamemode, user[2], utcnow(), position)
        )
        await db.commit()

    await log_event("QUEUE_JOIN", interaction.user.id, gamemode)
    embed = discord.Embed(
        title="✅ Joined Queue",
        description=f"You joined the **{gamemode}** queue.",
        color=COLORS["green"]
    )
    embed.set_thumbnail(url=skin_url(user[1]))
    embed.add_field(name="Your Position", value=f"#{position}", inline=True)
    embed.add_field(name="Username", value=user[1], inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await _refresh_queue_embed(interaction.guild, gamemode)


async def _handle_queue_leave(interaction: discord.Interaction, gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, position FROM queue_members WHERE user_id = ? AND gamemode = ?",
            (interaction.user.id, gamemode)
        ) as cur:
            member = await cur.fetchone()
        if not member:
            await interaction.response.send_message("⚠️ You are not in this queue.", ephemeral=True)
            return
        await db.execute(
            "DELETE FROM queue_members WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
        )
        await db.execute(
            "UPDATE queue_members SET position = position - 1 WHERE gamemode = ? AND position > ?",
            (gamemode, member[1])
        )
        await db.commit()

    await log_event("QUEUE_LEAVE", interaction.user.id, gamemode)
    await interaction.response.send_message("✅ You have left the queue.", ephemeral=True)
    await _refresh_queue_embed(interaction.guild, gamemode)


async def _refresh_queue_embed(guild: discord.Guild, gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
        ) as cur:
            session = await cur.fetchone()
        if not session:
            return

        async with db.execute(
            "SELECT COUNT(*) FROM queue_members WHERE gamemode = ?", (gamemode,)
        ) as cur:
            count_row = await cur.fetchone()
        waiting = count_row[0] if count_row else 0

        current_player_name = "None"
        if session[7]:
            async with db.execute("SELECT minecraft_username FROM users WHERE user_id = ?", (session[7],)) as cur:
                cp = await cur.fetchone()
            if cp:
                current_player_name = cp[0]

        async with db.execute(
            "SELECT q.user_id, u.minecraft_username, q.position FROM queue_members q "
            "JOIN users u ON q.user_id = u.user_id WHERE q.gamemode = ? ORDER BY q.position LIMIT 5",
            (gamemode,)
        ) as cur:
            top_players = await cur.fetchall()

    tester = guild.get_member(session[3])
    tester_name = tester.display_name if tester else "Unknown"
    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")

    embed = discord.Embed(
        title=f"{emoji} {gamemode} Queue — Open",
        description="@here A tester is now available! Join the queue below.",
        color=COLORS["gold"]
    )
    embed.add_field(name="🎯 Current Tester", value=tester_name, inline=True)
    embed.add_field(name="🌐 Region", value=session[2], inline=True)
    embed.add_field(name="👥 Players Waiting", value=str(waiting), inline=True)
    embed.add_field(name="⚔️ Current Test", value=current_player_name, inline=True)

    if top_players:
        queue_list = "\n".join([f"`#{p[2]}` {p[1]}" for p in top_players])
        if waiting > 5:
            queue_list += f"\n*...and {waiting - 5} more*"
        embed.add_field(name="📋 Queue", value=queue_list, inline=False)
    else:
        embed.add_field(name="📋 Queue", value="*No players waiting*", inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • Opened {session[4]}")

    msg_id, chan_id = session[8], session[9]
    if msg_id and chan_id:
        channel = guild.get_channel(chan_id)
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=_queue_views.get(gamemode))
            except Exception:
                pass

# ─────────────────────────────────────────────
# VIEWS – TICKET SYSTEM  (persistent — static custom_ids)
# Ticket lookup is done via interaction.channel.id so no constructor state needed.
# ─────────────────────────────────────────────
class SupportTicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="tkt_support")
    async def support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "support")

    @discord.ui.button(label="Appeal", style=discord.ButtonStyle.danger, emoji="⚖️", custom_id="tkt_appeal")
    async def appeal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "appeal")

    @discord.ui.button(label="Tester App", style=discord.ButtonStyle.success, emoji="✅", custom_id="tkt_tester_app")
    async def tester_app_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "tester_app")

    @discord.ui.button(label="Advertisements", style=discord.ButtonStyle.secondary, emoji="📢", custom_id="tkt_ads")
    async def ads_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "advertisement")


class ReportTicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Report Ticket", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="tkt_report")
    async def report_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "report")


class TicketControlView(discord.ui.View):
    """Persistent ticket control — looks up ticket by channel_id, no stored state."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="tkt_ctrl_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, user_id, status FROM tickets WHERE channel_id = ?", (interaction.channel.id,)
            ) as cur:
                ticket = await cur.fetchone()
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        if ticket[2] == "closed":
            await interaction.response.send_message("⚠️ Ticket is already closed.", ephemeral=True)
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not has_staff_role(interaction.user, cfg.get("staff_role")) and interaction.user.id != ticket[1]:
            await interaction.response.send_message("❌ You cannot close this ticket.", ephemeral=True)
            return
        await _do_close_ticket(interaction, ticket[0], ticket[1])

    @discord.ui.button(label="Delete Ticket", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="tkt_ctrl_delete")
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = await get_guild_config(interaction.guild.id)
        if not has_staff_role(interaction.user, cfg.get("staff_role")):
            await interaction.response.send_message("❌ Only staff can delete tickets.", ephemeral=True)
            return
        await interaction.response.send_message("🗑️ Deleting channel...", ephemeral=True)
        await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")


async def _do_close_ticket(interaction: discord.Interaction, ticket_id: int, owner_id: int):
    messages = []
    async for msg in interaction.channel.history(limit=200, oldest_first=True):
        if not msg.author.bot:
            messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.display_name}: {msg.content}")
    transcript = "\n".join(messages)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status='closed', closed_at=?, transcript=? WHERE id=?",
            (utcnow(), transcript, ticket_id)
        )
        await db.commit()

    embed = discord.Embed(
        title="🔒 Ticket Closed",
        description=f"This ticket has been closed by {interaction.user.mention}.",
        color=COLORS["orange"]
    )
    await interaction.response.send_message(embed=embed)
    owner = interaction.guild.get_member(owner_id)
    if owner:
        try:
            await interaction.channel.set_permissions(owner, send_messages=False)
        except Exception:
            pass
    await log_event("TICKET_CLOSE", interaction.user.id, details=f"Ticket ID:#{ticket_id}")


TICKET_TYPE_INFO = {
    "support":       {"name": "Support",             "emoji": "🎫", "color": COLORS["blue"]},
    "appeal":        {"name": "Appeal",              "emoji": "⚖️", "color": COLORS["orange"]},
    "tester_app":    {"name": "Tester Application",  "emoji": "✅", "color": COLORS["green"]},
    "advertisement": {"name": "Advertisement",        "emoji": "📢", "color": COLORS["purple"]},
    "report":        {"name": "Report",              "emoji": "⚠️", "color": COLORS["red"]},
    "migration":     {"name": "Migration",           "emoji": "🔄", "color": COLORS["teal"]},
}


async def open_ticket(interaction: discord.Interaction, ticket_type: str):
    cfg = await get_guild_config(interaction.guild.id)
    staff_role_id = cfg.get("staff_role")
    tickets_category_id = cfg.get("tickets_category")
    info = TICKET_TYPE_INFO.get(ticket_type, {"name": ticket_type, "emoji": "🎫", "color": COLORS["blue"]})

    channel_name = f"{ticket_type.replace('_', '-')}-{interaction.user.name[:10]}"
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    if staff_role_id:
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            )

    category = interaction.guild.get_channel(tickets_category_id) if tickets_category_id else None

    try:
        channel = await interaction.guild.create_text_channel(
            name=channel_name, category=category, overwrites=overwrites,
            reason=f"{info['name']} ticket by {interaction.user}"
        )
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to create ticket channels.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tickets (user_id, ticket_type, channel_id, created_at) VALUES (?, ?, ?, ?)",
            (interaction.user.id, ticket_type, channel.id, utcnow())
        )
        ticket_id = cur.lastrowid
        await db.commit()

    embed = discord.Embed(
        title=f"{info['emoji']} {info['name']} Ticket",
        description=(
            f"Hello {interaction.user.mention}! A staff member will assist you shortly.\n\n"
            "Please describe your issue in detail. Include any relevant screenshots or evidence."
        ),
        color=info["color"]
    )
    embed.add_field(name="Ticket Type", value=info["name"], inline=True)
    embed.add_field(name="Opened By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Ticket ID", value=f"#{ticket_id}", inline=True)
    embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")

    mention = f"{interaction.user.mention}"
    if staff_role_id:
        mention += f" <@&{staff_role_id}>"
    await channel.send(content=mention, embed=embed, view=TicketControlView())

    await log_event("TICKET_OPEN", interaction.user.id, details=f"Type:{ticket_type} ID:#{ticket_id}")
    await interaction.response.send_message(
        f"✅ Your **{info['name']}** ticket: {channel.mention}", ephemeral=True
    )

# ─────────────────────────────────────────────
# VIEWS – RUBRICS  (persistent — static custom_ids)
# ─────────────────────────────────────────────
RUBRICS_DATA = {
    "UHC": {
        "title": "🌟 UHC Rubrics",
        "description": "Ultra Hardcore scoring guidelines for testers.",
        "scoring": "PvP skill, strafeability, gap mechanics, bow usage, terrain awareness, and decision-making under pressure.",
        "requirements": "Consistent golden apple management, proper bow tracking, and solid rod mechanics.",
        "combat_standards": "W-tap or S-tap timing, gap healing optimization, bow leading, terrain usage.",
        "tester_instructions": "Test 3 rounds minimum. Note notable plays. Evaluate decision-making under low HP situations.",
        "tier_thresholds": "HT1: Elite level. HT5: High consistency. LT1: Solid all-around. LT5: Basic competency. Unranked: No baseline met.",
    },
    "Pot": {
        "title": "🧪 Pot Rubrics",
        "description": "Potion PvP scoring guidelines for testers.",
        "scoring": "Combo ability, pot timing, strafeability, reach control, and overall consistency.",
        "requirements": "Proper pot heal timing, combo extension, and sprint reset mechanics.",
        "combat_standards": "W-tap after combos, clean pot usage under pressure, proper range management.",
        "tester_instructions": "Minimum 3 rounds. Look for pot timing efficiency, combo consistency, and movement control.",
        "tier_thresholds": "HT1: Frame-perfect pot timings, unbeatable combos. LT5: Basic combo with occasional pot usage.",
    },
    "Sword": {
        "title": "⚔️ Sword Rubrics",
        "description": "Sword PvP scoring guidelines for testers.",
        "scoring": "Timing, blocking, sprint resets, positioning, and combo control.",
        "requirements": "Blocking at correct moments, W/S-tap execution, and consistent hitting rhythm.",
        "combat_standards": "Jitter clicking or drag clicking, block hitting, sprint reset mastery.",
        "tester_instructions": "Minimum 3 rounds. Evaluate blocking usage, CPS consistency, and movement under attack.",
        "tier_thresholds": "HT1: Perfect mechanics across all areas. LT5: Understands basic sword mechanics.",
    },
    "Axe": {
        "title": "🪓 Axe Rubrics",
        "description": "Axe PvP scoring guidelines for testers.",
        "scoring": "Cooldown management, shield breaking, positioning, and burst damage windows.",
        "requirements": "Proper axe timing, shield exploitation, and shield break combos required at higher tiers.",
        "combat_standards": "Precise 1.0 cooldown hits, shield break timing, knockback management.",
        "tester_instructions": "Minimum 3 rounds. Focus on attack timing precision and shield mechanics.",
        "tier_thresholds": "HT1: Flawless axe timing and shield exploitation. LT5: Basic axe timing understanding.",
    },
    "SMP": {
        "title": "🌿 SMP Rubrics",
        "description": "SMP PvP scoring guidelines for testers.",
        "scoring": "Gear usage, strafing, totems, arrow management, and overall survival.",
        "requirements": "Totem popping, elytra management, and gear optimization.",
        "combat_standards": "Proper totem timing, crossbow/bow switching, strategic retreat.",
        "tester_instructions": "Evaluate in standard SMP loadout. Test decision-making with limited resources.",
        "tier_thresholds": "HT1: Mastery of all SMP mechanics. LT5: Basic understanding of SMP combat.",
    },
    "Vanilla": {
        "title": "🔮 Vanilla Rubrics",
        "description": "Vanilla PvP scoring guidelines for testers.",
        "scoring": "1.9+ mechanics, shield usage, axe/sword combination, positioning.",
        "requirements": "1.9+ attack cooldown, shield timing, and sprinting mechanics.",
        "combat_standards": "Proper 1.9 attack window, shield break timing, strategic positioning.",
        "tester_instructions": "Minimum 3 rounds vanilla settings. Evaluate cooldown management.",
        "tier_thresholds": "HT1: Perfect 1.9 mechanics mastery. LT5: Basic vanilla PvP understanding.",
    },
    "NethOP": {
        "title": "💀 NethOP Rubrics",
        "description": "NethOP scoring guidelines for testers.",
        "scoring": "Fire resistance management, overpowered kit usage, nether terrain navigation, and raw PvP.",
        "requirements": "OP gear fights, fire management, and the chaotic nether environment.",
        "combat_standards": "Proper enchant leverage, fire resistance timing, aggressive playstyle.",
        "tester_instructions": "Test in standard NethOP settings. Focus on kit management and mechanics.",
        "tier_thresholds": "HT1: Dominates NethOP environment. LT5: Survives basic NethOP encounters.",
    },
    "Mace": {
        "title": "🔨 Mace Rubrics",
        "description": "Mace PvP scoring guidelines for testers.",
        "scoring": "Mace smash accuracy, fall distance exploitation, combo follow-ups, and positioning.",
        "requirements": "Mace smash mechanics correctly and follow up effectively.",
        "combat_standards": "Proper fall height calculation, smash accuracy, and post-smash combos.",
        "tester_instructions": "Minimum 3 encounters. Focus on smash accuracy and combo consistency.",
        "tier_thresholds": "HT1: Perfect mace smash execution. LT5: Basic mace usage understanding.",
    },
    "Cart": {
        "title": "🛒 Cart Rubrics",
        "description": "Cart PvP scoring guidelines for testers.",
        "scoring": "Cart mechanics, desyncs, positioning, and combat while in/around carts.",
        "requirements": "Cart desync mechanics and how to exploit them in combat.",
        "combat_standards": "Proper cart desync timing, hitbox exploitation, and cart combat awareness.",
        "tester_instructions": "Test in cart-enabled environment. Evaluate cart mechanic mastery.",
        "tier_thresholds": "HT1: Master cart desync user. LT5: Basic cart combat awareness.",
    },
    "DiaSMP": {
        "title": "💎 DiaSMP Rubrics",
        "description": "Diamond SMP scoring guidelines for testers.",
        "scoring": "Diamond armor PvP, totem usage, enchant management, and strategy.",
        "requirements": "Diamond tier fights with proper enchant selection and survival instincts.",
        "combat_standards": "Proper diamond armor mechanics, enchant exploitation, strategic combat.",
        "tester_instructions": "Test with standard DiaSMP gear. Focus on gear management and combat quality.",
        "tier_thresholds": "HT1: Elite DiaSMP combat. LT5: Basic diamond armor PvP.",
    },
}

RULESET_DATA = {
    "allowed_mods": [
        "OptiFine / Sodium / Iris (performance only)",
        "Replay Mod (recording only)",
        "Badlion Client / Lunar Client (whitelisted)",
        "Texture packs (non-hitbox altering)",
        "Brightness / Gamma mods",
        "Keystrokes / CPS counter mods",
        "ArmorStatus / PotionStatus HUD",
    ],
    "disallowed_mods": [
        "Kill Aura / Aimbot / AutoClicker",
        "Reach hacks / Anti-KB",
        "Timer / Speed hacks",
        "X-Ray / Freecam",
        "Inventory / Chest hacks",
        "AutoPot / AutoSoup",
        "Any mod giving unfair combat advantage",
    ],
    "match_rules": [
        "Both players must agree on the test server before starting",
        "Tests must be recorded or witnessed by the tester",
        "No interruptions or disconnects allowed (without valid reason)",
        "Player must be in proper kit before test begins",
        "5-day cooldown between tests per gamemode",
        "HT3+ players should open a high-priority ticket",
    ],
    "combat_rules": [
        "No intentional teaming or third-partying",
        "No bug exploitation or glitch abuse",
        "Respectful conduct toward tester required",
        "No stalling or time-wasting tactics",
        "Both parties must acknowledge test completion",
    ],
    "ban_policies": [
        "1st offense cheating: Permanent ban from testing",
        "Severe rule violations: Immediate server ban",
        "False evidence submission: Testing ban + role removal",
        "Harassment of staff/testers: Progressive punishment",
        "Appeals can be submitted via the support channel",
    ],
    "evidence_policies": [
        "All migration requests require proof from the source server",
        "Screenshots must be unedited and clearly show username",
        "Video evidence preferred for tier claims",
        "Evidence must be dated within 4 months for migrations",
        "Falsified evidence results in immediate ban",
    ],
}


class RubricsPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Vanilla", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="rub_vanilla", row=0)
    async def vanilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Vanilla")

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="rub_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "UHC")

    @discord.ui.button(label="Pot", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="rub_pot", row=0)
    async def pot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Pot")

    @discord.ui.button(label="NethOP", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="rub_nethop", row=1)
    async def nethop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "NethOP")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="rub_smp", row=2)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "SMP")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="rub_sword", row=2)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="rub_axe", row=2)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Axe")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="rub_mace", row=3)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Mace")

    @discord.ui.button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒", custom_id="rub_cart", row=3)
    async def cart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "Cart")

    @discord.ui.button(label="DiaSMP", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="rub_diasmp", row=3)
    async def diasmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_rubric(interaction, "DiaSMP")


async def _show_rubric(interaction: discord.Interaction, gamemode: str):
    data = RUBRICS_DATA.get(gamemode)
    if not data:
        await interaction.response.send_message("❌ Rubric not found.", ephemeral=True)
        return
    embed = discord.Embed(title=data["title"], description=data["description"], color=COLORS["gold"])
    embed.add_field(name="📊 Scoring", value=data["scoring"], inline=False)
    embed.add_field(name="📋 Requirements", value=data["requirements"], inline=False)
    embed.add_field(name="⚔️ Combat Standards", value=data["combat_standards"], inline=False)
    embed.add_field(name="👨‍⚖️ Tester Instructions", value=data["tester_instructions"], inline=False)
    embed.add_field(name="🏆 Tier Thresholds", value=data["tier_thresholds"], inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


class RulesetPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Vanilla", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="rul_vanilla", row=0)
    async def vanilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Vanilla")

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="rul_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "UHC")

    @discord.ui.button(label="Pot", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="rul_pot", row=0)
    async def pot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Pot")

    @discord.ui.button(label="NethOP", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="rul_nethop", row=1)
    async def nethop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "NethOP")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="rul_smp", row=2)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "SMP")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="rul_sword", row=2)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="rul_axe", row=2)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Axe")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="rul_mace", row=3)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Mace")

    @discord.ui.button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒", custom_id="rul_cart", row=3)
    async def cart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "Cart")

    @discord.ui.button(label="DiaSMP", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="rul_diasmp", row=3)
    async def diasmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _show_ruleset(interaction, "DiaSMP")


async def _show_ruleset(interaction: discord.Interaction, gamemode: str):
    d = RULESET_DATA
    embed = discord.Embed(
        title=f"📖 {gamemode} Ruleset",
        description=f"Official rules for **{gamemode}** tierlist fights. Any advanced modifications or exploitation of bugs that might give unfair advantage is considered cheating.",
        color=COLORS["teal"]
    )
    embed.add_field(name="✅ Allowed Mods", value="\n".join(f"• {m}" for m in d["allowed_mods"]), inline=False)
    embed.add_field(name="❌ Disallowed Mods", value="\n".join(f"• {m}" for m in d["disallowed_mods"]), inline=False)
    embed.add_field(name="📋 Match Rules", value="\n".join(f"• {m}" for m in d["match_rules"]), inline=False)
    embed.add_field(name="⚔️ Combat Rules", value="\n".join(f"• {m}" for m in d["combat_rules"]), inline=False)
    embed.add_field(name="🔨 Ban Policies", value="\n".join(f"• {m}" for m in d["ban_policies"]), inline=False)
    embed.add_field(name="📸 Evidence Policies", value="\n".join(f"• {m}" for m in d["evidence_policies"]), inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# VIEWS – MIGRATIONS PANEL  (persistent)
# ─────────────────────────────────────────────
class MigrationsPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="How To Migrate", style=discord.ButtonStyle.primary, emoji="❓", custom_id="mig_howto")
    async def howto_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔄 How To Migrate",
            description="Migrate your ranks to TestYourTier (LT3+)",
            color=COLORS["teal"]
        )
        embed.add_field(name="📋 Requirements", value=(
            "• Your migrating tier is **LT3+**\n"
            "• You did **not** test this gamemode here before\n"
            "• Your migrating Tier result was **within 4 months**\n"
            "• You can comply to purge if needed\n"
            "• You can share proper authentication of your account\n"
            "• Your current tier — no migration for Peak Tiers"
        ), inline=False)
        embed.add_field(name="📸 Evidence Required", value=(
            "• Screenshot or video proof from the source server\n"
            "• Clear display of your Minecraft username\n"
            "• Server name visible in the proof\n"
            "• Date of the tier result"
        ), inline=False)
        embed.add_field(name="⏳ Processing Time", value="Migration requests are reviewed within 48–72 hours by senior staff.", inline=False)
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Tier Transfer", style=discord.ButtonStyle.danger, emoji="⚔️", custom_id="mig_transfer")
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
                if not await cur.fetchone():
                    await interaction.response.send_message("❌ You must register your profile first!", ephemeral=True)
                    return
        await interaction.response.send_modal(MigrationModal())


class MigrationModal(discord.ui.Modal, title="Tier Transfer Request"):
    gamemode = discord.ui.TextInput(label="Gamemode", placeholder="e.g. Pot, UHC, Sword", max_length=20, required=True)
    from_server = discord.ui.TextInput(label="Source Server", placeholder="e.g. MCTiers, EU Tiers, Indian Tiers", max_length=50, required=True)
    claimed_tier = discord.ui.TextInput(label="Your Tier on Source Server", placeholder="e.g. LT3, HT5", max_length=10, required=True)
    evidence = discord.ui.TextInput(label="Evidence Link or Description", placeholder="Paste screenshot link or describe your proof", style=discord.TextStyle.paragraph, required=True, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        gm = self.gamemode.value.strip()
        if gm not in GAMEMODES:
            await interaction.response.send_message(f"❌ Invalid gamemode. Valid: {', '.join(GAMEMODES)}", ephemeral=True)
            return
        tier = self.claimed_tier.value.strip().upper()
        if tier not in TIERS:
            await interaction.response.send_message(f"❌ Invalid tier. Valid: {', '.join(TIERS)}", ephemeral=True)
            return
        if TIERS.index(tier) > 7:
            await interaction.response.send_message("❌ Migrations require LT3 or higher.", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO migration_requests (user_id, gamemode, from_server, claimed_tier, evidence, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.user.id, gm, self.from_server.value, tier, self.evidence.value, utcnow())
            )
            await db.commit()

        await log_event("MIGRATION_REQUEST", interaction.user.id, gm, details=f"From:{self.from_server.value} Tier:{tier}")

        embed = discord.Embed(title="✅ Migration Request Submitted", description="Your tier transfer request has been submitted for staff review.", color=COLORS["teal"])
        embed.add_field(name="Gamemode", value=gm, inline=True)
        embed.add_field(name="Source Server", value=self.from_server.value, inline=True)
        embed.add_field(name="Claimed Tier", value=tier, inline=True)
        embed.add_field(name="Status", value="🟡 Pending Review", inline=False)
        embed.set_footer(text="TestYourTier | TYT • Processing: 48–72 hours")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# SLASH COMMANDS – QUEUE
# ─────────────────────────────────────────────
@tree.command(name="queue", description="Open or close a gamemode queue")
@app_commands.describe(action="open or close the queue", gamemode="The gamemode for this queue", region="The region for this queue session")
@app_commands.choices(
    action=[app_commands.Choice(name="open", value="open"), app_commands.Choice(name="close", value="close")],
    gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES],
    region=[app_commands.Choice(name=r, value=r) for r in REGIONS],
)
async def queue_cmd(interaction: discord.Interaction, action: str, gamemode: str, region: str = "NA"):
    if not await is_tester_or_staff(interaction.user, interaction.guild.id):
        await interaction.response.send_message("❌ You need the Tester or Staff role to manage queues.", ephemeral=True)
        return

    if action == "open":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
            ) as cur:
                if await cur.fetchone():
                    await interaction.response.send_message(f"⚠️ A **{gamemode}** queue is already open!", ephemeral=True)
                    return

        await interaction.response.defer()
        cfg = await get_guild_config(interaction.guild.id)
        chan_id = cfg.get(f"waitlist_chan_{gamemode.lower()}")
        channel = interaction.guild.get_channel(chan_id) if chan_id else interaction.channel

        emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
        embed = discord.Embed(
            title=f"{emoji} {gamemode} Queue — Open",
            description="@here A tester is now available! Join the queue below.",
            color=COLORS["gold"]
        )
        embed.add_field(name="🎯 Current Tester", value=interaction.user.display_name, inline=True)
        embed.add_field(name="🌐 Region", value=region, inline=True)
        embed.add_field(name="👥 Players Waiting", value="0", inline=True)
        embed.add_field(name="⚔️ Current Test", value="None", inline=True)
        embed.add_field(name="📋 Queue", value="*No players waiting*", inline=False)
        embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")

        queue_view = _queue_views.get(gamemode)
        msg = await channel.send(content="@here", embed=embed, view=queue_view)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO queue_sessions (gamemode, region, tester_id, opened_at, queue_message_id, queue_channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                (gamemode, region, interaction.user.id, utcnow(), msg.id, channel.id)
            )
            await db.commit()

        await log_event("QUEUE_OPEN", interaction.user.id, gamemode, details=f"Region:{region}")
        await interaction.followup.send(f"✅ **{gamemode}** queue opened in {channel.mention}!", ephemeral=True)

    elif action == "close":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT * FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
            ) as cur:
                session = await cur.fetchone()
            if not session:
                await interaction.response.send_message(f"⚠️ No open **{gamemode}** queue found.", ephemeral=True)
                return
            await db.execute("DELETE FROM queue_members WHERE gamemode = ?", (gamemode,))
            await db.execute(
                "UPDATE queue_sessions SET status='closed', closed_at=? WHERE id=?",
                (utcnow(), session[0])
            )
            await db.commit()

        emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
        closed_embed = discord.Embed(
            title=f"{emoji} {gamemode} Queue Is Now Closed",
            description=f"No {gamemode} Tester Currently Online",
            color=COLORS["dark"]
        )
        closed_embed.add_field(name="Status", value="This queue has been closed. You will be notified when a new queue is opened.", inline=False)
        closed_embed.add_field(name="Session Ended", value=utcnow(), inline=False)
        closed_embed.set_footer(text="TestYourTier | TYT")

        if session[8] and session[9]:
            ch = interaction.guild.get_channel(session[9])
            if ch:
                try:
                    m = await ch.fetch_message(session[8])
                    await m.edit(content=None, embed=closed_embed, view=None)
                except Exception:
                    pass

        await log_event("QUEUE_CLOSE", interaction.user.id, gamemode)
        await interaction.response.send_message(f"✅ **{gamemode}** queue closed.", ephemeral=True)


@tree.command(name="nextplayer", description="Advance to the next player in the queue")
@app_commands.describe(gamemode="The gamemode queue to advance")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def nextplayer_cmd(interaction: discord.Interaction, gamemode: str):
    if not await is_tester_or_staff(interaction.user, interaction.guild.id):
        await interaction.response.send_message("❌ Tester/Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
        ) as cur:
            session = await cur.fetchone()
        if not session:
            await interaction.response.send_message(f"⚠️ No open **{gamemode}** queue.", ephemeral=True)
            return

        async with db.execute(
            "SELECT q.user_id, u.minecraft_username FROM queue_members q "
            "JOIN users u ON q.user_id = u.user_id WHERE q.gamemode = ? ORDER BY q.position LIMIT 1",
            (gamemode,)
        ) as cur:
            next_player = await cur.fetchone()

        if not next_player:
            await interaction.response.send_message("⚠️ Queue is empty.", ephemeral=True)
            return

        await db.execute(
            "DELETE FROM queue_members WHERE user_id = ? AND gamemode = ?", (next_player[0], gamemode)
        )
        await db.execute(
            "UPDATE queue_members SET position = position - 1 WHERE gamemode = ?", (gamemode,)
        )
        await db.execute(
            "UPDATE queue_sessions SET current_player_id = ? WHERE id = ?", (next_player[0], session[0])
        )
        await db.commit()

    member = interaction.guild.get_member(next_player[0])
    embed = discord.Embed(
        title="⚔️ Next Player Called",
        description=f"{member.mention if member else next_player[1]} — you are up for your **{gamemode}** test!",
        color=COLORS["gold"]
    )
    embed.set_thumbnail(url=skin_url(next_player[1]))
    embed.add_field(name="Player", value=next_player[1], inline=True)
    embed.add_field(name="Gamemode", value=gamemode, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)
    await log_event("NEXT_PLAYER", interaction.user.id, gamemode, details=f"Next:{next_player[1]}")
    await _refresh_queue_embed(interaction.guild, gamemode)

# ─────────────────────────────────────────────
# SLASH COMMANDS – RESULT SUBMIT  (replaces /logtest)
# ─────────────────────────────────────────────
@tree.command(name="resultsubmit", description="Submit a completed test result and assign a tier")
@app_commands.describe(
    player="The Discord user who was tested",
    gamemode="The gamemode that was tested",
    rank_before="The player's rank before the test",
    rank_after="The new rank earned",
    notes="Optional notes about the test"
)
@app_commands.choices(
    gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES],
    rank_before=[app_commands.Choice(name=t, value=t) for t in TIERS],
    rank_after=[app_commands.Choice(name=t, value=t) for t in TIERS],
)
async def resultsubmit_cmd(
    interaction: discord.Interaction,
    player: discord.Member,
    gamemode: str,
    rank_before: str,
    rank_after: str,
    notes: str = None
):
    if not await is_tester_or_staff(interaction.user, interaction.guild.id):
        await interaction.response.send_message("❌ Tester/Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT minecraft_username FROM users WHERE user_id = ?", (player.id,)) as cur:
            puser = await cur.fetchone()
        mc_name = puser[0] if puser else player.display_name

        before_idx = TIERS.index(rank_before) if rank_before in TIERS else -1
        after_idx = TIERS.index(rank_after) if rank_after in TIERS else -1

        if rank_after != "Unranked":
            async with db.execute(
                "SELECT current_tier, peak_tier FROM player_ranks WHERE user_id = ? AND gamemode = ?",
                (player.id, gamemode)
            ) as cur:
                existing_rank = await cur.fetchone()

            if existing_rank:
                peak = existing_rank[1]
                peak_idx = TIERS.index(peak) if peak in TIERS else len(TIERS)
                new_peak = rank_after if after_idx < peak_idx else peak
                await db.execute(
                    "UPDATE player_ranks SET current_tier=?, peak_tier=?, tests_taken=tests_taken+1 "
                    "WHERE user_id=? AND gamemode=?",
                    (rank_after, new_peak, player.id, gamemode)
                )
            else:
                await db.execute(
                    "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 1)",
                    (player.id, gamemode, rank_after, rank_after)
                )

        cd_end = datetime.now(timezone.utc) + timedelta(days=COOLDOWN_DAYS)
        await db.execute(
            "INSERT INTO cooldowns (user_id, gamemode, cooldown_end) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, gamemode) DO UPDATE SET cooldown_end=excluded.cooldown_end",
            (player.id, gamemode, cd_end.strftime("%Y-%m-%d %H:%M:%S UTC"))
        )

        await db.execute(
            "INSERT INTO test_logs (player_id, tester_id, gamemode, rank_before, rank_after, timestamp, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (player.id, interaction.user.id, gamemode, rank_before, rank_after, utcnow(), notes)
        )
        await db.commit()

    if rank_before == "Unranked":
        color = COLORS["blue"]
        result_type = "🔵 Placement"
    elif after_idx < before_idx:
        color = COLORS["gold"]
        result_type = "🥇 Promotion"
    elif after_idx == before_idx:
        color = COLORS["orange"]
        result_type = "🟠 No Change"
    else:
        color = COLORS["red"]
        result_type = "🔴 Demotion"

    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    embed = discord.Embed(
        title=f"{mc_name}'s Test Results 🏆",
        color=color
    )
    embed.set_thumbnail(url=skin_url(mc_name))
    embed.add_field(name="Player Name", value=mc_name, inline=False)
    embed.add_field(name="Tester Name", value=interaction.user.mention, inline=False)
    embed.add_field(name="Rank Before", value=rank_before, inline=True)
    embed.add_field(name="Rank Earned", value=rank_after, inline=True)
    embed.add_field(name="Result", value=result_type, inline=True)
    embed.add_field(name="Game Mode", value=f"{emoji} {gamemode}", inline=False)
    if notes:
        embed.add_field(name="📝 Notes", value=notes, inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")

    cfg = await get_guild_config(interaction.guild.id)
    results_chan_id = cfg.get("results_channel")
    if results_chan_id:
        results_chan = interaction.guild.get_channel(results_chan_id)
        if results_chan:
            await results_chan.send(content=player.mention, embed=embed)
            await interaction.response.send_message(f"✅ Result posted in {results_chan.mention}!", ephemeral=True)
            await log_event("TEST_LOGGED", player.id, gamemode, details=f"Before:{rank_before} After:{rank_after} Tester:{interaction.user.id}")
            return

    await interaction.response.send_message(embed=embed)
    await log_event("TEST_LOGGED", player.id, gamemode, details=f"Before:{rank_before} After:{rank_after} Tester:{interaction.user.id}")

# ─────────────────────────────────────────────
# SLASH COMMANDS – RESULTS (view a player's tier)
# ─────────────────────────────────────────────
@tree.command(name="results", description="View a player's tier rankings")
@app_commands.describe(
    member="The player to look up (leave blank for yourself)",
    gamemode="Filter to a specific gamemode (optional)"
)
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def results_cmd(interaction: discord.Interaction, member: discord.Member = None, gamemode: str = None):
    target = member or interaction.user

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (target.id,)) as cur:
            user = await cur.fetchone()

        if gamemode:
            async with db.execute(
                "SELECT gamemode, current_tier, peak_tier, wins, losses, tests_taken FROM player_ranks "
                "WHERE user_id = ? AND gamemode = ?",
                (target.id, gamemode)
            ) as cur:
                ranks = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT gamemode, current_tier, peak_tier, wins, losses, tests_taken FROM player_ranks "
                "WHERE user_id = ? ORDER BY CASE current_tier "
                "WHEN 'HT1' THEN 1 WHEN 'HT2' THEN 2 WHEN 'HT3' THEN 3 "
                "WHEN 'HT4' THEN 4 WHEN 'HT5' THEN 5 WHEN 'LT1' THEN 6 "
                "WHEN 'LT2' THEN 7 WHEN 'LT3' THEN 8 WHEN 'LT4' THEN 9 "
                "WHEN 'LT5' THEN 10 ELSE 11 END",
                (target.id,)
            ) as cur:
                ranks = await cur.fetchall()

    if not user:
        await interaction.response.send_message(
            f"❌ {target.mention} has not registered a profile yet.", ephemeral=True
        )
        return

    mc_name = user[1]
    embed = discord.Embed(
        title=f"🏆 {mc_name}'s Results",
        color=COLORS["gold"]
    )
    embed.set_thumbnail(url=skin_url(mc_name))
    embed.add_field(name="🌐 Region", value=user[2], inline=True)
    embed.add_field(name="💎 Account Type", value=user[3], inline=True)
    embed.add_field(name="📅 Registered", value=user[4], inline=True)

    if ranks:
        for gm, cur_tier, peak_tier, wins, losses, tests in ranks:
            emoji = GAMEMODE_EMOJIS.get(gm, "⚔️")
            tier_display = cur_tier if cur_tier != "Unranked" else "Unranked"
            embed.add_field(
                name=f"{emoji} {gm}",
                value=f"**Tier:** {tier_display}\n**Peak:** {peak_tier}\n**Tests:** {tests}",
                inline=True
            )
    else:
        embed.add_field(
            name="No Rankings Yet",
            value="This player has not been ranked in any gamemode. Join a queue to get tested!",
            inline=False
        )

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
# SLASH COMMANDS – PROFILE
# ─────────────────────────────────────────────
@tree.command(name="profile", description="View your full TYT profile and registration info")
@app_commands.describe(member="The member to look up (leave blank for yourself)")
async def profile_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (target.id,)) as cur:
            user = await cur.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM player_ranks WHERE user_id = ?", (target.id,)
        ) as cur:
            total_gamemodes = (await cur.fetchone())[0]

    if not user:
        await interaction.response.send_message(f"❌ {target.mention} has not registered a profile.", ephemeral=True)
        return

    embed = discord.Embed(title=f"👤 {user[1]}'s Profile", color=COLORS["blue"])
    embed.set_thumbnail(url=skin_url(user[1]))
    embed.add_field(name="🌐 Region", value=user[2], inline=True)
    embed.add_field(name="💎 Account Type", value=user[3], inline=True)
    embed.add_field(name="📅 Registered", value=user[4], inline=True)
    embed.add_field(name="🎮 Ranked Gamemodes", value=str(total_gamemodes), inline=True)
    embed.add_field(name="🔍 View Rankings", value="Use `/results` to see full tier rankings", inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
# SLASH COMMANDS – LEADERBOARD
# ─────────────────────────────────────────────
@tree.command(name="leaderboard", description="View the top players for a gamemode")
@app_commands.describe(gamemode="The gamemode to show rankings for")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def leaderboard_cmd(interaction: discord.Interaction, gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT u.minecraft_username, r.current_tier, r.peak_tier, r.tests_taken "
            "FROM player_ranks r JOIN users u ON r.user_id = u.user_id "
            "WHERE r.gamemode = ? AND r.current_tier != 'Unranked' "
            "ORDER BY CASE r.current_tier "
            "WHEN 'HT1' THEN 1 WHEN 'HT2' THEN 2 WHEN 'HT3' THEN 3 "
            "WHEN 'HT4' THEN 4 WHEN 'HT5' THEN 5 WHEN 'LT1' THEN 6 "
            "WHEN 'LT2' THEN 7 WHEN 'LT3' THEN 8 WHEN 'LT4' THEN 9 "
            "WHEN 'LT5' THEN 10 ELSE 11 END LIMIT 15",
            (gamemode,)
        ) as cur:
            players = await cur.fetchall()

    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    embed = discord.Embed(
        title=f"{emoji} {gamemode} Leaderboard",
        description=f"Top ranked players in **{gamemode}**",
        color=COLORS["gold"]
    )

    if not players:
        embed.add_field(name="No Rankings", value="No players have been ranked in this gamemode yet.", inline=False)
    else:
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 12
        lb_text = "\n".join(
            f"{medals[i]} `#{i+1}` **{name}** — {tier} *(Peak: {peak})* | Tests: {tests}"
            for i, (name, tier, peak, tests) in enumerate(players)
        )
        embed.add_field(name="Rankings", value=lb_text, inline=False)

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
# SLASH COMMANDS – COOLDOWN
# ─────────────────────────────────────────────
@tree.command(name="cooldown", description="Check your testing cooldown status")
@app_commands.describe(gamemode="Check cooldown for a specific gamemode", member="Check another player's cooldown")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def cooldown_cmd(interaction: discord.Interaction, gamemode: str = None, member: discord.Member = None):
    target = member or interaction.user
    async with aiosqlite.connect(DB_PATH) as db:
        if gamemode:
            async with db.execute(
                "SELECT gamemode, cooldown_end FROM cooldowns WHERE user_id = ? AND gamemode = ?",
                (target.id, gamemode)
            ) as cur:
                cds = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT gamemode, cooldown_end FROM cooldowns WHERE user_id = ?", (target.id,)
            ) as cur:
                cds = await cur.fetchall()

    embed = discord.Embed(title=f"⏳ Cooldowns for {target.display_name}", color=COLORS["blue"])
    if not cds:
        embed.description = "✅ No active cooldowns!"
    else:
        now = datetime.now(timezone.utc)
        for gm, cd_end_str in cds:
            try:
                cd_end = datetime.strptime(cd_end_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                if cd_end > now:
                    remaining = cd_end - now
                    h = int(remaining.total_seconds() // 3600)
                    m = int((remaining.total_seconds() % 3600) // 60)
                    embed.add_field(
                        name=f"{GAMEMODE_EMOJIS.get(gm, '⚔️')} {gm}",
                        value=f"⏳ {h}h {m}m remaining\nEnds: `{cd_end_str}`",
                        inline=True
                    )
                else:
                    embed.add_field(name=f"{GAMEMODE_EMOJIS.get(gm, '⚔️')} {gm}", value="✅ Ready to test!", inline=True)
            except Exception:
                embed.add_field(name=gm, value=cd_end_str, inline=True)

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
# SLASH COMMANDS – QUEUE STATUS
# ─────────────────────────────────────────────
@tree.command(name="queuestatus", description="Check the status of all queues")
async def queuestatus_cmd(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT gamemode, region, tester_id, opened_at FROM queue_sessions WHERE status = 'open'"
        ) as cur:
            open_queues = await cur.fetchall()

    embed = discord.Embed(title="📋 Queue Status", color=COLORS["blue"])
    if not open_queues:
        embed.description = "❌ No queues are currently open."
    else:
        for gm, region, tester_id, opened_at in open_queues:
            tester = interaction.guild.get_member(tester_id)
            tester_name = tester.display_name if tester else f"<@{tester_id}>"
            embed.add_field(
                name=f"{GAMEMODE_EMOJIS.get(gm, '⚔️')} {gm}",
                value=f"🌐 {region} | 🎯 {tester_name} | 🕐 {opened_at}",
                inline=False
            )

    open_gms = [q[0] for q in open_queues]
    closed = [gm for gm in GAMEMODES if gm not in open_gms]
    if closed:
        embed.add_field(name="❌ Closed", value=" • ".join(closed), inline=False)

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
# SLASH COMMANDS – SETRANK / STAFF / TIMEOUT
# ─────────────────────────────────────────────
@tree.command(name="setrank", description="Manually set a player's rank (Staff only)")
@app_commands.describe(player="The player to rank", gamemode="The gamemode", tier="The tier to assign")
@app_commands.choices(
    gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES],
    tier=[app_commands.Choice(name=t, value=t) for t in TIERS],
)
async def setrank_cmd(interaction: discord.Interaction, player: discord.Member, gamemode: str, tier: str):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT peak_tier FROM player_ranks WHERE user_id = ? AND gamemode = ?", (player.id, gamemode)
        ) as cur:
            existing = await cur.fetchone()

        peak = existing[0] if existing else tier
        if existing and existing[0] in TIERS and tier in TIERS:
            peak = tier if TIERS.index(tier) < TIERS.index(existing[0]) else existing[0]

        await db.execute(
            "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(user_id, gamemode) DO UPDATE SET current_tier=excluded.current_tier, peak_tier=excluded.peak_tier",
            (player.id, gamemode, tier, peak)
        )
        await db.commit()

    await log_event("RANK_SET", player.id, gamemode, details=f"Tier:{tier} By:{interaction.user.id}")
    embed = discord.Embed(title="✅ Rank Updated", color=COLORS["green"])
    embed.set_thumbnail(url=skin_url(player.display_name))
    embed.add_field(name="Player", value=player.mention, inline=True)
    embed.add_field(name="Gamemode", value=gamemode, inline=True)
    embed.add_field(name="New Tier", value=tier, inline=True)
    embed.set_footer(text=f"Set by {interaction.user.display_name} • TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)


@tree.command(name="timeout_player", description="Remove a player from the queue with a short cooldown (Tester only)")
@app_commands.describe(player="The player to remove", gamemode="The gamemode queue", reason="Reason for removal")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def timeout_player_cmd(interaction: discord.Interaction, player: discord.Member, gamemode: str, reason: str = "No reason provided"):
    if not await is_tester_or_staff(interaction.user, interaction.guild.id):
        await interaction.response.send_message("❌ Tester/Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM queue_members WHERE user_id = ? AND gamemode = ?", (player.id, gamemode)
        )
        cd_end = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.execute(
            "INSERT INTO cooldowns (user_id, gamemode, cooldown_end) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, gamemode) DO UPDATE SET cooldown_end=excluded.cooldown_end",
            (player.id, gamemode, cd_end.strftime("%Y-%m-%d %H:%M:%S UTC"))
        )
        await db.commit()

    await log_event("PLAYER_TIMEOUT", player.id, gamemode, details=f"By:{interaction.user.id} Reason:{reason}")
    embed = discord.Embed(
        title="⏰ Player Removed from Queue",
        description=f"{player.mention} has been removed from **{gamemode}** queue and placed on a 24-hour cooldown.",
        color=COLORS["orange"]
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • Action by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="staff_stats", description="View staff member activity stats (Staff only)")
@app_commands.describe(member="The staff member to check")
async def staff_stats_cmd(interaction: discord.Interaction, member: discord.Member = None):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    target = member or interaction.user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM test_logs WHERE tester_id = ?", (target.id,)) as cur:
            tests = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM queue_sessions WHERE tester_id = ?", (target.id,)) as cur:
            sessions = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT gamemode, COUNT(*) as c FROM test_logs WHERE tester_id = ? GROUP BY gamemode ORDER BY c DESC LIMIT 3",
            (target.id,)
        ) as cur:
            top_gms = await cur.fetchall()

    embed = discord.Embed(title=f"📊 Staff Stats — {target.display_name}", color=COLORS["purple"])
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="⚔️ Tests Completed", value=str(tests), inline=True)
    embed.add_field(name="🔄 Queue Sessions", value=str(sessions), inline=True)
    if top_gms:
        embed.add_field(name="🎮 Top Gamemodes", value="\n".join(f"{GAMEMODE_EMOJIS.get(gm,'⚔️')} {gm}: {c}" for gm, c in top_gms), inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="migration_review", description="Review a migration request (Staff only)")
@app_commands.describe(request_id="The migration request ID", action="approve or deny", reason="Reason for decision")
@app_commands.choices(action=[
    app_commands.Choice(name="approve", value="approve"),
    app_commands.Choice(name="deny", value="deny"),
])
async def migration_review_cmd(interaction: discord.Interaction, request_id: int, action: str, reason: str = None):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM migration_requests WHERE id = ?", (request_id,)) as cur:
            req = await cur.fetchone()
        if not req:
            await interaction.response.send_message("❌ Migration request not found.", ephemeral=True)
            return

        new_status = "approved" if action == "approve" else "denied"
        await db.execute(
            "UPDATE migration_requests SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
            (new_status, interaction.user.id, utcnow(), request_id)
        )
        if action == "approve":
            await db.execute(
                "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 0) "
                "ON CONFLICT(user_id, gamemode) DO UPDATE SET current_tier=excluded.current_tier",
                (req[1], req[2], req[4], req[4])
            )
        await db.commit()

    color = COLORS["green"] if action == "approve" else COLORS["red"]
    embed = discord.Embed(
        title=f"{'✅' if action == 'approve' else '❌'} Migration {action.capitalize()}d",
        color=color
    )
    embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
    embed.add_field(name="Gamemode", value=req[2], inline=True)
    embed.add_field(name="Claimed Tier", value=req[4], inline=True)
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Reviewed by {interaction.user.display_name} • TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

    user = interaction.guild.get_member(req[1])
    if user:
        try:
            dm = discord.Embed(
                title=f"{'✅' if action == 'approve' else '❌'} Your Migration Request has been {action.capitalize()}d",
                color=color
            )
            dm.add_field(name="Gamemode", value=req[2], inline=True)
            dm.add_field(name="Claimed Tier", value=req[4], inline=True)
            if reason:
                dm.add_field(name="Reason", value=reason, inline=False)
            dm.set_footer(text="TestYourTier | TYT")
            await user.send(embed=dm)
        except Exception:
            pass

    await log_event(f"MIGRATION_{action.upper()}", req[1], req[2], details=f"By:{interaction.user.id}")

# ─────────────────────────────────────────────
# SLASH COMMANDS – SETUP GROUP (Admin only)
# ─────────────────────────────────────────────
def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        raise app_commands.MissingPermissions(["administrator"])
    return app_commands.check(predicate)


setup_group = app_commands.Group(name="setup", description="Setup commands for TYT bot (Admin only)")


@setup_group.command(name="panels", description="Post all channel panels")
@is_admin()
async def setup_panels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    cfg = await get_guild_config(interaction.guild.id)
    results = []

    async def post_panel(key: str, embed: discord.Embed, view: discord.ui.View):
        chan_id = cfg.get(key)
        if chan_id:
            ch = interaction.guild.get_channel(chan_id)
            if ch:
                await ch.send(embed=embed, view=view)
                results.append(f"✅ Panel posted in {ch.mention}")
                return True
        return False

    request_embed = discord.Embed(
        title="📝 Evaluation Testing Waitlist",
        description=(
            "Upon applying, you will be added to a waitlist channel. Here you will be pinged when a tester of your region is available.\n"
            "If you are HT3 or higher, create a high ticket\n\n"
            "**① Register Your Profile 💚**\nClick Register / Update Profile to set your in-game username, region, and account type before joining any queue.\n\n"
            "**② Select a Gamemode 🦵**\nClick any gamemode button below to receive the corresponding waitlist role. A tester will pick you up when they open a queue.\n\n"
            "**③ Testing Cooldown ⏱️**\nEach Gamemode has a 5-day cooldown after each test\n\n"
            "**④ Validity 👤**\nProvide authentic information about your account and testing details"
        ),
        color=COLORS["dark"]
    )
    request_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("request_test_channel", request_embed, WaitlistPanel())

    rubrics_embed = discord.Embed(
        title="Ranked Rubrics 🏆",
        description="These are the ranked rubrics for all game modes. Players and testers should follow the scores in the game mode by following the Rubrics. Tests should be done according to the rubrics and TierList Rules. Failure to follow this will result in your test being invalidated by higher staffs.",
        color=COLORS["gold"]
    )
    rubrics_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("rubrics_channel", rubrics_embed, RubricsPanel())

    ruleset_embed = discord.Embed(
        title="Tierlist Ruleset 🥇",
        description="Tierlists Rules are applied to every Tierlist fight ensuring proper and fair advantages over the players. Any advanced modifications or exploitation of the bugs that might get an unfair advantage over your opponents is considered as cheating and if caught will be restricted from the tierlist fights.",
        color=COLORS["teal"]
    )
    ruleset_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("ruleset_channel", ruleset_embed, RulesetPanel())

    mig_embed = discord.Embed(
        title="🔄 Gamemode Migrations",
        description=(
            "Migrate your ranks to TestYourTier - (LT3+)\n\n"
            "**How To Migrate**\n• Your migrating tier is LT3+\n• You did not test the gamemode here before\n"
            "• Your migrating Tier result was within 4 months\n• You can comply to purge if needed\n"
            "• You can share proper authentication of your account\n• Your current tier meaning no migration for Peak Tiers"
        ),
        color=COLORS["teal"]
    )
    mig_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("migrations_channel", mig_embed, MigrationsPanel())

    sup_embed = discord.Embed(
        title="🎫 Support Tickets",
        description="If you **require support**, you may open a ticket\n\n• Prior to doing this, and depending on your issue, it would be considerate to explore ways to resolve the issue yourself.\n• Please have all necessary information ready before opening a ticket.",
        color=COLORS["blue"]
    )
    sup_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("support_channel", sup_embed, SupportTicketPanel())

    rep_embed = discord.Embed(
        title="🚩 Report Tickets",
        description="Open a ticket if you need to report a staff / tester member to server authorities.\n\n• You need concrete evidence about the report.\n• You can take the ticket in these category to report staffs under manager role.",
        color=COLORS["red"]
    )
    rep_embed.set_footer(text="TestYourTier | TYT")
    await post_panel("report_channel", rep_embed, ReportTicketPanel())

    if not results:
        await interaction.followup.send("⚠️ No channels configured. Run `/setup channels` first.", ephemeral=True)
        return
    await interaction.followup.send("\n".join(results), ephemeral=True)


@setup_group.command(name="channels", description="Configure all TYT channels")
@is_admin()
@app_commands.describe(
    request_test="The #request-test channel", results="The #results channel",
    rubrics="The #ranked-rubrics channel", ruleset="The #ranked-ruleset channel",
    migrations="The #migrations channel", support="The #request-support channel",
    report="The #report-tickets channel",
)
async def setup_channels(
    interaction: discord.Interaction,
    request_test: discord.TextChannel = None, results: discord.TextChannel = None,
    rubrics: discord.TextChannel = None, ruleset: discord.TextChannel = None,
    migrations: discord.TextChannel = None, support: discord.TextChannel = None,
    report: discord.TextChannel = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    changes = []
    if request_test: cfg["request_test_channel"] = request_test.id; changes.append(f"Request Test → {request_test.mention}")
    if results: cfg["results_channel"] = results.id; changes.append(f"Results → {results.mention}")
    if rubrics: cfg["rubrics_channel"] = rubrics.id; changes.append(f"Rubrics → {rubrics.mention}")
    if ruleset: cfg["ruleset_channel"] = ruleset.id; changes.append(f"Ruleset → {ruleset.mention}")
    if migrations: cfg["migrations_channel"] = migrations.id; changes.append(f"Migrations → {migrations.mention}")
    if support: cfg["support_channel"] = support.id; changes.append(f"Support → {support.mention}")
    if report: cfg["report_channel"] = report.id; changes.append(f"Report → {report.mention}")
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(title="✅ Channels Configured", description="\n".join(changes) or "No changes.", color=COLORS["green"])
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="roles", description="Configure TYT roles")
@is_admin()
@app_commands.describe(staff_role="The staff role", tester_role="The tester role", admin_role="The admin role")
async def setup_roles(
    interaction: discord.Interaction,
    staff_role: discord.Role = None, tester_role: discord.Role = None, admin_role: discord.Role = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    changes = []
    if staff_role: cfg["staff_role"] = staff_role.id; changes.append(f"Staff → {staff_role.mention}")
    if tester_role: cfg["tester_role"] = tester_role.id; changes.append(f"Tester → {tester_role.mention}")
    if admin_role: cfg["admin_role"] = admin_role.id; changes.append(f"Admin → {admin_role.mention}")
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(title="✅ Roles Configured", description="\n".join(changes) or "No changes.", color=COLORS["green"])
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="waitlists", description="Configure waitlist channel and role for a gamemode")
@is_admin()
@app_commands.describe(gamemode="The gamemode", channel="The waitlist channel", role="The waitlist role")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def setup_waitlists(
    interaction: discord.Interaction,
    gamemode: str, channel: discord.TextChannel = None, role: discord.Role = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    gm_key = gamemode.lower()
    changes = []
    if channel: cfg[f"waitlist_chan_{gm_key}"] = channel.id; changes.append(f"Channel → {channel.mention}")
    if role: cfg[f"waitlist_role_{gm_key}"] = role.id; changes.append(f"Role → {role.mention}")
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(title=f"✅ {gamemode} Waitlist Configured", description="\n".join(changes) or "No changes.", color=COLORS["green"])
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="database", description="Check database status and stats")
@is_admin()
async def setup_database(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur: users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM player_ranks") as cur: ranks = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM test_logs") as cur: tests = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tickets") as cur: tickets = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM queue_sessions WHERE status='open'") as cur: open_q = (await cur.fetchone())[0]

    embed = discord.Embed(title="🗄️ Database Status", color=COLORS["blue"])
    embed.add_field(name="📋 Users", value=str(users), inline=True)
    embed.add_field(name="🏆 Rank Records", value=str(ranks), inline=True)
    embed.add_field(name="⚔️ Tests Logged", value=str(tests), inline=True)
    embed.add_field(name="🎫 Tickets", value=str(tickets), inline=True)
    embed.add_field(name="🟢 Open Queues", value=str(open_q), inline=True)
    embed.add_field(name="💾 Status", value="✅ Online and operational", inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="tickets_category", description="Set the category for ticket channels")
@is_admin()
@app_commands.describe(category="The category where ticket channels will be created")
async def setup_tickets_cat(interaction: discord.Interaction, category: discord.CategoryChannel):
    cfg = await get_guild_config(interaction.guild.id)
    cfg["tickets_category"] = category.id
    await set_guild_config(interaction.guild.id, cfg)
    await interaction.response.send_message(f"✅ Tickets category set to **{category.name}**", ephemeral=True)


@setup_group.command(name="everything", description="Full setup guide")
@is_admin()
async def setup_everything(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ TYT Complete Setup Guide", color=COLORS["blue"])
    embed.add_field(name="Step 1", value="`/setup channels` — Assign all channels", inline=False)
    embed.add_field(name="Step 2", value="`/setup roles` — Assign staff, tester, and admin roles", inline=False)
    embed.add_field(name="Step 3", value="`/setup waitlists` — Set waitlist channel + role per gamemode (×10)", inline=False)
    embed.add_field(name="Step 4", value="`/setup tickets_category` — Set tickets category", inline=False)
    embed.add_field(name="Step 5", value="`/setup panels` — Posts all embeds with buttons", inline=False)
    embed.add_field(name="Step 6", value="`/setup database` — Verify DB is operational", inline=False)
    embed.add_field(name="Gamemodes", value=" • ".join(GAMEMODES), inline=False)
    embed.add_field(name="Tiers", value=" • ".join(TIERS), inline=False)
    embed.set_footer(text="TestYourTier | TYT — Panels persist through restarts.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


tree.add_command(setup_group)

# ─────────────────────────────────────────────
# SLASH COMMANDS – TICKET MANAGEMENT
# /add /remove /requestclose /close /claim /panel
# ─────────────────────────────────────────────

def _ticket_check(interaction: discord.Interaction) -> bool:
    """True if caller has staff/ticket-perm or is the ticket owner."""
    return has_ticket_perm(interaction.user)


async def _get_ticket_by_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
        ) as cur:
            return await cur.fetchone()


@tree.command(name="add", description="Add a user to the current ticket channel")
@app_commands.describe(user="The user to add to this ticket")
async def ticket_add_cmd(interaction: discord.Interaction, user: discord.Member):
    ticket = await _get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return
    if not _ticket_check(interaction):
        await interaction.response.send_message("❌ You don't have permission to manage this ticket.", ephemeral=True)
        return
    try:
        await interaction.channel.set_permissions(
            user,
            read_messages=True,
            send_messages=True,
            reason=f"Added to ticket by {interaction.user}"
        )
        embed = discord.Embed(
            description=f"✅ {user.mention} has been **added** to this ticket by {interaction.user.mention}.",
            color=COLORS["green"]
        )
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to edit this channel.", ephemeral=True)


@tree.command(name="remove", description="Remove a user from the current ticket channel")
@app_commands.describe(user="The user to remove from this ticket")
async def ticket_remove_cmd(interaction: discord.Interaction, user: discord.Member):
    ticket = await _get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return
    if not _ticket_check(interaction):
        await interaction.response.send_message("❌ You don't have permission to manage this ticket.", ephemeral=True)
        return
    if user.id == ticket[1]:  # ticket owner
        await interaction.response.send_message("❌ You cannot remove the ticket owner.", ephemeral=True)
        return
    try:
        await interaction.channel.set_permissions(
            user,
            overwrite=None,
            reason=f"Removed from ticket by {interaction.user}"
        )
        embed = discord.Embed(
            description=f"🚫 {user.mention} has been **removed** from this ticket by {interaction.user.mention}.",
            color=COLORS["red"]
        )
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to edit this channel.", ephemeral=True)


@tree.command(name="requestclose", description="Request that this ticket be closed")
@app_commands.describe(reason="Reason for requesting closure")
async def ticket_requestclose_cmd(interaction: discord.Interaction, reason: str = "No reason provided"):
    ticket = await _get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔒 Close Request",
        description=f"{interaction.user.mention} has requested this ticket be closed.\n\n**Reason:** {reason}",
        color=COLORS["orange"]
    )
    embed.set_footer(text="TestYourTier | TYT • Staff can close with /close")

    class ConfirmCloseView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.button(label="Close Now", style=discord.ButtonStyle.danger, emoji="🔒")
        async def confirm_close(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            if not has_ticket_perm(btn_interaction.user):
                await btn_interaction.response.send_message("❌ Staff only.", ephemeral=True)
                return
            await btn_interaction.response.send_message("🔒 Closing ticket...", ephemeral=True)
            await asyncio.sleep(3)
            try:
                await btn_interaction.channel.delete(reason=f"Closed via request by {btn_interaction.user}")
            except discord.Forbidden:
                pass
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE tickets SET status='closed' WHERE channel_id=?",
                    (btn_interaction.channel.id,)
                )
                await db.commit()

        @discord.ui.button(label="Keep Open", style=discord.ButtonStyle.secondary, emoji="✅")
        async def keep_open(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
            await btn_interaction.response.edit_message(
                content="✅ Ticket kept open.", embed=None, view=None
            )

    await interaction.response.send_message(embed=embed, view=ConfirmCloseView())


@tree.command(name="close", description="Immediately close and delete this ticket (Staff only)")
@app_commands.describe(reason="Reason for closing")
async def ticket_close_cmd(interaction: discord.Interaction, reason: str = "Resolved"):
    ticket = await _get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return
    if not has_ticket_perm(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔒 Ticket Closing",
        description=f"This ticket is being closed by {interaction.user.mention}.\n**Reason:** {reason}\n\nChannel will be deleted in 5 seconds.",
        color=COLORS["red"]
    )
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status='closed' WHERE channel_id=?",
            (interaction.channel.id,)
        )
        await db.commit()

    await asyncio.sleep(5)
    try:
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}: {reason}")
    except discord.Forbidden:
        pass


@tree.command(name="claim", description="Claim this ticket as your responsibility (Staff only)")
async def ticket_claim_cmd(interaction: discord.Interaction):
    ticket = await _get_ticket_by_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return
    if not has_ticket_perm(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET claimed_by=? WHERE channel_id=?",
            (interaction.user.id, interaction.channel.id)
        )
        await db.commit()

    embed = discord.Embed(
        title="🙋 Ticket Claimed",
        description=f"{interaction.user.mention} has claimed this ticket and will handle your request.",
        color=COLORS["blue"]
    )
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)

    try:
        await interaction.channel.edit(name=f"claimed-{interaction.channel.name}", reason="Ticket claimed")
    except Exception:
        pass


@tree.command(name="panel", description="Send the support ticket panel in this channel (Staff only)")
async def ticket_panel_cmd(interaction: discord.Interaction):
    if not has_ticket_perm(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    sup_embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "If you **require support**, you may open a ticket.\n\n"
            "• Prior to doing this, explore ways to resolve the issue yourself.\n"
            "• Please have all necessary information ready before opening a ticket."
        ),
        color=COLORS["blue"]
    )
    sup_embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message("✅ Posting ticket panel...", ephemeral=True)
    await interaction.channel.send(embed=sup_embed, view=SupportTicketPanel())


# ─────────────────────────────────────────────
# SLASH COMMAND – /ANNOUNCE
# ─────────────────────────────────────────────
@tree.command(name="announce", description="Send an announcement embed to a channel (Staff only)")
@app_commands.describe(
    channel="The channel to post in",
    title="Announcement title",
    message="Announcement body (use \\n for new lines)",
    color="Embed colour: gold, blue, red, green, orange, purple, teal",
    ping="Role to ping with the announcement (optional)",
    image_url="Optional image URL to attach to the embed",
)
async def announce_cmd(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str,
    message: str,
    color: str = "gold",
    ping: discord.Role = None,
    image_url: str = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    colour_val = COLORS.get(color.lower(), COLORS["gold"])
    embed = discord.Embed(
        title=title,
        description=message.replace("\\n", "\n"),
        color=colour_val,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"TYT Announcement • Posted by {interaction.user.display_name}")
    if image_url:
        embed.set_image(url=image_url)

    content = ping.mention if ping else None
    try:
        await channel.send(content=content, embed=embed)
        await interaction.followup.send(f"✅ Announcement posted in {channel.mention}.", ephemeral=True)
        await log_event("ANNOUNCE", interaction.user.id, details=f"Channel:{channel.id} Title:{title}")
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to post in that channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to post: {e}", ephemeral=True)


# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()

    # Build and register per-gamemode queue views with static custom_ids
    for gm in GAMEMODES:
        view = _make_queue_view(gm)
        _queue_views[gm] = view
        bot.add_view(view)

    # Register all other persistent views
    bot.add_view(WaitlistPanel())
    bot.add_view(RubricsPanel())
    bot.add_view(RulesetPanel())
    bot.add_view(MigrationsPanel())
    bot.add_view(SupportTicketPanel())
    bot.add_view(ReportTicketPanel())
    bot.add_view(TicketControlView())

    try:
        synced = await tree.sync()
        logger.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    logger.info(f"TYT Bot Online — {bot.user} ({bot.user.id}) — {len(bot.guilds)} guild(s)")


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        try:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        except Exception:
            pass
    else:
        logger.error(f"Command error in /{interaction.command.name if interaction.command else '?'}: {error}")
        try:
            await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
        except Exception:
            pass

# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask uptime server started on port 8080")

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN environment variable is not set!")
        exit(1)

    token = token.strip()
    bot.run(token, log_handler=None)
