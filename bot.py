# ============================================================
# TRADEVAULT MM TICKET BOT
# ============================================================

import os
import re
import asyncio
import discord

from discord.ext import commands
from discord.ui import Modal, TextInput, View, button
from discord import ButtonStyle


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

MIDDLEMAN_ROLE_ID = int(
    os.getenv("MIDDLEMAN_ROLE_ID", "1548878658637144114")
)

OWNER_ROLE_ID = int(
    os.getenv("OWNER_ROLE_ID", "1549812220664221877")
)

TICKET_CATEGORY_ID = int(
    os.getenv("TICKET_CATEGORY_ID", "1548605071703547904")
)

# ============================================================
# BANNERS
# ============================================================

# Put your image/GIF URL inside the quotes.
#
# Example:
# PANEL_BANNER_URL = "https://i.imgur.com/example.png"
#
# Leave "" if you don't want a banner.

PANEL_BANNER_URL = "https://cdn.discordapp.com/attachments/1547444944606593066/1547850627466665995/30D405DD-E3B4-49D5-AAB0-85A3BA6E0106.png?ex=6aa4ebbb&is=6aa39a3b&hm=3a995cad9d28dbb8288423b76e90b8201eeb3ab5116c4bafecd6c166ea336f4d&"

TICKET_BANNER_URL = "https://cdn.discordapp.com/attachments/1547444944606593066/1547850627466665995/30D405DD-E3B4-49D5-AAB0-85A3BA6E0106.png?ex=6aa4ebbb&is=6aa39a3b&hm=3a995cad9d28dbb8288423b76e90b8201eeb3ab5116c4bafecd6c166ea336f4d&"


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set"
    )


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)


# ============================================================
# STORAGE
# ============================================================

# ticket_channel_id:
#
# {
#     "owner": user_id,
#     "trader": user_id,
#     "game": "...",
#     "giving": "...",
#     "trader_giving": "...",
#     "private_links": "...",
#     "claimed_by": None
# }

tickets = {}


# ============================================================
# HELPERS
# ============================================================

def get_middleman_role(
    guild: discord.Guild
):

    if not MIDDLEMAN_ROLE_ID:
        return None

    return guild.get_role(
        MIDDLEMAN_ROLE_ID
    )


def get_owner_role(
    guild: discord.Guild
):

    if not OWNER_ROLE_ID:
        return None

    return guild.get_role(
        OWNER_ROLE_ID
    )


def is_middleman(
    member: discord.Member
):

    role = get_middleman_role(
        member.guild
    )

    if not role:
        return False

    return role in member.roles


def is_owner(
    member: discord.Member
):

    role = get_owner_role(
        member.guild
    )

    if not role:
        return False

    return role in member.roles


def clean_channel_name(
    name: str
):

    name = name.lower()

    name = re.sub(
        r"[^a-z0-9-]",
        "-",
        name
    )

    name = re.sub(
        r"-+",
        "-",
        name
    )

    return name[:90]


async def find_user(
    guild: discord.Guild,
    value: str
):

    value = value.strip()

    # ========================================================
    # MENTION
    # ========================================================

    match = re.fullmatch(
        r"<@!?(\d+)>",
        value
    )

    if match:

        user_id = int(
            match.group(1)
        )

    elif value.isdigit():

        user_id = int(value)

    else:

        member = discord.utils.find(
            lambda m:
            m.name.lower() == value.lower()
            or m.display_name.lower() == value.lower(),
            guild.members
        )

        if member:
            return member

        return None

    try:

        return (
            guild.get_member(user_id)
            or await guild.fetch_member(user_id)
        )

    except discord.NotFound:

        return None

    except discord.HTTPException:

        return None


# ============================================================
# MIDDLEMAN REQUEST MODAL
# ============================================================

