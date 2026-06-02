import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import logging
import json
import re
import os
from datetime import datetime, timezone
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
    flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
DB_PATH = "tyt_bot.db"

TIERS = ["HT1", "HT2", "HT3", "HT4", "HT5", "LT1", "LT2", "LT3", "LT4", "LT5", "Unranked"]

GAMEMODES = ["UHC", "Pot", "Sword", "Axe", "SMP", "Vanilla", "NethOP", "Mace", "Cart", "DiaSMP"]

GAMEMODE_EMOJIS = {
    "UHC": "🌟",
    "Pot": "🧪",
    "Sword": "⚔️",
    "Axe": "🪓",
    "SMP": "🌿",
    "Vanilla": "🔮",
    "NethOP": "💀",
    "Mace": "🔨",
    "Cart": "🛒",
    "DiaSMP": "💎",
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

# Cooldown in days
COOLDOWN_DAYS = 5

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
                transcript TEXT
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
            if row:
                return json.loads(row[0])
            return {}

async def set_guild_config(guild_id: int, config: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_config (guild_id, config) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET config = excluded.config",
            (guild_id, json.dumps(config))
        )
        await db.commit()

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
        super().__init__(placeholder="Select your region", options=options, custom_id="region_select")

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
        super().__init__(placeholder="Select your account type", options=options, custom_id="account_type_select")

    async def callback(self, interaction: discord.Interaction):
        account_type = self.values[0]
        modal = UsernameModal(region=self.region, account_type=account_type)
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
                """INSERT INTO users (user_id, minecraft_username, region, account_type, registration_date)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       minecraft_username = excluded.minecraft_username,
                       region = excluded.region,
                       account_type = excluded.account_type""",
                (interaction.user.id, mc_username, self.region, self.account_type, utcnow())
            )
            await db.commit()

        await log_event("USER_REGISTERED", interaction.user.id, details=f"MC: {mc_username}, Region: {self.region}, Type: {self.account_type}")

        embed = discord.Embed(
            title="✅ Profile Registered Successfully!",
            description="You can now join waitlists!",
            color=COLORS["green"]
        )
        embed.add_field(name="🌐 Region", value=self.region, inline=False)
        embed.add_field(name="💎 Account Type", value=self.account_type, inline=False)
        embed.add_field(name="👤 Username", value=mc_username, inline=False)
        embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# VIEWS – WAITLIST PANEL
# ─────────────────────────────────────────────
class WaitlistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Register/Update", style=discord.ButtonStyle.danger, emoji="📋", custom_id="waitlist_register", row=0)
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Register/Update Profile — Step 1/3",
            description="**Select Your Region**\n\nChoose the server region you wish to test on.",
            color=COLORS["blue"]
        )
        embed.set_footer(text="TestYourTier | TYT")
        view = RegionView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="waitlist_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "UHC")

    @discord.ui.button(label="Pot", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="waitlist_pot", row=0)
    async def pot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Pot")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="waitlist_mace", row=1)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Mace")

    @discord.ui.button(label="NethOP", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="waitlist_nethop", row=1)
    async def nethop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "NethOP")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="waitlist_smp", row=2)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "SMP")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="waitlist_sword", row=2)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="waitlist_axe", row=2)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Axe")

    @discord.ui.button(label="Vanilla", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="waitlist_vanilla", row=3)
    async def vanilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Vanilla")

    @discord.ui.button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒", custom_id="waitlist_cart", row=3)
    async def cart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "Cart")

    @discord.ui.button(label="DiaSmp", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="waitlist_diasmp", row=3)
    async def diasmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_waitlist_join(interaction, "DiaSMP")


