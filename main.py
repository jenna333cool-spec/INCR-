import discord
from discord.ext import commands
import asyncio
from groq import Groq
import io
import os

# --- Configuration ---
# REPLACE THESE WITH YOUR NEW KEYS AFTER RESETTING THEM
TOKEN = 'MTQ5MzM3MjEwMzYwMzUxOTU5OQ.GUBzzq.DC5uOGF6wdQ1UcYJzeQ-5gTBh63Hi2lx4I0fnU'
GROQ_API_KEY = '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'

# Channel IDs
PENDING_LOG_ID = 1503031852477452288  # Where new apps arrive
ACCEPTED_LOG_ID = 1503064925356953720  # Channel for approved apps
DENIED_LOG_ID = 1503064008998256700    # Channel for rejected apps

# Role IDs
STAFF_ROLE_ID = 1502241071403368498 
PM_ROLE_ID = 1502328183096082552      # <--- REPLACE WITH ACTUAL PM ROLE ID
DROPPER_ROLE_ID = 1502241909580632144  # <--- REPLACE WITH ACTUAL DROPPER ROLE ID
ADMIN_PING = "<@&1502985205059813396> <@1114806107760758824>" 
GOLD_COLOR = 0xFFD700 

client_groq = Groq(api_key=GROQ_API_KEY)

# --- Best-in-Class Questions ---
QUESTIONS = {
    "staff application": [
        "What motivated you to specifically choose incredible DROPS over other communities?",
        "Describe your daily routine and how many hours you can realistically commit to monitoring chat.",
        "Provide a detailed history of your moderation experience (Server names, roles, and reasons for leaving).",
        "A long-time member is bypassing filters and being toxic. They claim they are 'just joking.' What is your process?",
        "In your opinion, what is the most important rule in our server and why must it be enforced strictly?",
        "How do you handle stress or being overwhelmed by a fast-moving chat during a major drop?",
        "If an admin gives you an instruction you disagree with, how do you handle the situation professionally?",
        "What specific tools or bots (Mee6, Dyno, etc.) are you most proficient in using for moderation?",
        "What is your current timezone and what are your 'peak' activity hours in UTC?",
        "Scenario: You witness a senior staff member leaking internal info. What are your immediate steps?"
    ],
    "pm application": [
        "What is your unique strategy for scouting high-quality partners that match the incredible DROPS vibe?",
        "Provide a list of 3 specific communities you would target for a partnership today and justify why.",
        "How do you handle a partner manager from another server who is being disrespectful or unresponsive?",
        "Describe your past success in growing a server's member count through outreach and networking.",
        "Draft a short, professional partnership requirement list that maintains our server's prestige.",
        "How many hours per week can you spend actively DMing and negotiating with other server managers?",
        "If a partner fails to post our ad, what is your professional 'follow-up' and 'strike' procedure?",
        "What does the incredible DROPS brand represent to you, and how will you pitch that to others?"
    ],
    "dropper application": [
        "What specific categories of items or services are you experienced in dropping for communities?",
        "Provide verifiable proof of your drop history (Vouches, screenshots, or server references).",
        "How do you ensure the items you provide are legitimate and secured against chargebacks or pulls?",
        "What is your weekly hosting schedule? (e.g., Monday/Wednesday at 5 PM UTC).",
        "How do you handle a situation where a drop goes wrong or a user claims they didn't receive an item?",
        "Why should incrediblegg trust you with a role that has a direct impact on our community's economy?",
        "Are you familiar with anti-nuke and anti-scam bot commands used during high-traffic drops?",
        "What is your long-term goal as a Dropper within the incredible DROPS ecosystem?"
    ]
}

# --- Helper Functions ---
def get_role_to_give(role_name):
    """Maps the application type to the correct Discord Role ID."""
    if role_name == "staff application":
        return STAFF_ROLE_ID
    elif role_name == "pm application":
        return PM_ROLE_ID
    elif role_name == "dropper application":
        return DROPPER_ROLE_ID
    return None

async def archive_application(interaction, member, role_name, ai_content, status, reason=None):
    channel_id = ACCEPTED_LOG_ID if status == "Approved" else DENIED_LOG_ID
    archive_channel = interaction.guild.get_channel(channel_id)
    
    color = 0x2ecc71 if status == "Approved" else 0xe74c3c
    embed = discord.Embed(title=f"{status}: {role_name.upper()}", color=color)
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.description = f"**AI Analysis:**\n{ai_content}\n\n**Decision Reason:** {reason if reason else 'Standard processed.'}"
    embed.set_footer(text=f"Processed by {interaction.user.name}")
    
    await archive_channel.send(embed=embed)
    await interaction.message.delete()