class MiddlemanRequestModal(Modal):

    def __init__(
        self,
        selected_game: str
    ):

        super().__init__(
            title=f"{selected_game} Middleman Request"
        )

        self.selected_game = selected_game

        # ====================================================
        # TRADER USERNAME / ID
        # ====================================================

        self.trader_input = TextInput(
            label="Trader Username / User ID",
            placeholder="Enter trader username or ID",
            required=True,
            max_length=100
        )

        # ====================================================
        # WHAT YOU ARE GIVING
        # ====================================================

        self.giving_input = TextInput(
            label="What Are You Giving?",
            placeholder="Enter what you are giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        # ====================================================
        # WHAT TRADER IS GIVING
        # ====================================================

        self.trader_giving_input = TextInput(
            label="What Is Your Trader Giving?",
            placeholder="Enter what your trader is giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        # ====================================================
        # PRIVATE SERVER LINKS
        # ====================================================

        self.private_input = TextInput(
            label="Can You Join Private Server Links?",
            placeholder="Yes or No",
            required=True,
            max_length=20
        )

        self.add_item(
            self.trader_input
        )

        self.add_item(
            self.giving_input
        )

        self.add_item(
            self.trader_giving_input
        )

        self.add_item(
            self.private_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        if guild is None:
            return

        # ====================================================
        # FIND TRADER
        # ====================================================

        trader = await find_user(
            guild,
            self.trader_input.value
        )

        if not trader:

            await interaction.response.send_message(
                "❌ I couldn't find that user. Please use their Discord ID or mention.",
                ephemeral=True
            )

            return

        # ====================================================
        # PREVENT SELF TRADE
        # ====================================================

        if trader.id == interaction.user.id:

            await interaction.response.send_message(
                "❌ You can't use yourself as the other trader.",
                ephemeral=True
            )

            return

        # ====================================================
        # CATEGORY
        # ====================================================

        category = None

        if TICKET_CATEGORY_ID:

            category = guild.get_channel(
                TICKET_CATEGORY_ID
            )

            if category and not isinstance(
                category,
                discord.CategoryChannel
            ):

                category = None

        # ====================================================
        # BASE PERMISSIONS
        # ====================================================

        overwrites = {

            # Everyone
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            # Ticket creator
            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            # Other trader
            trader:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )
        }

        # ====================================================
        # MIDDLEMAN ROLE
        # ====================================================

        mm_role = get_middleman_role(
            guild
        )

        if mm_role:

            overwrites[mm_role] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            )

        # ====================================================
        # OWNER ROLE
        # ====================================================

        owner_role = get_owner_role(
            guild
        )

        if owner_role:

            overwrites[owner_role] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            )

        # ====================================================
        # CHANNEL NAME
        # ====================================================

        channel_name = clean_channel_name(
            f"{self.selected_game}-{interaction.user.name}"
        )

        # ====================================================
        # CREATE CHANNEL
        # ====================================================

        try:

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="Middleman ticket created"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ Discord failed to create the ticket. Try again.",
                ephemeral=True
            )

            return

        # ====================================================
        # SAVE TICKET
        # ====================================================

        tickets[channel.id] = {

            "owner": interaction.user.id,

            "trader": trader.id,

            "game": self.selected_game,

            "giving": self.giving_input.value,

            "trader_giving":
                self.trader_giving_input.value,

            "private_links":
                self.private_input.value,

            "claimed_by": None
        }

        # ====================================================
        # CREATION RESPONSE
        # ====================================================

        await interaction.response.send_message(
            f"✅ Your **{self.selected_game}** middleman ticket has been created: {channel.mention}",
            ephemeral=True
        )

        # ====================================================
        # WELCOME EMBED
        # ====================================================

        welcome = discord.Embed(

            title="👑 Welcome to your Ticket!",

            description=(
                f"Hello {interaction.user.mention}, "
                "thanks for opening a "
                "**Middleman Service Ticket!**\n\n"

                f"🎮 **Game:** {self.selected_game}\n\n"

                "A middleman will assist you shortly.\n"
                "Provide all trade details clearly.\n"
                "Fake/troll tickets will result in consequences."
            ),

            color=discord.Color.from_rgb(
                217,
                232,
                74
            )
        )

        # ====================================================
        # TICKET BANNER
        # ====================================================

        if TICKET_BANNER_URL:

            welcome.set_image(
                url=TICKET_BANNER_URL
            )

        welcome.set_footer(
            text=(
                "LUCK's MM • "
                "Please wait for a middleman"
            )
        )

        # ====================================================
        # TRADE DETAILS EMBED
        # ====================================================

        details = discord.Embed(

            title="📋 Trade Details",

            color=discord.Color.from_rgb(217, 232, 74)
        )

        details.add_field(
            name="🎮 Game",
            value=self.selected_game,
            inline=False
        )

        details.add_field(
            name="What Are You Giving?",
            value=self.giving_input.value,
            inline=False
        )

        details.add_field(
            name="What Is Your Trader Giving?",
            value=self.trader_giving_input.value,
            inline=False
        )

        details.add_field(
            name="Trader",
            value=(
                f"{trader.mention}\n"
                f"`{trader.id}`"
            ),
            inline=False
        )

        details.add_field(
            name="Can Join Private Server Links?",
            value=self.private_input.value,
            inline=False
        )

        details.set_footer(
            text="LUCK's MM Service"
        )

        # ====================================================
        # TOP PING
        # ====================================================

        ping_message = (
            f"{interaction.user.mention} "
            f"{trader.mention}"
        )

        if mm_role:

            ping_message += (
                f" {mm_role.mention}"
            )

        # ====================================================
        # SEND TICKET
        # ====================================================

        await channel.send(

            content=ping_message,

            embeds=[
                welcome,
                details
            ],

            view=TicketView()
        )