async def handle_waitlist_join(interaction: discord.Interaction, gamemode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
            user = await cur.fetchone()

    if not user:
        await interaction.response.send_message(
            "❌ You must register your profile first! Click the **'Register / Update Profile'** button.",
            ephemeral=True
        )
        return

    mc_username = user[1]
    region = user[2]
    account_type = user[3]

    cfg = await get_guild_config(interaction.guild.id)
    waitlist_role_key = f"waitlist_role_{gamemode.lower()}"
    role_id = cfg.get(waitlist_role_key)

    if role_id:
        role = interaction.guild.get_role(role_id)
        if role:
            if role in interaction.user.roles:
                await interaction.response.send_message(
                    f"⚠️ You are already on the **{gamemode}** waitlist!",
                    ephemeral=True
                )
                return
            await interaction.user.add_roles(role, reason=f"Joined {gamemode} waitlist")

    await log_event("WAITLIST_JOIN", interaction.user.id, gamemode, details=f"Region: {region}")

    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    embed = discord.Embed(
        title="✅ Waitlist Role Added!",
        description=f"You have been given the **{gamemode}** waitlist role",
        color=COLORS["green"]
    )
    if role_id:
        embed.add_field(name="Next Step", value=f"Go to the **{gamemode.lower()}-waitlist** channel and wait for a tester to open queue", inline=False)
    embed.add_field(name="👤 Username", value=mc_username, inline=True)
    embed.add_field(name=f"{emoji} Gamemode", value=gamemode, inline=True)
    embed.add_field(name="🌐 Region", value=region, inline=True)
    embed.add_field(name="💎 Account Type", value=account_type, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# VIEWS – QUEUE
# ─────────────────────────────────────────────
class QueueView(discord.ui.View):
    def __init__(self, gamemode: str, session_id: int):
        super().__init__(timeout=None)
        self.gamemode = gamemode
        self.session_id = session_id

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.success, emoji="✅", custom_id="queue_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_queue_join(interaction, self.gamemode, self.session_id)

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, emoji="❌", custom_id="queue_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_queue_leave(interaction, self.gamemode, self.session_id)


async def handle_queue_join(interaction: discord.Interaction, gamemode: str, session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
            user = await cur.fetchone()
        if not user:
            await interaction.response.send_message("❌ You must register your profile first!", ephemeral=True)
            return

        async with db.execute(
            "SELECT * FROM queue_sessions WHERE id = ? AND status = 'open'", (session_id,)
        ) as cur:
            session = await cur.fetchone()
        if not session:
            await interaction.response.send_message("❌ This queue is no longer active.", ephemeral=True)
            return

        async with db.execute(
            "SELECT * FROM queue_members WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            await interaction.response.send_message("⚠️ You are already in this queue!", ephemeral=True)
            return

        async with db.execute(
            "SELECT cooldown_end FROM cooldowns WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
        ) as cur:
            cd = await cur.fetchone()
        if cd:
            from datetime import datetime
            try:
                cd_end = datetime.strptime(cd[0], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < cd_end:
                    await interaction.response.send_message(
                        f"⏳ You are on cooldown for **{gamemode}**. Cooldown ends: {cd_end.strftime('%Y-%m-%d %H:%M UTC')}",
                        ephemeral=True
                    )
                    return
            except Exception:
                pass

        async with db.execute(
            "SELECT COUNT(*) FROM queue_members WHERE gamemode = ?", (gamemode,)
        ) as cur:
            count_row = await cur.fetchone()
        position = (count_row[0] if count_row else 0) + 1

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
    embed.add_field(name="Your Position", value=f"#{position}", inline=True)
    embed.add_field(name="Username", value=user[1], inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await refresh_queue_embed(interaction, gamemode, session_id)


async def handle_queue_leave(interaction: discord.Interaction, gamemode: str, session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM queue_members WHERE user_id = ? AND gamemode = ?", (interaction.user.id, gamemode)
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
            (gamemode, member[5])
        )
        await db.commit()

    await log_event("QUEUE_LEAVE", interaction.user.id, gamemode)
    await interaction.response.send_message("✅ You have left the queue.", ephemeral=True)
    await refresh_queue_embed(interaction, gamemode, session_id)


async def refresh_queue_embed(interaction: discord.Interaction, gamemode: str, session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM queue_sessions WHERE id = ?", (session_id,)
        ) as cur:
            session = await cur.fetchone()
        if not session:
            return

        async with db.execute(
            "SELECT COUNT(*) FROM queue_members WHERE gamemode = ?", (gamemode,)
        ) as cur:
            count_row = await cur.fetchone()
        waiting = count_row[0] if count_row else 0

        current_player_id = session[7]
        current_player_name = "None"
        if current_player_id:
            async with db.execute("SELECT minecraft_username FROM users WHERE user_id = ?", (current_player_id,)) as cur:
                cp = await cur.fetchone()
            if cp:
                current_player_name = cp[0]

        async with db.execute(
            "SELECT q.user_id, u.minecraft_username, q.position FROM queue_members q "
            "JOIN users u ON q.user_id = u.user_id WHERE q.gamemode = ? ORDER BY q.position LIMIT 5",
            (gamemode,)
        ) as cur:
            top_players = await cur.fetchall()

    tester = interaction.guild.get_member(session[3])
    tester_name = tester.display_name if tester else "Unknown"
    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")

    embed = discord.Embed(
        title=f"{emoji} {gamemode} Queue — Open",
        description=f"@here A tester is now available! Join the queue below.",
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

    msg_id = session[8]
    chan_id = session[9]
    if msg_id and chan_id:
        channel = interaction.guild.get_channel(chan_id)
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=QueueView(gamemode, session_id))
            except Exception:
                pass


async def build_queue_embed(gamemode: str, region: str, tester: discord.Member, session_id: int):
    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    embed = discord.Embed(
        title=f"{emoji} {gamemode} Queue — Open",
        description=f"@here A tester is now available! Join the queue below.",
        color=COLORS["gold"]
    )
    embed.add_field(name="🎯 Current Tester", value=tester.display_name, inline=True)
    embed.add_field(name="🌐 Region", value=region, inline=True)
    embed.add_field(name="👥 Players Waiting", value="0", inline=True)
    embed.add_field(name="⚔️ Current Test", value="None", inline=True)
    embed.add_field(name="📋 Queue", value="*No players waiting*", inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")
    return embed


# ─────────────────────────────────────────────
# VIEWS – TICKET SYSTEM
# ─────────────────────────────────────────────
class SupportTicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="ticket_support")
    async def support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "support")

    @discord.ui.button(label="Appeal", style=discord.ButtonStyle.danger, emoji="⚖️", custom_id="ticket_appeal")
    async def appeal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "appeal")

    @discord.ui.button(label="Tester App", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_tester_app")
    async def tester_app_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "tester_app")

    @discord.ui.button(label="Advertisements", style=discord.ButtonStyle.secondary, emoji="📢", custom_id="ticket_ads")
    async def ads_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "advertisement")


class ReportTicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Report Ticket", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="ticket_report")
    async def report_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "report")


class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket(interaction, self.ticket_id)

    @discord.ui.button(label="Delete Ticket", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = await get_guild_config(interaction.guild.id)
        staff_role_id = cfg.get("staff_role")
        if not has_staff_role(interaction.user, staff_role_id):
            await interaction.response.send_message("❌ Only staff can delete tickets.", ephemeral=True)
            return
        await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")


def has_staff_role(member: discord.Member, staff_role_id: int = None) -> bool:
    if member.guild_permissions.administrator:
        return True
    if staff_role_id:
        return any(r.id == staff_role_id for r in member.roles)
    return False


TICKET_TYPE_INFO = {
    "support": {"name": "Support", "emoji": "🎫", "color": COLORS["blue"]},
    "appeal": {"name": "Appeal", "emoji": "⚖️", "color": COLORS["orange"]},
    "tester_app": {"name": "Tester Application", "emoji": "✅", "color": COLORS["green"]},
    "advertisement": {"name": "Advertisement", "emoji": "📢", "color": COLORS["purple"]},
    "report": {"name": "Report", "emoji": "⚠️", "color": COLORS["red"]},
    "migration": {"name": "Migration", "emoji": "🔄", "color": COLORS["teal"]},
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
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)

    category = None
    if tickets_category_id:
        category = interaction.guild.get_channel(tickets_category_id)

    try:
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
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
            f"Please describe your issue in detail. Include any relevant screenshots or evidence."
        ),
        color=info["color"]
    )
    embed.add_field(name="Ticket Type", value=info["name"], inline=True)
    embed.add_field(name="Opened By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Ticket ID", value=f"#{ticket_id}", inline=True)
    embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")

    await channel.send(
        content=f"{interaction.user.mention}" + (f" <@&{staff_role_id}>" if staff_role_id else ""),
        embed=embed,
        view=TicketControlView(ticket_id)
    )

    await log_event("TICKET_OPEN", interaction.user.id, details=f"Type: {ticket_type}, ID: #{ticket_id}")
    await interaction.response.send_message(
        f"✅ Your **{info['name']}** ticket has been created: {channel.mention}",
        ephemeral=True
    )


async def close_ticket(interaction: discord.Interaction, ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) as cur:
            ticket = await cur.fetchone()
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        if ticket[4] == "closed":
            await interaction.response.send_message("⚠️ Ticket is already closed.", ephemeral=True)
            return

        messages = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.display_name}: {msg.content}")
        transcript = "\n".join(messages)

        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ?, transcript = ? WHERE id = ?",
            (utcnow(), transcript, ticket_id)
        )
        await db.commit()

    cfg = await get_guild_config(interaction.guild.id)
    staff_role_id = cfg.get("staff_role")
    if not has_staff_role(interaction.user, staff_role_id) and interaction.user.id != ticket[1]:
        await interaction.response.send_message("❌ You cannot close this ticket.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔒 Ticket Closed",
        description=f"This ticket has been closed by {interaction.user.mention}.",
        color=COLORS["orange"]
    )
    await interaction.response.send_message(embed=embed)
    await interaction.channel.set_permissions(
        interaction.guild.get_member(ticket[1]),
        send_messages=False
    )
    await log_event("TICKET_CLOSE", interaction.user.id, details=f"Ticket ID: #{ticket_id}")