# --- Modals & Buttons ---
class ReasonModal(discord.ui.Modal):
    def __init__(self, action, member, role_name, ai_content):
        super().__init__(title=f"{action} Application")
        self.action, self.member, self.role_name, self.ai_content = action, member, role_name, ai_content
        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if self.action == "Approve":
            role_id = get_role_to_give(self.role_name)
            role = interaction.guild.get_role(role_id)
            if role: await self.member.add_roles(role)
            await self.member.send(f"🎉 Approved for **incredible DROPS**!\n**Reason:** {self.reason.value}")
            await archive_application(interaction, self.member, self.role_name, self.ai_content, "Approved", self.reason.value)
        else:
            await self.member.send(f"❌ Your application was denied.\n**Reason:** {self.reason.value}")
            await archive_application(interaction, self.member, self.role_name, self.ai_content, "Denied", self.reason.value)
        await interaction.response.send_message("Archived successfully.", ephemeral=True)

class AdminActions(discord.ui.View):
    def __init__(self, member, role_name, ai_content):
        super().__init__(timeout=None)
        self.member, self.role_name, self.ai_content = member, role_name, ai_content

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id = get_role_to_give(self.role_name)
        role = interaction.guild.get_role(role_id)
        if role: 
            await self.member.add_roles(role)
            await self.member.send(f"🎉 You've been approved for **incredible DROPS**!")
            await archive_application(interaction, self.member, self.role_name, self.ai_content, "Approved")
            await interaction.response.send_message(f"✅ Approved as {role.name}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Error: Correct role not found.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.member.send(f"❌ Your application for **incredible DROPS** was denied.")
        await archive_application(interaction, self.member, self.role_name, self.ai_content, "Denied")
        await interaction.response.send_message("Denied & Archived.", ephemeral=True)

    @discord.ui.button(label="Approve w/ Reason", style=discord.ButtonStyle.secondary)
    async def approve_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReasonModal("Approve", self.member, self.role_name, self.ai_content))

    @discord.ui.button(label="Deny w/ Reason", style=discord.ButtonStyle.secondary)
    async def deny_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReasonModal("Deny", self.member, self.role_name, self.ai_content))

# --- Bot Core ---
class IncredibleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

bot = IncredibleBot()

async def run_application(user, role_name):
    try:
        await user.send(embed=discord.Embed(title="Recruitment System", description=f"Applying for: **{role_name.upper()}**\n\nTake your time (4m per question).", color=GOLD_COLOR))
        
        answers = []
        for i, q in enumerate(QUESTIONS[role_name], 1):
            await user.send(embed=discord.Embed(title=f"Question {i}", description=q, color=GOLD_COLOR))
            msg = await bot.wait_for('message', check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel), timeout=240.0)
            answers.append(f"Q: {q}\nA: {msg.content}")

        await user.send("⏳ **Analyzing your responses with AI...**")
        transcript = "\n\n".join(answers)
        
        res = client_groq.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are the Head of Recruitment for the Discord server 'incredible DROPS'. "
                        "Your job is to provide a detailed internal report to the Owner (incrediblegg) and Admins (adhithi shree, lrgg). "
                        "STRICT RULE: Do NOT talk TO the applicant. Talk ABOUT the applicant. "
                        "Slang like 'yk', 'cuz', 'sigma', and 'aura' is NORMAL—do not judge the applicant's professionalism based on slang. "
                        "Focus on their intent, effort, and whether they can be trusted with server permissions. "
                        "Format your report strictly like this: "
                        "### 🟢 Positives\n[Detailed list of what makes them a good fit]\n\n"
                        "### 🔴 Negatives\n[Detailed list of red flags, threats, or lack of effort]\n\n"
                        "### ⚡ Verdict\n[Give a clear 'Hire' or 'No Hire' with a 1-sentence reason for the admins.]"
                    )
                },
                {"role": "user", "content": f"Role: {role_name}\n\nTranscript:\n{transcript}"}
            ],
            model="llama-3.3-70b-versatile"
        )

        ai_msg = res.choices[0].message.content
        log_channel = bot.get_channel(PENDING_LOG_ID)
        await log_channel.send(ADMIN_PING)
        
        embed = discord.Embed(title=f"New {role_name.upper()} Submission", description=ai_msg, color=GOLD_COLOR)
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        
        await log_channel.send(embed=embed, view=AdminActions(user, role_name, ai_msg))
                # --- Add this to send the transcript file ---
        data = io.BytesIO(transcript.encode())
        await log_channel.send(content=f"**Transcript for {user.name}:**", file=discord.File(data, filename=f"{user.name}_app.txt"))

        await user.send("✅ **Submitted! The staff team will review it soon.**")

    except asyncio.TimeoutError:
        await user.send("❌ **Timed out.** You took too long to respond. Please restart in the server.")

@bot.event
async def on_message(message):
    if message.author.bot: return
    if bot.user.mentioned_in(message):
        content = message.content.lower()
        for role in QUESTIONS.keys():
            if role in content:
                await message.reply(f"Started your **{role}** in DMs! 🚀")
                await run_application(message.author, role)
                return

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} | incredible DROPS System Online")

bot.run(TOKEN)