# ============================================================
# GAME SELECT
# ============================================================

class GameSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Steal a Brainrot",
                emoji="🧠",
                value="Steal a Brainrot"
            ),

            discord.SelectOption(
                label="Adopt Me",
                emoji="🐶",
                value="Adopt Me"
            ),

            discord.SelectOption(
                label="Murder Mystery 2",
                emoji="🔪",
                value="Murder Mystery 2"
            ),

            discord.SelectOption(
                label="Grow A Garden",
                emoji="🌱",
                value="Grow A Garden"
            ),

            discord.SelectOption(
                label="Blade Ball",
                emoji="⚔️",
                value="Blade Ball"
            ),

            discord.SelectOption(
                label="Others",
                emoji="📝",
                value="Others"
            )
        ]

        super().__init__(

            placeholder="Select a game...",

            min_values=1,

            max_values=1,

            options=options,

            custom_id="game_selection"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected_game = self.values[0]

        await interaction.response.send_modal(
            MiddlemanRequestModal(
                selected_game
            )
        )


# ============================================================
# REQUEST PANEL VIEW
# ============================================================

class TicketPanelView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            GameSelect()
        )


# ============================================================
# ADD USER MODAL
# ============================================================

class AddUserModal(Modal):

    def __init__(
        self,
        channel: discord.TextChannel
    ):

        super().__init__(
            title="Add User"
        )

        self.channel = channel

        self.user_input = TextInput(
            label="User ID / Username",
            placeholder="eg: 1234567890",
            required=True,
            max_length=100
        )

        self.add_item(
            self.user_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # ====================================================
        # ONLY MIDDLEMAN
        # ====================================================

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ Only a middleman can add users to this ticket.",
                ephemeral=True
            )

            return

        # ====================================================
        # CHECK CLAIM
        # ====================================================

        ticket = tickets.get(
            self.channel.id
        )

        if ticket:

            claimed_by = ticket[
                "claimed_by"
            ]

            if claimed_by:

                if claimed_by != interaction.user.id:

                    await interaction.response.send_message(
                        "❌ Only the middleman who claimed this ticket can add users.",
                        ephemeral=True
                    )

                    return

        # ====================================================
        # FIND USER
        # ====================================================

        user = await find_user(
            interaction.guild,
            self.user_input.value
        )

        if not user:

            await interaction.response.send_message(
                "❌ User not found.",
                ephemeral=True
            )

            return

        # ====================================================
        # ADD USER
        # ====================================================

        try:

            await self.channel.set_permissions(

                user,

                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            await interaction.response.send_message(
                f"✅ Added {user.mention} to the ticket.",
                ephemeral=True
            )

            await self.channel.send(
                f"➕ {user.mention} was added by "
                f"{interaction.user.mention}."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to add that user.",
                ephemeral=True
            )


# ============================================================
# TICKET VIEW
# ============================================================

class TicketView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # ========================================================
    # CLAIM
    # ========================================================

    @button(
        label="Claim Ticket",
        emoji="✅",
        style=ButtonStyle.success,
        custom_id="claim_ticket"
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # ====================================================
        # ONLY MIDDLEMAN
        # ====================================================

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ Only a middleman can claim this ticket.",
                ephemeral=True
            )

            return

        # ====================================================
        # GET TICKET
        # ====================================================

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Ticket data was not found.",
                ephemeral=True
            )

            return

        # ====================================================
        # ALREADY CLAIMED
        # ====================================================

        if ticket["claimed_by"]:

            claimed_user = (
                interaction.guild.get_member(
                    ticket["claimed_by"]
                )
            )

            name = (
                claimed_user.mention
                if claimed_user
                else "another middleman"
            )

            await interaction.response.send_message(
                f"❌ This ticket is already claimed by {name}.",
                ephemeral=True
            )

            return

        # ====================================================
        # SAVE CLAIM
        # ====================================================

        ticket["claimed_by"] = (
            interaction.user.id
        )

        # ====================================================
        # REMOVE MM ROLE ACCESS
        # ====================================================

        mm_role = get_middleman_role(
            interaction.guild
        )

        if mm_role:

            await interaction.channel.set_permissions(

                mm_role,

                view_channel=False,
                send_messages=False,
                read_message_history=False
            )

        # ====================================================
        # GIVE CLAIMING MM ACCESS
        # ====================================================

        await interaction.channel.set_permissions(

            interaction.user,

            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        await interaction.response.send_message(
            f"✅ {interaction.user.mention} has claimed this ticket!"
        )


    # ========================================================
    # UNCLAIM
    # ========================================================

    @button(
        label="Unclaim Ticket",
        emoji="🔓",
        style=ButtonStyle.secondary,
        custom_id="unclaim_ticket"
    )
    async def unclaim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # ====================================================
        # GET TICKET
        # ====================================================

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Ticket data was not found.",
                ephemeral=True
            )

            return

        # ====================================================
        # ONLY CLAIMING MM
        # ====================================================

        if ticket["claimed_by"] != interaction.user.id:

            await interaction.response.send_message(
                "❌ Only the middleman who claimed this ticket can unclaim it.",
                ephemeral=True
            )

            return

        # ====================================================
        # REMOVE CLAIMED MM OVERRIDE
        # ====================================================

        await interaction.channel.set_permissions(
            interaction.user,
            overwrite=None
        )

        # ====================================================
        # RESTORE MM ROLE
        # ====================================================

        mm_role = get_middleman_role(
            interaction.guild
        )

        if mm_role:

            await interaction.channel.set_permissions(

                mm_role,

                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        # ====================================================
        # CLEAR CLAIM
        # ====================================================

        ticket["claimed_by"] = None

        await interaction.response.send_message(
            f"🔓 {interaction.user.mention} has unclaimed the ticket."
        )


    # ========================================================
    # CLOSE
    # ========================================================

    @button(
        label="Close Ticket",
        emoji="🔒",
        style=ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Ticket data was not found.",
                ephemeral=True
            )

            return

        # ====================================================
        # CLAIMED MM OR OWNER ROLE
        # ====================================================

        allowed = False

        if (
            ticket["claimed_by"]
            == interaction.user.id
        ):

            allowed = True

        if is_owner(
            interaction.user
        ):

            allowed = True

        if not allowed:

            await interaction.response.send_message(
                "❌ Only the claimed middleman or Owner can close this ticket.",
                ephemeral=True
            )

            return

        # ====================================================
        # CLOSE MESSAGE
        # ====================================================

        await interaction.response.send_message(
            "🔒 Closing this ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        # ====================================================
        # REMOVE STORAGE
        # ====================================================

        tickets.pop(
            interaction.channel.id,
            None
        )

        # ====================================================
        # DELETE CHANNEL
        # ====================================================

        try:

            await interaction.channel.delete(
                reason=(
                    f"Ticket closed by "
                    f"{interaction.user}"
                )
            )

        except discord.NotFound:

            pass

        except discord.Forbidden:

            pass


    # ========================================================
    # ADD USER
    # ========================================================

    @button(
        label="Add User",
        emoji="➕",
        style=ButtonStyle.primary,
        custom_id="add_user"
    )
    async def add_user(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # ====================================================
        # ONLY MIDDLEMAN
        # ====================================================

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ Only a middleman can use **Add User**.",
                ephemeral=True
            )

            return

        # ====================================================
        # CHECK CLAIM
        # ====================================================

        ticket = tickets.get(
            interaction.channel.id
        )

        if ticket:

            if ticket["claimed_by"]:

                if ticket["claimed_by"] != interaction.user.id:

                    await interaction.response.send_message(
                        "❌ Only the middleman who claimed this ticket can use Add User.",
                        ephemeral=True
                    )

                    return

        # ====================================================
        # OPEN MODAL
        # ====================================================

        await interaction.response.send_modal(
            AddUserModal(
                interaction.channel
            )
        )


# ============================================================
# TICKET PANEL COMMAND
# ============================================================

@bot.command(
    name="panel"
)
@commands.has_permissions(
    administrator=True
)
async def ticketpanel(
    ctx: commands.Context
):

    embed = discord.Embed(

        title="LUCK's MM | MM Service",

        description=(

            "Welcome to our middleman Service centre.\n\n"

            "At LUCK's MM, we value and provide a safe "
            "and secure way to exchange your goods.\n\n"

            "**If you've found a trade and want to ensure "
            "your safety, you can use our middleman service.**\n\n"

            "Our secure middleman service will ensure the "
            "trade goes smoothly and both users receive "
            "their sides.\n\n"

            "---\n"

            "**Usage Conditions:**\n"

            "• Select the correct game before requesting a middleman.\n"

            "• Both parties agree to trade before requesting "
            "a middleman.\n"

            "• State the trade details clearly.\n"

            "• Fake or troll tickets will result in punishments."
        ),

        color=discord.Color.from_rgb(
            217,
            232,
            74
        )
    )

    # ========================================================
    # PANEL BANNER
    # ========================================================

    if PANEL_BANNER_URL:

        embed.set_image(
            url=PANEL_BANNER_URL
        )

    embed.set_footer(
        text="LUCK's MM • Trusted & Secure"
    )

    await ctx.send(

        embed=embed,

        view=TicketPanelView()
    )


# ============================================================
# COMMAND ERROR
# ============================================================

@ticketpanel.error
async def ticketpanel_error(
    ctx: commands.Context,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ You need Administrator permission to use `$panel`.",
            delete_after=5
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    bot.add_view(
        TicketPanelView()
    )

    bot.add_view(
        TicketView()
    )

    print(
        "========================================"
    )

    print(
        f"Logged in as {bot.user}"
    )

    print(
        f"Bot ID: {bot.user.id}"
    )

    print(
        "TradeVault MM Ticket System Online"
    )

    print(
        "========================================"
    )


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)