# ─────────────────────────────────────────────
# VIEWS – RUBRICS PANEL
# ─────────────────────────────────────────────
RUBRICS_DATA = {
    "UHC": {
        "title": "🌟 UHC Rubrics",
        "description": "Ultra Hardcore scoring guidelines for testers.",
        "scoring": "Tests are judged on: PvP skill, strafeability, gap mechanics, bow usage, terrain awareness, and decision-making under pressure.",
        "requirements": "Player must demonstrate consistent golden apple management, proper bow tracking, and solid rod mechanics.",
        "combat_standards": "Expected: proper W-tap or S-tap timing, gap healing optimization, bow leading, terrain usage.",
        "tester_instructions": "Test 3 rounds minimum. Note notable plays. Evaluate decision-making under low HP situations.",
        "tier_thresholds": "HT1: Elite level. HT5: High consistency. LT1: Solid all-around. LT5: Basic competency. Unranked: No baseline met.",
    },
    "Pot": {
        "title": "🧪 Pot Rubrics",
        "description": "Potion PvP scoring guidelines for testers.",
        "scoring": "Judged on: combo ability, pot timing, strafeability, reach control, and overall consistency.",
        "requirements": "Must show proper pot heal timing, combo extension, and sprint reset mechanics.",
        "combat_standards": "Expected: W-tap after combos, clean pot usage under pressure, proper range management.",
        "tester_instructions": "Minimum 3 rounds. Look for pot timing efficiency, combo consistency, and movement control.",
        "tier_thresholds": "HT1: Frame-perfect pot timings, unbeatable combos. LT5: Basic combo with occasional pot usage.",
    },
    "Sword": {
        "title": "⚔️ Sword Rubrics",
        "description": "Sword PvP scoring guidelines for testers.",
        "scoring": "Judged on: timing, blocking, sprint resets, positioning, and combo control.",
        "requirements": "Must demonstrate blocking at correct moments, W/S-tap execution, and consistent hitting rhythm.",
        "combat_standards": "Expected: proper jitter clicking or drag clicking, block hitting, sprint reset mastery.",
        "tester_instructions": "Minimum 3 rounds. Evaluate blocking usage, CPS consistency, and movement under attack.",
        "tier_thresholds": "HT1: Perfect mechanics across all areas. LT5: Understands basic sword mechanics.",
    },
    "Axe": {
        "title": "🪓 Axe Rubrics",
        "description": "Axe PvP scoring guidelines for testers.",
        "scoring": "Judged on: cooldown management, shield breaking, positioning, and burst damage windows.",
        "requirements": "Proper axe timing, shield exploitation, and shield break combos required at higher tiers.",
        "combat_standards": "Expected: precise 1.0 cooldown hits, shield break timing, knockback management.",
        "tester_instructions": "Minimum 3 rounds. Focus on attack timing precision and shield mechanics.",
        "tier_thresholds": "HT1: Flawless axe timing and shield exploitation. LT5: Basic axe timing understanding.",
    },
    "SMP": {
        "title": "🌿 SMP Rubrics",
        "description": "SMP PvP scoring guidelines for testers.",
        "scoring": "Judged on: gear usage, strafing, totems, arrow management, and overall survival.",
        "requirements": "Must understand totem popping, elytra management, and gear optimization.",
        "combat_standards": "Expected: proper totem timing, crossbow/bow switching, strategic retreat.",
        "tester_instructions": "Evaluate in standard SMP loadout. Test decision-making with limited resources.",
        "tier_thresholds": "HT1: Mastery of all SMP mechanics. LT5: Basic understanding of SMP combat.",
    },
    "Vanilla": {
        "title": "🔮 Vanilla Rubrics",
        "description": "Vanilla PvP scoring guidelines for testers.",
        "scoring": "Judged on: 1.9+ mechanics, shield usage, axe/sword combination, positioning.",
        "requirements": "Must understand 1.9+ attack cooldown, shield timing, and sprinting mechanics.",
        "combat_standards": "Expected: proper 1.9 attack window, shield break timing, strategic positioning.",
        "tester_instructions": "Minimum 3 rounds vanilla settings. Evaluate cooldown management.",
        "tier_thresholds": "HT1: Perfect 1.9 mechanics mastery. LT5: Basic vanilla PvP understanding.",
    },
    "NethOP": {
        "title": "💀 NethOP Rubrics",
        "description": "NethOP scoring guidelines for testers.",
        "scoring": "Judged on: fire resistance management, overpowered kit usage, nether terrain navigation, and raw PvP.",
        "requirements": "Must handle OP gear fights, fire management, and the chaotic nether environment.",
        "combat_standards": "Expected: proper enchant leverage, fire resistance timing, aggressive playstyle.",
        "tester_instructions": "Test in standard NethOP settings. Focus on kit management and mechanics.",
        "tier_thresholds": "HT1: Dominates NethOP environment. LT5: Survives basic NethOP encounters.",
    },
    "Mace": {
        "title": "🔨 Mace Rubrics",
        "description": "Mace PvP scoring guidelines for testers.",
        "scoring": "Judged on: mace smash accuracy, fall distance exploitation, combo follow-ups, and positioning.",
        "requirements": "Must execute mace smash mechanics correctly and follow up effectively.",
        "combat_standards": "Expected: proper fall height calculation, smash accuracy, and post-smash combos.",
        "tester_instructions": "Minimum 3 encounters. Focus on smash accuracy and combo consistency.",
        "tier_thresholds": "HT1: Perfect mace smash execution. LT5: Basic mace usage understanding.",
    },
    "Cart": {
        "title": "🛒 Cart Rubrics",
        "description": "Cart PvP scoring guidelines for testers.",
        "scoring": "Judged on: cart mechanics, desyncs, positioning, and combat while in/around carts.",
        "requirements": "Must understand cart desync mechanics and how to exploit them in combat.",
        "combat_standards": "Expected: proper cart desync timing, hitbox exploitation, and cart combat awareness.",
        "tester_instructions": "Test in cart-enabled environment. Evaluate cart mechanic mastery.",
        "tier_thresholds": "HT1: Master cart desync user. LT5: Basic cart combat awareness.",
    },
    "DiaSMP": {
        "title": "💎 DiaSMP Rubrics",
        "description": "Diamond SMP scoring guidelines for testers.",
        "scoring": "Judged on: diamond armor PvP, totem usage, enchant management, and strategy.",
        "requirements": "Must handle diamond tier fights with proper enchant selection and survival instincts.",
        "combat_standards": "Expected: proper diamond armor mechanics, enchant exploitation, strategic combat.",
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

    @discord.ui.button(label="Vanilla", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="rubric_vanilla", row=0)
    async def vanilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Vanilla")

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="rubric_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "UHC")

    @discord.ui.button(label="Pot", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="rubric_pot", row=0)
    async def pot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Pot")

    @discord.ui.button(label="NethOP", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="rubric_nethop", row=1)
    async def nethop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "NethOP")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="rubric_smp", row=2)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "SMP")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="rubric_sword", row=2)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="rubric_axe", row=2)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Axe")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="rubric_mace", row=3)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Mace")

    @discord.ui.button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒", custom_id="rubric_cart", row=3)
    async def cart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "Cart")

    @discord.ui.button(label="DiaSMP", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="rubric_diasmp", row=3)
    async def diasmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rubric(interaction, "DiaSMP")


async def show_rubric(interaction: discord.Interaction, gamemode: str):
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

    @discord.ui.button(label="Vanilla", style=discord.ButtonStyle.secondary, emoji="🔮", custom_id="ruleset_vanilla", row=0)
    async def vanilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Vanilla")

    @discord.ui.button(label="UHC", style=discord.ButtonStyle.secondary, emoji="🌟", custom_id="ruleset_uhc", row=0)
    async def uhc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "UHC")

    @discord.ui.button(label="Pot", style=discord.ButtonStyle.secondary, emoji="🧪", custom_id="ruleset_pot", row=0)
    async def pot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Pot")

    @discord.ui.button(label="NethOP", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="ruleset_nethop", row=1)
    async def nethop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "NethOP")

    @discord.ui.button(label="SMP", style=discord.ButtonStyle.secondary, emoji="🌿", custom_id="ruleset_smp", row=2)
    async def smp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "SMP")

    @discord.ui.button(label="Sword", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="ruleset_sword", row=2)
    async def sword_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Sword")

    @discord.ui.button(label="Axe", style=discord.ButtonStyle.secondary, emoji="🪓", custom_id="ruleset_axe", row=2)
    async def axe_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Axe")

    @discord.ui.button(label="Mace", style=discord.ButtonStyle.secondary, emoji="🔨", custom_id="ruleset_mace", row=3)
    async def mace_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Mace")

    @discord.ui.button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒", custom_id="ruleset_cart", row=3)
    async def cart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "Cart")

    @discord.ui.button(label="DiaSMP", style=discord.ButtonStyle.secondary, emoji="💎", custom_id="ruleset_diasmp", row=3)
    async def diasmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ruleset(interaction, "DiaSMP")


async def show_ruleset(interaction: discord.Interaction, gamemode: str):
    d = RULESET_DATA
    embed = discord.Embed(
        title=f"📖 {gamemode} Ruleset",
        description=f"Official rules for **{gamemode}** tierlist fights.\nTierlists Rules are applied to every Tierlist fight ensuring proper and fair advantages over the players.",
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
# VIEWS – MIGRATIONS PANEL
# ─────────────────────────────────────────────
class MigrationsPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="How To Migrate", style=discord.ButtonStyle.primary, emoji="❓", custom_id="migration_howto")
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
            "Provide:\n"
            "• Screenshot or video proof from the source server\n"
            "• Clear display of your Minecraft username\n"
            "• Server name visible in the proof\n"
            "• Date of the tier result"
        ), inline=False)
        embed.add_field(name="⏳ Processing Time", value="Migration requests are reviewed within 48–72 hours by senior staff.", inline=False)
        embed.set_footer(text="TestYourTier | TYT")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Tier Transfer", style=discord.ButtonStyle.danger, emoji="⚔️", custom_id="migration_transfer")
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (interaction.user.id,)) as cur:
                user = await cur.fetchone()
        if not user:
            await interaction.response.send_message("❌ You must register your profile first!", ephemeral=True)
            return
        modal = MigrationModal()
        await interaction.response.send_modal(modal)


class MigrationModal(discord.ui.Modal, title="Tier Transfer Request"):
    gamemode = discord.ui.TextInput(
        label="Gamemode",
        placeholder="e.g. Pot, UHC, Sword",
        max_length=20,
        required=True
    )
    from_server = discord.ui.TextInput(
        label="Source Server",
        placeholder="e.g. MCTiers, EU Tiers, Indian Tiers",
        max_length=50,
        required=True
    )
    claimed_tier = discord.ui.TextInput(
        label="Your Tier on Source Server",
        placeholder="e.g. LT3, HT5",
        max_length=10,
        required=True
    )
    evidence = discord.ui.TextInput(
        label="Evidence Link or Description",
        placeholder="Paste screenshot link or describe your proof",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        gm = self.gamemode.value.strip()
        if gm not in GAMEMODES:
            await interaction.response.send_message(
                f"❌ Invalid gamemode. Valid: {', '.join(GAMEMODES)}", ephemeral=True
            )
            return

        tier = self.claimed_tier.value.strip().upper()
        if tier not in TIERS:
            await interaction.response.send_message(
                f"❌ Invalid tier. Valid tiers: {', '.join(TIERS)}", ephemeral=True
            )
            return

        tier_index = TIERS.index(tier)
        if tier_index > 7:
            await interaction.response.send_message(
                "❌ Migrations require LT3 or higher.", ephemeral=True
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO migration_requests (user_id, gamemode, from_server, claimed_tier, evidence, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.user.id, gm, self.from_server.value, tier, self.evidence.value, utcnow())
            )
            await db.commit()

        await log_event("MIGRATION_REQUEST", interaction.user.id, gm, details=f"From: {self.from_server.value}, Tier: {tier}")

        embed = discord.Embed(
            title="✅ Migration Request Submitted",
            description="Your tier transfer request has been submitted for staff review.",
            color=COLORS["teal"]
        )
        embed.add_field(name="Gamemode", value=gm, inline=True)
        embed.add_field(name="Source Server", value=self.from_server.value, inline=True)
        embed.add_field(name="Claimed Tier", value=tier, inline=True)
        embed.add_field(name="Status", value="🟡 Pending Review", inline=False)
        embed.set_footer(text="TestYourTier | TYT • Processing: 48–72 hours")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# SLASH COMMANDS – QUEUE
# ─────────────────────────────────────────────
@tree.command(name="queue", description="Queue management commands")
@app_commands.describe(
    action="open or close the queue",
    gamemode="The gamemode for this queue",
    region="The region for this queue session"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="open", value="open"),
        app_commands.Choice(name="close", value="close"),
    ],
    gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES],
    region=[app_commands.Choice(name=r, value=r) for r in REGIONS],
)
async def queue_cmd(interaction: discord.Interaction, action: str, gamemode: str, region: str = "NA"):
    cfg = await get_guild_config(interaction.guild.id)
    tester_role_id = cfg.get("tester_role")
    staff_role_id = cfg.get("staff_role")

    if not has_staff_role(interaction.user, staff_role_id) and not (tester_role_id and any(r.id == tester_role_id for r in interaction.user.roles)):
        await interaction.response.send_message("❌ You need the Tester or Staff role to manage queues.", ephemeral=True)
        return

    if action == "open":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id FROM queue_sessions WHERE gamemode = ? AND status = 'open'", (gamemode,)
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                await interaction.response.send_message(f"⚠️ A **{gamemode}** queue is already open!", ephemeral=True)
                return

        await interaction.response.defer()
        embed = await build_queue_embed(gamemode, region, interaction.user, 0)

        emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
        waitlist_chan_key = f"waitlist_chan_{gamemode.lower()}"
        chan_id = cfg.get(waitlist_chan_key)
        channel = interaction.channel

        if chan_id:
            wl_channel = interaction.guild.get_channel(chan_id)
            if wl_channel:
                channel = wl_channel

        msg = await channel.send(content="@here", embed=embed)

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO queue_sessions (gamemode, region, tester_id, opened_at, queue_message_id, queue_channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                (gamemode, region, interaction.user.id, utcnow(), msg.id, channel.id)
            )
            session_id = cur.lastrowid
            await db.commit()

        await msg.edit(embed=embed, view=QueueView(gamemode, session_id))
        await log_event("QUEUE_OPEN", interaction.user.id, gamemode, details=f"Region: {region}")

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

            await db.execute(
                "DELETE FROM queue_members WHERE gamemode = ?", (gamemode,)
            )
            await db.execute(
                "UPDATE queue_sessions SET status = 'closed', closed_at = ? WHERE id = ?",
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

        msg_id = session[8]
        chan_id = session[9]
        if msg_id and chan_id:
            channel = interaction.guild.get_channel(chan_id)
            if channel:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(content=None, embed=closed_embed, view=None)
                except Exception:
                    pass

        await log_event("QUEUE_CLOSE", interaction.user.id, gamemode)
        await interaction.response.send_message(f"✅ **{gamemode}** queue closed.", ephemeral=True)


@tree.command(name="nextplayer", description="Advance to the next player in the queue")
@app_commands.describe(gamemode="The gamemode queue to advance")
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def nextplayer_cmd(interaction: discord.Interaction, gamemode: str):
    cfg = await get_guild_config(interaction.guild.id)
    tester_role_id = cfg.get("tester_role")
    staff_role_id = cfg.get("staff_role")

    if not has_staff_role(interaction.user, staff_role_id) and not (tester_role_id and any(r.id == tester_role_id for r in interaction.user.roles)):
        await interaction.response.send_message("❌ You need the Tester or Staff role.", ephemeral=True)
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
            "DELETE FROM queue_members WHERE user_id = ? AND gamemode = ?",
            (next_player[0], gamemode)
        )
        await db.execute(
            "UPDATE queue_members SET position = position - 1 WHERE gamemode = ?", (gamemode,)
        )
        await db.execute(
            "UPDATE queue_sessions SET current_player_id = ? WHERE id = ?",
            (next_player[0], session[0])
        )
        await db.commit()

    member = interaction.guild.get_member(next_player[0])
    embed = discord.Embed(
        title="⚔️ Next Player Called",
        description=f"{member.mention if member else next_player[1]} you are up for your **{gamemode}** test!",
        color=COLORS["gold"]
    )
    embed.add_field(name="Player", value=next_player[1], inline=True)
    embed.add_field(name="Gamemode", value=gamemode, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)
    await log_event("NEXT_PLAYER", interaction.user.id, gamemode, details=f"Next: {next_player[1]}")
    await refresh_queue_embed(interaction, gamemode, session[0])


# ─────────────────────────────────────────────
# SLASH COMMANDS – RESULTS
# ─────────────────────────────────────────────
@tree.command(name="logtest", description="Log a completed test and assign a tier")
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
async def logtest_cmd(
    interaction: discord.Interaction,
    player: discord.Member,
    gamemode: str,
    rank_before: str,
    rank_after: str,
    notes: str = None
):
    cfg = await get_guild_config(interaction.guild.id)
    tester_role_id = cfg.get("tester_role")
    staff_role_id = cfg.get("staff_role")

    if not has_staff_role(interaction.user, staff_role_id) and not (tester_role_id and any(r.id == tester_role_id for r in interaction.user.roles)):
        await interaction.response.send_message("❌ You need the Tester or Staff role to log tests.", ephemeral=True)
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
                peak_tier = existing_rank[1]
                peak_idx = TIERS.index(peak_tier) if peak_tier in TIERS else len(TIERS)
                new_peak = peak_tier if peak_idx <= after_idx else rank_after
                await db.execute(
                    "UPDATE player_ranks SET current_tier = ?, peak_tier = ?, tests_taken = tests_taken + 1 WHERE user_id = ? AND gamemode = ?",
                    (rank_after, new_peak, player.id, gamemode)
                )
            else:
                await db.execute(
                    "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 1)",
                    (player.id, gamemode, rank_after, rank_after)
                )

        from datetime import timedelta
        cd_end = datetime.now(timezone.utc) + timedelta(days=COOLDOWN_DAYS)
        await db.execute(
            "INSERT INTO cooldowns (user_id, gamemode, cooldown_end) VALUES (?, ?, ?) ON CONFLICT(user_id, gamemode) DO UPDATE SET cooldown_end = excluded.cooldown_end",
            (player.id, gamemode, cd_end.strftime("%Y-%m-%d %H:%M:%S UTC"))
        )

        cur = await db.execute(
            "INSERT INTO test_logs (player_id, tester_id, gamemode, rank_before, rank_after, timestamp, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (player.id, interaction.user.id, gamemode, rank_before, rank_after, utcnow(), notes)
        )
        await db.commit()

    if before_idx == -1 or after_idx == -1:
        color = COLORS["blue"]
        result_type = "Placement"
    elif rank_before == "Unranked":
        color = COLORS["blue"]
        result_type = "Placement"
    elif after_idx < before_idx:
        color = COLORS["gold"]
        result_type = "Promotion"
    elif after_idx == before_idx:
        color = COLORS["orange"]
        result_type = "No Change"
    else:
        color = COLORS["red"]
        result_type = "Demotion"

    emoji = GAMEMODE_EMOJIS.get(gamemode, "⚔️")
    embed = discord.Embed(
        title=f"{mc_name}'s Test Results 🏆",
        color=color
    )
    embed.add_field(name="Player Name", value=mc_name, inline=False)
    embed.add_field(name="Tester Name", value=interaction.user.mention, inline=False)
    embed.add_field(name="Rank Before", value=rank_before, inline=False)
    embed.add_field(name="Rank Earned", value=rank_after, inline=False)
    embed.add_field(name="Game Mode", value=f"{emoji} {gamemode}", inline=False)
    embed.add_field(name="Result", value=result_type, inline=False)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • {utcnow()}")

    results_chan_id = cfg.get("results_channel")
    if results_chan_id:
        results_chan = interaction.guild.get_channel(results_chan_id)
        if results_chan:
            await results_chan.send(content=player.mention, embed=embed)
            await interaction.response.send_message(f"✅ Test logged and posted in {results_chan.mention}!", ephemeral=True)
            await log_event("TEST_LOGGED", player.id, gamemode, details=f"Before: {rank_before}, After: {rank_after}, Tester: {interaction.user.id}")
            return

    await interaction.response.send_message(embed=embed)
    await log_event("TEST_LOGGED", player.id, gamemode, details=f"Before: {rank_before}, After: {rank_after}, Tester: {interaction.user.id}")


# ─────────────────────────────────────────────
# SLASH COMMANDS – PLAYER PROFILE
# ─────────────────────────────────────────────
@tree.command(name="profile", description="View a player's TYT profile and rankings")
@app_commands.describe(member="The member to look up (leave blank for yourself)")
async def profile_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (target.id,)) as cur:
            user = await cur.fetchone()
        async with db.execute(
            "SELECT gamemode, current_tier, peak_tier, wins, losses, tests_taken FROM player_ranks WHERE user_id = ? ORDER BY gamemode",
            (target.id,)
        ) as cur:
            ranks = await cur.fetchall()

    if not user:
        await interaction.response.send_message(
            f"❌ {target.mention} has not registered a profile yet.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"👤 {user[1]}'s Profile",
        color=COLORS["blue"]
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🌐 Region", value=user[2], inline=True)
    embed.add_field(name="💎 Account Type", value=user[3], inline=True)
    embed.add_field(name="📅 Registered", value=user[4], inline=True)

    if ranks:
        ranks_text = ""
        for gm, cur_tier, peak_tier, wins, losses, tests in ranks:
            emoji = GAMEMODE_EMOJIS.get(gm, "⚔️")
            ranks_text += f"{emoji} **{gm}**: {cur_tier} *(Peak: {peak_tier})* — Tests: {tests}\n"
        embed.add_field(name="🏆 Rankings", value=ranks_text, inline=False)
    else:
        embed.add_field(name="🏆 Rankings", value="No ranks yet. Join a queue to get tested!", inline=False)

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
            """SELECT u.minecraft_username, r.current_tier, r.peak_tier, r.tests_taken
               FROM player_ranks r JOIN users u ON r.user_id = u.user_id
               WHERE r.gamemode = ? AND r.current_tier != 'Unranked'
               ORDER BY CASE r.current_tier
                   WHEN 'HT1' THEN 1 WHEN 'HT2' THEN 2 WHEN 'HT3' THEN 3
                   WHEN 'HT4' THEN 4 WHEN 'HT5' THEN 5 WHEN 'LT1' THEN 6
                   WHEN 'LT2' THEN 7 WHEN 'LT3' THEN 8 WHEN 'LT4' THEN 9
                   WHEN 'LT5' THEN 10 ELSE 11 END
               LIMIT 15""",
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
        lb_text = ""
        for i, (name, cur_tier, peak_tier, tests) in enumerate(players):
            lb_text += f"{medals[i]} `#{i+1}` **{name}** — {cur_tier} *(Peak: {peak_tier})* | Tests: {tests}\n"
        embed.add_field(name="Rankings", value=lb_text, inline=False)

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────
# SLASH COMMANDS – ADMIN / SETUP
# ─────────────────────────────────────────────
def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        raise app_commands.MissingPermissions(["administrator"])
    return app_commands.check(predicate)


setup_group = app_commands.Group(name="setup", description="Setup commands for TYT bot (Admin only)")


@setup_group.command(name="panels", description="Post all channel panels (request-test, rubrics, ruleset, migrations, tickets)")
@is_admin()
async def setup_panels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    cfg = await get_guild_config(interaction.guild.id)
    results = []

    request_test_chan_id = cfg.get("request_test_channel")
    if request_test_chan_id:
        chan = interaction.guild.get_channel(request_test_chan_id)
        if chan:
            embed = discord.Embed(
                title="📝 Evaluation Testing Waitlist",
                description=(
                    "Upon applying, you will be added to a waitlist channel. "
                    "Here you will be pinged when a tester of your region is available.\n"
                    "If you are HT3 or higher, create a high ticket\n\n"
                    "**① Register Your Profile 💚**\n"
                    "Click Register / Update Profile to set your in-game username, region, and account type before joining any queue.\n\n"
                    "**② Select a Gamemode 🦵**\n"
                    "Click any gamemode button below to receive the corresponding waitlist role. A tester will pick you up when they open a queue.\n\n"
                    "**③ Testing Cooldown ⏱️**\n"
                    "Each Gamemode has a 5-day cooldown after each tests\n\n"
                    "**④ Validity 👤**\n"
                    "Provide authentic information about your account and testing details"
                ),
                color=COLORS["dark"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=WaitlistPanel())
            results.append(f"✅ Waitlist panel posted in {chan.mention}")

    rubrics_chan_id = cfg.get("rubrics_channel")
    if rubrics_chan_id:
        chan = interaction.guild.get_channel(rubrics_chan_id)
        if chan:
            embed = discord.Embed(
                title="Ranked Rubrics 🏆",
                description=(
                    "These are the ranked rubrics for all game modes. Players and testers should follow the scores "
                    "in the game mode by following the Rubrics. Tests should be done according to the rubrics and "
                    "TierList Rules. Failure to follow this will result in your test being invalidated by higher staffs."
                ),
                color=COLORS["gold"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=RubricsPanel())
            results.append(f"✅ Rubrics panel posted in {chan.mention}")

    ruleset_chan_id = cfg.get("ruleset_channel")
    if ruleset_chan_id:
        chan = interaction.guild.get_channel(ruleset_chan_id)
        if chan:
            embed = discord.Embed(
                title="Tierlist Ruleset 🥇",
                description=(
                    "Tierlists Rules are applied to every Tierlist fights ensuring proper and fair advantages over the players. "
                    "Any advanced modifications or exploitation of the bugs that might get an unfair advantage over your opponents "
                    "is considered as cheating and if caught will be restricted from the tierlist fights."
                ),
                color=COLORS["teal"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=RulesetPanel())
            results.append(f"✅ Ruleset panel posted in {chan.mention}")

    migrations_chan_id = cfg.get("migrations_channel")
    if migrations_chan_id:
        chan = interaction.guild.get_channel(migrations_chan_id)
        if chan:
            embed = discord.Embed(
                title="🔄 Gamemode Migrations",
                description=(
                    "Migrate your ranks to TestYourTier - (LT3+)\n\n"
                    "**How To Migrate**\n"
                    "• Your migrating tier is LT3+\n"
                    "• You did not test the gamemode here before\n"
                    "• Your migrating Tier result was within 4 months\n"
                    "• You can comply to purge if needed\n"
                    "• You can share proper authentication of your account\n"
                    "• Your current tier meaning no migration for Peak Tiers"
                ),
                color=COLORS["teal"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=MigrationsPanel())
            results.append(f"✅ Migrations panel posted in {chan.mention}")

    support_chan_id = cfg.get("support_channel")
    if support_chan_id:
        chan = interaction.guild.get_channel(support_chan_id)
        if chan:
            embed = discord.Embed(
                title="🎫 Support Tickets",
                description=(
                    "If you **require support**, you may open a ticket\n\n"
                    "• Prior to doing this, and depending on your issue, it would be considerate to explore ways to resolve the issue yourself.\n"
                    "• Please have all necessary information ready before opening a ticket."
                ),
                color=COLORS["blue"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=SupportTicketPanel())
            results.append(f"✅ Support ticket panel posted in {chan.mention}")

    report_chan_id = cfg.get("report_channel")
    if report_chan_id:
        chan = interaction.guild.get_channel(report_chan_id)
        if chan:
            embed = discord.Embed(
                title="🚩 Report Tickets",
                description=(
                    "Open a ticket if you need to report a staff / tester member to server authorities.\n\n"
                    "• You need concrete evidence about the report.\n"
                    "• You can take the ticket in these category to report staffs under manager role."
                ),
                color=COLORS["red"]
            )
            embed.set_footer(text="TestYourTier | TYT")
            await chan.send(embed=embed, view=ReportTicketPanel())
            results.append(f"✅ Report ticket panel posted in {chan.mention}")

    if not results:
        await interaction.followup.send(
            "⚠️ No channels configured yet. Run `/setup channels` first to assign channels.",
            ephemeral=True
        )
        return

    await interaction.followup.send("\n".join(results), ephemeral=True)


@setup_group.command(name="channels", description="Configure all TYT channels")
@is_admin()
@app_commands.describe(
    request_test="The #request-test channel",
    results="The #results channel",
    rubrics="The #ranked-rubrics channel",
    ruleset="The #ranked-ruleset channel",
    migrations="The #migrations channel",
    support="The #request-support channel",
    report="The #report-tickets channel",
)
async def setup_channels(
    interaction: discord.Interaction,
    request_test: discord.TextChannel = None,
    results: discord.TextChannel = None,
    rubrics: discord.TextChannel = None,
    ruleset: discord.TextChannel = None,
    migrations: discord.TextChannel = None,
    support: discord.TextChannel = None,
    report: discord.TextChannel = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    if request_test:
        cfg["request_test_channel"] = request_test.id
    if results:
        cfg["results_channel"] = results.id
    if rubrics:
        cfg["rubrics_channel"] = rubrics.id
    if ruleset:
        cfg["ruleset_channel"] = ruleset.id
    if migrations:
        cfg["migrations_channel"] = migrations.id
    if support:
        cfg["support_channel"] = support.id
    if report:
        cfg["report_channel"] = report.id
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(title="✅ Channels Configured", color=COLORS["green"])
    if request_test:
        embed.add_field(name="Request Test", value=request_test.mention, inline=True)
    if results:
        embed.add_field(name="Results", value=results.mention, inline=True)
    if rubrics:
        embed.add_field(name="Rubrics", value=rubrics.mention, inline=True)
    if ruleset:
        embed.add_field(name="Ruleset", value=ruleset.mention, inline=True)
    if migrations:
        embed.add_field(name="Migrations", value=migrations.mention, inline=True)
    if support:
        embed.add_field(name="Support", value=support.mention, inline=True)
    if report:
        embed.add_field(name="Report", value=report.mention, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="roles", description="Configure TYT roles")
@is_admin()
@app_commands.describe(
    staff_role="The staff role",
    tester_role="The tester role",
    admin_role="The admin role",
)
async def setup_roles(
    interaction: discord.Interaction,
    staff_role: discord.Role = None,
    tester_role: discord.Role = None,
    admin_role: discord.Role = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    if staff_role:
        cfg["staff_role"] = staff_role.id
    if tester_role:
        cfg["tester_role"] = tester_role.id
    if admin_role:
        cfg["admin_role"] = admin_role.id
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(title="✅ Roles Configured", color=COLORS["green"])
    if staff_role:
        embed.add_field(name="Staff Role", value=staff_role.mention, inline=True)
    if tester_role:
        embed.add_field(name="Tester Role", value=tester_role.mention, inline=True)
    if admin_role:
        embed.add_field(name="Admin Role", value=admin_role.mention, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="waitlists", description="Configure waitlist channels and roles for each gamemode")
@is_admin()
@app_commands.describe(
    gamemode="The gamemode to configure",
    channel="The waitlist channel for this gamemode",
    role="The waitlist role for this gamemode",
)
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def setup_waitlists(
    interaction: discord.Interaction,
    gamemode: str,
    channel: discord.TextChannel = None,
    role: discord.Role = None,
):
    cfg = await get_guild_config(interaction.guild.id)
    gm_key = gamemode.lower()
    if channel:
        cfg[f"waitlist_chan_{gm_key}"] = channel.id
    if role:
        cfg[f"waitlist_role_{gm_key}"] = role.id
    await set_guild_config(interaction.guild.id, cfg)

    embed = discord.Embed(
        title=f"✅ {gamemode} Waitlist Configured",
        color=COLORS["green"]
    )
    if channel:
        embed.add_field(name="Channel", value=channel.mention, inline=True)
    if role:
        embed.add_field(name="Role", value=role.mention, inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="database", description="Check database status and stats")
@is_admin()
async def setup_database(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM player_ranks") as cur:
            ranks = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM test_logs") as cur:
            tests = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tickets") as cur:
            tickets = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM queue_sessions") as cur:
            sessions = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM queue_sessions WHERE status = 'open'") as cur:
            open_sessions = (await cur.fetchone())[0]

    embed = discord.Embed(title="🗄️ Database Status", color=COLORS["blue"])
    embed.add_field(name="📋 Registered Users", value=str(users), inline=True)
    embed.add_field(name="🏆 Rank Records", value=str(ranks), inline=True)
    embed.add_field(name="⚔️ Tests Logged", value=str(tests), inline=True)
    embed.add_field(name="🎫 Total Tickets", value=str(tickets), inline=True)
    embed.add_field(name="🔄 Queue Sessions", value=str(sessions), inline=True)
    embed.add_field(name="🟢 Open Queues", value=str(open_sessions), inline=True)
    embed.add_field(name="💾 Database File", value=DB_PATH, inline=False)
    embed.add_field(name="Status", value="✅ Online and operational", inline=False)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="queues", description="Configure queue channels for each gamemode")
@is_admin()
@app_commands.describe(
    gamemode="The gamemode to configure",
    channel="The queue/waitlist channel for this gamemode",
)
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def setup_queues(
    interaction: discord.Interaction,
    gamemode: str,
    channel: discord.TextChannel,
):
    cfg = await get_guild_config(interaction.guild.id)
    cfg[f"queue_chan_{gamemode.lower()}"] = channel.id
    await set_guild_config(interaction.guild.id, cfg)
    await interaction.response.send_message(
        f"✅ **{gamemode}** queue channel set to {channel.mention}",
        ephemeral=True
    )


@setup_group.command(name="everything", description="Interactive guide to configure everything at once")
@is_admin()
async def setup_everything(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚙️ TYT Complete Setup Guide",
        description="Follow these steps to fully configure TestYourTier:",
        color=COLORS["blue"]
    )
    embed.add_field(name="Step 1 — Channels", value="`/setup channels` — Assign all primary channels (request-test, results, rubrics, ruleset, migrations, support, report)", inline=False)
    embed.add_field(name="Step 2 — Roles", value="`/setup roles` — Assign staff, tester, and admin roles", inline=False)
    embed.add_field(name="Step 3 — Waitlists", value="`/setup waitlists` — For each gamemode, set the waitlist channel and role (run 10 times, once per gamemode)", inline=False)
    embed.add_field(name="Step 4 — Panels", value="`/setup panels` — Posts all embeds with buttons in the configured channels", inline=False)
    embed.add_field(name="Step 5 — Verify", value="`/setup database` — Check that the database is running correctly", inline=False)
    embed.add_field(name="Available Gamemodes", value=" • ".join(GAMEMODES), inline=False)
    embed.add_field(name="Available Tiers", value=" • ".join(TIERS), inline=False)
    embed.set_footer(text="TestYourTier | TYT — Once configured, panels persist through restarts.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@setup_group.command(name="tickets_category", description="Set the category for ticket channels")
@is_admin()
@app_commands.describe(category="The category where ticket channels will be created")
async def setup_tickets_cat(interaction: discord.Interaction, category: discord.CategoryChannel):
    cfg = await get_guild_config(interaction.guild.id)
    cfg["tickets_category"] = category.id
    await set_guild_config(interaction.guild.id, cfg)
    await interaction.response.send_message(f"✅ Tickets category set to **{category.name}**", ephemeral=True)


tree.add_command(setup_group)


# ─────────────────────────────────────────────
# SLASH COMMANDS – MIGRATION REVIEW (STAFF)
# ─────────────────────────────────────────────
@tree.command(name="migration_review", description="Review a migration request (Staff only)")
@app_commands.describe(
    request_id="The migration request ID",
    action="approve or deny",
    reason="Reason for decision (optional)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="approve", value="approve"),
    app_commands.Choice(name="deny", value="deny"),
])
async def migration_review_cmd(interaction: discord.Interaction, request_id: int, action: str, reason: str = None):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only command.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM migration_requests WHERE id = ?", (request_id,)) as cur:
            req = await cur.fetchone()
        if not req:
            await interaction.response.send_message("❌ Migration request not found.", ephemeral=True)
            return

        new_status = "approved" if action == "approve" else "denied"
        await db.execute(
            "UPDATE migration_requests SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
            (new_status, interaction.user.id, utcnow(), request_id)
        )

        if action == "approve":
            await db.execute(
                "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 0) "
                "ON CONFLICT(user_id, gamemode) DO UPDATE SET current_tier = excluded.current_tier",
                (req[1], req[2], req[4], req[4])
            )
        await db.commit()

    user = interaction.guild.get_member(req[1])
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
    if user:
        try:
            dm_embed = discord.Embed(
                title=f"{'✅' if action == 'approve' else '❌'} Your Migration Request has been {action.capitalize()}d",
                color=color
            )
            dm_embed.add_field(name="Gamemode", value=req[2], inline=True)
            dm_embed.add_field(name="Claimed Tier", value=req[4], inline=True)
            if reason:
                dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.set_footer(text="TestYourTier | TYT")
            await user.send(embed=dm_embed)
        except Exception:
            pass

    await log_event(f"MIGRATION_{action.upper()}", req[1], req[2], details=f"By: {interaction.user.id}")


# ─────────────────────────────────────────────
# SLASH COMMANDS – TIMEOUT PLAYER (TESTER)
# ─────────────────────────────────────────────
@tree.command(name="timeout_player", description="Timeout a player from the queue (Tester only)")
@app_commands.describe(
    player="The player to timeout from queue",
    gamemode="The gamemode queue",
    reason="Reason for timeout"
)
@app_commands.choices(gamemode=[app_commands.Choice(name=gm, value=gm) for gm in GAMEMODES])
async def timeout_player_cmd(interaction: discord.Interaction, player: discord.Member, gamemode: str, reason: str = "No reason provided"):
    cfg = await get_guild_config(interaction.guild.id)
    tester_role_id = cfg.get("tester_role")
    if not has_staff_role(interaction.user, cfg.get("staff_role")) and not (tester_role_id and any(r.id == tester_role_id for r in interaction.user.roles)):
        await interaction.response.send_message("❌ Tester/Staff only.", ephemeral=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM queue_members WHERE user_id = ? AND gamemode = ?",
            (player.id, gamemode)
        )
        from datetime import timedelta
        cd_end = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.execute(
            "INSERT INTO cooldowns (user_id, gamemode, cooldown_end) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, gamemode) DO UPDATE SET cooldown_end = excluded.cooldown_end",
            (player.id, gamemode, cd_end.strftime("%Y-%m-%d %H:%M:%S UTC"))
        )
        await db.commit()

    await log_event("PLAYER_TIMEOUT", player.id, gamemode, details=f"By: {interaction.user.id}, Reason: {reason}")
    embed = discord.Embed(
        title="⏰ Player Removed from Queue",
        description=f"{player.mention} has been removed from the **{gamemode}** queue and placed on a 24-hour cooldown.",
        color=COLORS["orange"]
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"TestYourTier | TYT • Action by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────
# SLASH COMMANDS – COOLDOWN CHECK
# ─────────────────────────────────────────────
@tree.command(name="cooldown", description="Check your testing cooldown status")
@app_commands.describe(
    gamemode="Check cooldown for a specific gamemode (leave blank for all)",
    member="Check another player's cooldown"
)
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

    embed = discord.Embed(
        title=f"⏳ Cooldowns for {target.display_name}",
        color=COLORS["blue"]
    )

    if not cds:
        embed.description = "✅ No active cooldowns!"
    else:
        now = datetime.now(timezone.utc)
        for gm, cd_end_str in cds:
            try:
                cd_end = datetime.strptime(cd_end_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                if cd_end > now:
                    remaining = cd_end - now
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    embed.add_field(name=f"{GAMEMODE_EMOJIS.get(gm, '⚔️')} {gm}", value=f"⏳ {hours}h {minutes}m remaining\nEnds: {cd_end_str}", inline=True)
                else:
                    embed.add_field(name=f"{GAMEMODE_EMOJIS.get(gm, '⚔️')} {gm}", value="✅ Ready to test!", inline=True)
            except Exception:
                embed.add_field(name=gm, value=cd_end_str, inline=True)

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# SLASH COMMANDS – STAFF ACTIVITY
# ─────────────────────────────────────────────
@tree.command(name="staff_stats", description="View staff member activity stats (Staff only)")
@app_commands.describe(member="The staff member to check")
async def staff_stats_cmd(interaction: discord.Interaction, member: discord.Member = None):
    cfg = await get_guild_config(interaction.guild.id)
    if not has_staff_role(interaction.user, cfg.get("staff_role")):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    target = member or interaction.user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM test_logs WHERE tester_id = ?", (target.id,)
        ) as cur:
            tests = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM queue_sessions WHERE tester_id = ?", (target.id,)
        ) as cur:
            sessions = (await cur.fetchone())[0]

    embed = discord.Embed(
        title=f"📊 Staff Stats — {target.display_name}",
        color=COLORS["purple"]
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="⚔️ Tests Completed", value=str(tests), inline=True)
    embed.add_field(name="🔄 Queue Sessions", value=str(sessions), inline=True)
    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# SLASH COMMANDS – ADMIN RANK OVERRIDE
# ─────────────────────────────────────────────
@tree.command(name="setrank", description="Manually set a player's rank (Staff only)")
@app_commands.describe(
    player="The player to rank",
    gamemode="The gamemode",
    tier="The tier to assign"
)
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
            "SELECT peak_tier FROM player_ranks WHERE user_id = ? AND gamemode = ?",
            (player.id, gamemode)
        ) as cur:
            existing = await cur.fetchone()

        peak = existing[0] if existing else tier
        if existing:
            peak_idx = TIERS.index(peak) if peak in TIERS else len(TIERS)
            tier_idx = TIERS.index(tier) if tier in TIERS else len(TIERS)
            if tier_idx < peak_idx:
                peak = tier

        await db.execute(
            "INSERT INTO player_ranks (user_id, gamemode, current_tier, peak_tier, tests_taken) VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(user_id, gamemode) DO UPDATE SET current_tier = excluded.current_tier, peak_tier = excluded.peak_tier",
            (player.id, gamemode, tier, peak)
        )
        await db.commit()

    await log_event("RANK_SET", player.id, gamemode, details=f"Tier: {tier}, By: {interaction.user.id}")
    embed = discord.Embed(
        title="✅ Rank Updated",
        color=COLORS["green"]
    )
    embed.add_field(name="Player", value=player.mention, inline=True)
    embed.add_field(name="Gamemode", value=gamemode, inline=True)
    embed.add_field(name="New Tier", value=tier, inline=True)
    embed.set_footer(text=f"Set by {interaction.user.display_name} • TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)


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

    embed = discord.Embed(
        title="📋 Queue Status",
        color=COLORS["blue"]
    )

    if not open_queues:
        embed.description = "❌ No queues are currently open."
    else:
        for gm, region, tester_id, opened_at in open_queues:
            emoji = GAMEMODE_EMOJIS.get(gm, "⚔️")
            tester = interaction.guild.get_member(tester_id)
            tester_name = tester.display_name if tester else f"<@{tester_id}>"
            embed.add_field(
                name=f"{emoji} {gm}",
                value=f"🌐 {region} | 🎯 {tester_name} | 🕐 {opened_at}",
                inline=False
            )

    closed_gms = [gm for gm in GAMEMODES if gm not in [q[0] for q in open_queues]]
    if closed_gms:
        embed.add_field(
            name="❌ Closed Queues",
            value=" • ".join(closed_gms),
            inline=False
        )

    embed.set_footer(text="TestYourTier | TYT")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()
    bot.add_view(WaitlistPanel())
    bot.add_view(RubricsPanel())
    bot.add_view(RulesetPanel())
    bot.add_view(MigrationsPanel())
    bot.add_view(SupportTicketPanel())
    bot.add_view(ReportTicketPanel())

    try:
        synced = await tree.sync()
        logger.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    logger.info(f"TYT Bot Online — Logged in as {bot.user} ({bot.user.id})")
    logger.info(f"Serving {len(bot.guilds)} guild(s)")


@bot.event
async def on_guild_join(guild: discord.Guild):
    await log_event("GUILD_JOIN", details=f"Guild: {guild.name} ({guild.id})")
    logger.info(f"Joined guild: {guild.name} ({guild.id})")


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
    else:
        logger.error(f"Command error: {error}")
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

    bot.run(token, log_handler=None)
